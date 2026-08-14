"""
SQLite kalıcılık katmanı: belgeler, chunk'lar ve embedding'ler.

Embedding'ler float32 BLOB olarak saklanır (JSON değil). 1024 boyutlu bir vektör
JSON'da ~20 KB yer kaplar ve her okumada parse edilmesi gerekir; ham float32
buffer'da 4 KB'dır ve `np.frombuffer` ile kopyasız okunur.

Retrieval tarafı her soruda tüm matrisi ister, bu yüzden `load_matrix` sonucu
bellekte önbelleklenir ve yalnızca yazma işlemlerinde geçersiz kılınır.

Bu modül `rag.chunking.Chunk` sınıfını import ETMEZ; chunk nesnelerine yalnızca
attribute üzerinden erişir (source, page, content, via_ocr). Böylece iki modül
arasında bağımlılık oluşmaz.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from . import config

# --------------------------------------------------------------------------- şema

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    filename    TEXT UNIQUE NOT NULL,
    page_count  INTEGER,
    chunk_count INTEGER,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    page        INTEGER,
    content     TEXT NOT NULL,
    via_ocr     INTEGER NOT NULL DEFAULT 0,
    embedding   BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

-- Hibrit retrieval (rag/retrieve.py) için BM25 tam metin indeksi.
--
-- KASITLI OLARAK "external content" (content='chunks') DEĞİL, BAĞIMSIZ bir
-- FTS5 tablosu: content bilgisi burada bir kez daha tutulur (bu projenin
-- ölçeğinde -- birkaç MB metin -- önemsiz bir kopya maliyeti). ÖLÇÜLDÜ:
-- external-content modunda `SELECT COUNT(*) FROM chunks_fts`, FTS indeksi
-- HİÇ doldurulmamış olsa bile `chunks` tablosunun satır sayısını döner --
-- çünkü sorgu doğrudan dış tabloya devrediliyor, indekse hiç bakmıyor. Bu
-- da aşağıdaki _backfill_fts'in "boş mu?" kontrolünü SESSİZCE anlamsız
-- kılıyordu: var olan bir veritabanında (bu şema değişikliğinden önce
-- doldurulmuş) rowid eşleşse bile MATCH sonuç döndürmüyordu, hibrit
-- retrieval fark edilmeden dense-only'ye düşüyordu. Bağımsız modda
-- COUNT(*) gerçek indekslenmiş satır sayısını verir; kontrol güvenilir.
--
-- Senkronu yine TRIGGER'lar sağlar; upsert_document/delete_document bu
-- tabloya hiç dokunmaz, düz INSERT/DELETE'ler tetikleyicileri otomatik
-- çalıştırır.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content, tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    DELETE FROM chunks_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    DELETE FROM chunks_fts WHERE rowid = old.id;
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;

-- Studio artefakt hattı (Faz 1, FEATURE_SPEC.md §9.1). Üç yeni tablo mevcut
-- şemanın SONUNA eklenir; connect() zaten executescript çağırdığı için var
-- olan bir rag.db (kullanıcının veritabanı dahil) ilk açılışta kendiliğinden
-- yükselir, yeniden ingest gerekmez.
CREATE TABLE IF NOT EXISTS artifacts (
    id                 INTEGER PRIMARY KEY,
    kind               TEXT NOT NULL,        -- 'mindmap' | 'report' | 'quiz'
    scope              TEXT NOT NULL,        -- 'corpus' | 'document'
    document_id        INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    title              TEXT NOT NULL,
    params_json        TEXT NOT NULL,
    payload_json       TEXT NOT NULL,        -- ara temsil; render'ın TEK girdisi
    corpus_fingerprint TEXT NOT NULL,
    fidelity_score     REAL,
    generation_ms      INTEGER,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind, scope);

-- score HAM COSINE'dır, Hit.score ile AYNI ölçek (CLAUDE.md §1.1) --
-- normalize edilmez, [0,1]'e gerilmez, verdict'ten geri türetilmez.
CREATE TABLE IF NOT EXISTS artifact_claims (
    id          INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    node_path   TEXT NOT NULL,   -- payload_json'a JSON pointer: /nodes/3
    claim_text  TEXT NOT NULL,
    chunk_id    INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
    score       REAL,            -- HAM COSINE, Hit.score ile AYNI ölçek
    verdict     TEXT NOT NULL    -- 'grounded' | 'weak' | 'unsupported'
);
CREATE INDEX IF NOT EXISTS idx_claims_artifact ON artifact_claims(artifact_id);

-- Faz 1'de yalnızca OLUŞTURULUR; okuyan/yazan kod Faz 4'te gelir. Şimdi
-- eklenmesinin tek sebebi: şema göçü tek seferde ve tek yerde olsun.
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id           INTEGER PRIMARY KEY,
    artifact_id  INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    score        REAL,
    answers_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_artifact ON quiz_attempts(artifact_id);
"""

