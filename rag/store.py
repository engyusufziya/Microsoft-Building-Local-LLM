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
    return conn


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