# --------------------------------------------------------------------------- önbellek

# db_path -> (normalize edilmiş matris, satır metadata'ları)
_matrix_cache: dict[str, tuple[np.ndarray, list[dict]]] = {}
_cache_lock = threading.Lock()


class _Connection(sqlite3.Connection):
    """Bağlantının hangi veritabanına ait olduğunu taşıyan ince alt sınıf.

    Düz `sqlite3.Connection` nesnelerine attribute atanamaz; önbellek anahtarını
    bağlantıyla birlikte taşıyabilmek için alt sınıf gerekiyor.
    """

    cache_key: str = ""


def _cache_key(conn: sqlite3.Connection) -> str:
    """Bağlantıya karşılık gelen önbellek anahtarını üretir."""
    key = getattr(conn, "cache_key", "") or ""
    if key:
        return key
    # `connect()` dışında açılmış bir bağlantı verilmişse dosya yolunu SQLite'a soralım.
    try:
        for _seq, name, filename in conn.execute("PRAGMA database_list"):
            if name == "main":
                return filename or f"memory:{id(conn)}"
    except sqlite3.Error:
        pass
    return f"conn:{id(conn)}"


def _invalidate(conn: sqlite3.Connection) -> None:
    """Yazma sonrası ilgili veritabanının önbelleğini düşürür."""
    key = _cache_key(conn)
    with _cache_lock:
        _matrix_cache.pop(key, None)


def clear_cache() -> None:
    """Tüm bellek önbelleğini geçersiz kılar (manuel invalidasyon)."""
    with _cache_lock:
        _matrix_cache.clear()


# --------------------------------------------------------------------------- bağlantı


def connect(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    """Veritabanını açar, şemayı kurar ve bağlantıyı döndürür.

    Şema kurulumu idempotenttir; aynı yol için defalarca çağrılabilir.
    """
    path = Path(db_path) if db_path is not None else config.DB_PATH
    is_memory = str(path) == ":memory:"

    if not is_memory:
        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: Streamlit script'i her yeniden çalıştırmada farklı
    # bir thread'de koşar, tek bir bağlantıyı @st.cache_resource ile paylaşabilmek
    # için gerekli.
    conn = sqlite3.connect(str(path), factory=_Connection, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.cache_key = f"memory:{id(conn)}" if is_memory else str(path)

    # SQLite'ta foreign key zorlaması VARSAYILAN OLARAK KAPALIDIR ve bağlantı
    # başınadır; açılmazsa ON DELETE CASCADE sessizce çalışmaz.
    conn.execute("PRAGMA foreign_keys = ON")
    if not is_memory:
        # Streamlit okurken ingest yazabilsin diye WAL; veritabanına bir kez yazılır.
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            pass

    conn.executescript(_SCHEMA)
    conn.commit()
    _backfill_fts(conn)
    return conn


def _backfill_fts(conn: sqlite3.Connection) -> None:
    """chunks_fts'i chunks'la senkronlar -- yalnızca GERİYE DÖNÜK boşluk varsa.

    chunks_ai/au/ad trigger'ları yalnızca BUNDAN SONRAKİ yazmaları senkronlar.
    Bu şema değişikliğinden ÖNCE doldurulmuş bir veritabanı (kullanıcının
    mevcut rag.db'si dahil) chunks_fts'te hiç satır bulundurmaz; bu fonksiyon
    olmadan hibrit retrieval o veritabanında sessizce dense-only'ye düşerdi.

    Her connect()'te iki ucuz COUNT(*) çalıştırır; yalnızca chunks doluyken
    chunks_fts boşsa (gerçek bir geriye dönük boşluk -- bkz. _SCHEMA'daki
    external-content notu, bu kontrolün NEDEN bağımsız bir FTS5 tablosu
    gerektirdiğini açıklıyor) toplu INSERT ile doldurur.
    """
    chunks_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if chunks_count == 0:
        return
    fts_count = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    if fts_count > 0:
        return
    conn.execute("INSERT INTO chunks_fts(rowid, content) SELECT id, content FROM chunks")
    conn.commit()


# --------------------------------------------------------------------------- yazma


def _to_blob(vector: Sequence[float], expected_dim: Optional[int]) -> tuple[bytes, int]:
    """Vektörü float32 BLOB'a çevirir ve boyutunu döndürür."""
    arr = np.asarray(vector, dtype=np.float32).ravel()
    if arr.size == 0:
        raise ValueError("Boş embedding vektörü kaydedilemez.")
    if expected_dim is not None and arr.size != expected_dim:
        raise ValueError(
            f"Embedding boyutları tutarsız: {arr.size} != {expected_dim}. "
            f"Tüm chunk'lar aynı modelden gelmeli."
        )
    return arr.tobytes(), int(arr.size)


def upsert_document(
    conn: sqlite3.Connection,
    filename: str,
    page_count: int,
    chunks: Sequence[Any],
    embeddings: Sequence[Sequence[float]],
) -> int:
    """Bir belgeyi chunk'ları ve embedding'leriyle birlikte yazar, document_id döndürür.

    Aynı filename daha önce yüklenmişse eski chunk'lar silinip yenileri yazılır
    (kullanıcı aynı PDF'i tekrar yükleyebilir). Silme + yazma tek transaction
    içindedir: hata olursa veritabanı yarım belgeyle kalmaz.

    chunks öğelerinden yalnızca `source`, `page`, `content`, `via_ocr`
    attribute'ları okunur (duck typing).
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunk sayısı ({len(chunks)}) ile embedding sayısı "
            f"({len(embeddings)}) eşleşmiyor."
        )

    ingested_at = datetime.now().isoformat(timespec="seconds")

    # Satırları transaction'a girmeden hazırla; doğrulama hatası veritabanına
    # hiç dokunmadan patlasın.
    dim: Optional[int] = None
    rows: list[tuple] = []
    for chunk, vector in zip(chunks, embeddings):
        blob, dim = _to_blob(vector, dim)
        rows.append(
            (
                getattr(chunk, "source", filename),
                getattr(chunk, "page", None),
                getattr(chunk, "content"),
                int(bool(getattr(chunk, "via_ocr", False))),
                blob,
            )
        )

    try:
        with conn:  # commit / hata durumunda rollback
            conn.execute(
                """
                INSERT INTO documents (filename, page_count, chunk_count, ingested_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    page_count  = excluded.page_count,
                    chunk_count = excluded.chunk_count,
                    ingested_at = excluded.ingested_at
                """,
                (filename, page_count, len(rows), ingested_at),
            )
            row = conn.execute(
                "SELECT id FROM documents WHERE filename = ?", (filename,)
            ).fetchone()
            document_id = int(row[0])

            # Yeniden yükleme: eski chunk'lar gitmeli, yoksa sayı katlanır.
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            if rows:
                conn.executemany(
                    """
                    INSERT INTO chunks
                        (document_id, source, page, content, via_ocr, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [(document_id, *r) for r in rows],
                )
    finally:
        # Transaction başarısız olsa bile önbelleği düşürmek güvenli taraftır.
        _invalidate(conn)

    return document_id


def delete_document(conn: sqlite3.Connection, filename: str) -> bool:
    """Belgeyi siler. Chunk'lar ON DELETE CASCADE ile birlikte gider.

    Belge bulunamazsa False döner.
    """
    try:
        with conn:
            cur = conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))
            deleted = cur.rowcount > 0
    finally:
        _invalidate(conn)
    return deleted


# --------------------------------------------------------------------------- okuma


def list_documents(conn: sqlite3.Connection) -> list[dict]:
    """Yüklü belgeleri listeler (Streamlit kenar çubuğu için)."""
    cur = conn.execute(
        """
        SELECT filename, page_count, chunk_count, ingested_at
        FROM documents
        ORDER BY ingested_at DESC, filename ASC
        """
    )
    return [
        {
            "filename": r["filename"],
            "page_count": r["page_count"],
            "chunk_count": r["chunk_count"],
            "ingested_at": r["ingested_at"],
        }
        for r in cur.fetchall()
    ]


_FTS_TOKEN = re.compile(r"\w+", re.UNICODE)

# ÖLÇÜLDÜ (eval/eval_set.json Q22 regresyonu): filtresiz OR-of-all-terms bir
# doğal dil sorgusunda ("Yaklaşık en yakın komşu aramasının doğruluk ile hız
# arasında nasıl bir değiş tokuşu vardır?") bağlaç/işlev sözcükleri ("ile",
# "nasıl", "bir", "vardır", "arasında"...) neredeyse HER chunk'la eşleşiyor
# -- bm25() bunları zayıf ama sıfır olmayan skorlarla sıralıyor, RRF'ye
# gürültü olarak karışıyor ve doğru (ama saf semantik) sonucu top-k'den
# İTİYOR. Bu, dense-only'de 3/3 geçen diller arası testi 1/3'e düşürdü.
#
# Bu liste kapsamlı bir NLP stopword listesi DEĞİLDİR; yalnızca en sık geçen,
# en az ayırt edici bağlaç ve işlev sözcüklerini kapsar. Amaç mükemmel
# temizlik değil, RRF'yi kirleten en kaba gürültüyü kesmek -- BM25 hâlâ yalnızca
# ADAY havuzunu genişletiyor (rag/config.py), bu yüzden aşırı temizlik riski
# önemsiz: gerçek bir lexical eşleşme kaybolursa dense zaten aynı chunk'ı
# kendi yolundan bulur.
_FTS_STOPWORDS = frozenset(
    """
    ve veya ile bir bu şu o da de ki mi mı mu mü ne nedir neydi nasıl neden
    niçin niye gibi kadar göre için çok az en daha ama fakat ancak çünkü
    eğer ise olan olarak var yok vardır yoktur değil hem ya yani tüm bütün
    her hiç bazı diğer kendi sonra önce arasında altında üstünde içinde
    dışında olur oldu olacak eder edilir yapar yapılır hangi kaç nerede kim
    benim senin onun bizim sizin onların bunun şunun ona buna şuna
    a an the is are was were be been of to in on at for with and or but
    not this that these those it its as by from what which who how why
    when where do does did will would can could should
    """.split()
)


def bm25_candidates(conn: sqlite3.Connection, query: str, limit: int) -> list[int]:
    """Sorguyla sözcüksel olarak en alakalı chunk id'lerini alaka sırasıyla döndürür.

    rag/retrieve.py'deki hibrit retrieval için: dense (cosine) aramanın
    kaçırdığı BİREBİR terim eşleşmelerini (özel adlar, model kimlikleri,
    sayılar, diller arası teknik terimler) yakalar. Skoru DÖNDÜRMEZ, yalnızca
    sırayı -- final Hit.score her zaman cosine kalır (MIN_SCORE eşiği,
    Inspector renk bantları ve DESIGN_SYSTEM §1.2 semantiği bu alana bağlı;
    bir BM25/RRF skoru buraya karışırsa hepsi sessizce anlamını yitirir).

    Sorgu FTS5'in ÖZEL SÖZDİZİMİNE (", *, ^, AND/OR/NOT) ham haliyle
    geçirilmez -- kullanıcı girdisi güvenilmez. Yalnızca \\w+ ile ayrıştırılan
    sözcükler (bağlaç/işlev sözcükleri elenmiş -- yukarı bkz.), her biri ayrı
    tırnaklanıp OR ile birleştirilerek aranır.

    _FTS_STOPWORDS sabit bir liste ve TAMAMLANAMAZ -- Türkçe eklemeli bir dil,
    "nedir" gibi listeye alınmamış bir sözcük bu KORPUSA özgü gürültü
    üretebilir (ÖLÇÜLDÜ: bu projenin data/ fixture'larının hepsi "... Nedir"
    başlığıyla başlıyor, "nedir" sözcüğü neredeyse HER chunk'la eşleşiyordu).
    Bu yüzden ikinci, KORPUSA UYARLANAN bir süzgeç var: bir terim chunk'ların
    %40'ından FAZLASINDA geçiyorsa (df -- document frequency), ayırt edici
    değildir ve elenir. Sabit listeyi büyütmeye çalışmak yerine bu, hangi
    korpus yüklenirse yüklensin kendiliğinden doğru sözcükleri eler.
    """
    terms = [
        t for t in _FTS_TOKEN.findall(query or "")
        if len(t) >= 2 and t.lower() not in _FTS_STOPWORDS
    ]
    if not terms:
        return []

    total = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    if total == 0:
        return []
    max_df = max(1, int(total * 0.4))
    discriminating = []
    for t in terms:
        try:
            df = conn.execute(
                'SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH ?', (f'"{t}"',)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            return []
        if 0 < df <= max_df:
            discriminating.append(t)
    if not discriminating:
        return []

    match_expr = " OR ".join(f'"{t}"' for t in discriminating)
    try:
        cur = conn.execute(
            """
            SELECT rowid FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY bm25(chunks_fts)
            LIMIT ?
            """,
            (match_expr, limit),
        )
        return [int(r[0]) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        # FTS5 derlenmemiş bir SQLite ile karşılaşılırsa (nadiren): hibrit
        # retrieval sessizce dense-only'ye düşer, hata fırlatıp kullanıcıyı
        # engellemez. rag/retrieve.py bu boş listeyi normal karşılar.
        return []


def get_document_chunks(
    conn: sqlite3.Connection,
    filename: str,
    limit: Optional[int] = None,
) -> list[dict]:
    """Bir belgenin chunk'larını belge sırasıyla döndürür (benzerlik YOK).

    Özetleme yolu için (rag/query_router.py): "belgeyi özetle" sorgusunun
    eşleşecek bir konusu olmadığı için chunk'lar benzerlikle değil, doğrudan
    belge kimliğinden çekilir.

    limit verilirse chunk'lar belge boyunca EŞİT ARALIKLI örneklenir. İlk N
    tanesi alınsaydı özet yalnızca belgenin başını görür, sonuç sistematik
    olarak eksik olurdu. İlk ve son chunk her zaman korunur.
    """
    cur = conn.execute(
        """
        SELECT c.source, c.page, c.content, c.via_ocr
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.filename = ?
        ORDER BY c.id
        """,
        (filename,),
    )
    rows = [
        {
            "source": r["source"],
            "page": r["page"],
            "content": r["content"],
            "via_ocr": bool(r["via_ocr"]),
        }
        for r in cur.fetchall()
    ]

    if limit is None or len(rows) <= limit or limit <= 0:
        return rows

    # Eşit aralıklı örnekleme: son indeks limit-1'e bölünerek uçlar korunur.
    step = (len(rows) - 1) / (limit - 1) if limit > 1 else 0
    picked = sorted({int(round(i * step)) for i in range(limit)})
    return [rows[i] for i in picked]


def corpus_stats(conn: sqlite3.Connection) -> dict:
    """Korpusun toplam sayıları. Korpus sorularında LLM'e hiç gidilmez."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS documents,
               COALESCE(SUM(page_count), 0) AS pages,
               COALESCE(SUM(chunk_count), 0) AS chunks
        FROM documents
        """
    ).fetchone()
    return {
        "documents": int(row["documents"]),
        "pages": int(row["pages"]),
        "chunks": int(row["chunks"]),
    }


def corpus_fingerprint(conn: sqlite3.Connection) -> str:
    """Korpusun sha256 parmak izi -- artefakt bayatlığını (staleness) saptamak için.

    Studio artefaktları (rag/artifacts/) bu dizeyi kayıt anında saklar; okuma
    anında güncel değerle karşılaştırılır, farklıysa artefakt "bayat" sayılır
    (silinmez, otomatik yeniden üretilmez -- FEATURE_SPEC.md §9.2).

    Türetme, ölçülebilir olsun diye TAM tanımlıdır:
        satırlar = [f"{id}:{chunk_count}:{ingested_at}" için her documents satırı]
        girdi    = "\\n".join(sorted(satırlar))     -- sıralama SATIRLARIN TAMAMINA
                                                        uygulanır, id'ye değil
        sonuç    = sha256(girdi.encode("utf-8")).hexdigest()
    id zaten satırın başında olduğu için sonuç deterministiktir ve SQL'in
    döndürdüğü sıraya bağımlı kalmaz.

    Boş korpus da geçerli bir parmak izi üretir (boş dizenin sha256'sı) --
    çağıran taraf ayrıca None kontrolü yapmak zorunda kalmaz.

    BİLİNEN SINIR: ingested_at saniye çözünürlüklü (upsert_document
    timespec="seconds" kullanıyor). Aynı belgenin AYNI SANİYE içinde aynı
    chunk sayısıyla yeniden yüklenmesi aynı parmak izini üretir -- bir
    bayatlık sinyali kaçırabilir. Gerçek bir yeniden yüklemede içerik
    değiştiyse chunk_count de neredeyse her zaman değişir ve bu yol insan
    hızında bir işlemdir; bu sınır documents/eval sözleşmesini bozmamak
    (zaman damgası çözünürlüğünü değiştirmemek) için bilerek kabul edildi.
    """
    rows = conn.execute("SELECT id, chunk_count, ingested_at FROM documents").fetchall()
    lines = [f"{r['id']}:{r['chunk_count']}:{r['ingested_at']}" for r in rows]
    payload = "\n".join(sorted(lines))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_matrix(conn: sqlite3.Connection) -> tuple[np.ndarray, list[dict]]:
    """Tüm chunk embedding'lerini (N, D) float32 matris + metadata listesi olarak verir.

    Matris L2-normalize edilmiştir; sorgu vektörü de normalize edildiğinde cosine
    benzerliği tek bir `matrix @ query_vec` çarpımına iner.

    Boş veritabanında (0, 0) shape'li matris ve boş liste döner — çağıran taraf
    özel durum kontrolü yapmak zorunda kalmasın diye şekil yine 2 boyutludur.

    Sonuç db_path anahtarıyla önbelleklenir ve yazma işlemlerinde otomatik
    geçersiz kılınır. Döndürülen matris salt okunurdur; yanlışlıkla yerinde
    değiştirilip önbelleği bozması engellenir.
    """
    key = _cache_key(conn)
    with _cache_lock:
        cached = _matrix_cache.get(key)
    if cached is not None:
        return cached

    cur = conn.execute(
        """
        SELECT id, source, page, content, via_ocr, embedding
        FROM chunks
        ORDER BY id
        """
    )
    records = cur.fetchall()

    if not records:
        matrix = np.zeros((0, 0), dtype=np.float32)
        matrix.flags.writeable = False
        result: tuple[np.ndarray, list[dict]] = (matrix, [])
        with _cache_lock:
            _matrix_cache[key] = result
        return result

    # Vektör boyutu koda gömülmez; ilk kayıttan türetilir (model değişirse
    # yeniden ingest gerekir, aşağıdaki kontrol bunu erken yakalar).
    dim = len(records[0]["embedding"]) // np.dtype(np.float32).itemsize
    matrix = np.empty((len(records), dim), dtype=np.float32)
    metas: list[dict] = []

    for i, r in enumerate(records):
        vec = np.frombuffer(r["embedding"], dtype=np.float32)
        if vec.size != dim:
            raise ValueError(
                f"chunk id={r['id']} vektör boyutu {vec.size}, beklenen {dim}. "
                f"Veritabanı farklı embedding modelleriyle doldurulmuş; "
                f"belgeleri yeniden yükleyin."
            )
        matrix[i] = vec
        metas.append(
            {
                "id": r["id"],
                "source": r["source"],
                "page": r["page"],
                "content": r["content"],
                "via_ocr": bool(r["via_ocr"]),
            }
        )

    # L2 normalizasyon. Sıfır vektör (boş/bozuk embedding) sıfıra bölünmesin diye
    # normu 1.0 kabul edilir; satır sıfır kalır ve hiçbir sorguyla eşleşmez.
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, np.where(norms == 0.0, 1.0, norms), out=matrix)

    matrix.flags.writeable = False
    result = (matrix, metas)
    with _cache_lock:
        _matrix_cache[key] = result
    return result
