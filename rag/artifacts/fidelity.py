"""
Sadakat kapısı (fidelity gate) -- Studio hattının TEK savunma noktası.

Her iddia bir chunk'a bağlanır, bağ HAM COSINE ile ölçülür (retrieval'la aynı
asimetrik embed yolu -- USE_QUERY_INSTRUCTION sözleşmesi burada da geçerli,
aksi halde skorlar Hit.score ile karşılaştırılabilir olmaz), ölçüden bir
`verdict` türetilir.

DİKKAT: `verdict` bantları DESIGN_SYSTEM §1.2'nin (§ScoreBadge) bantlarıyla
AYNI DEĞİL -- §1.2 "bu chunk ne kadar alakalı" sorusunu, verdict "bu iddia
belgede var mı" sorusunu cevaplıyor. Birini diğerinden türetmeye çalışmak
ikisini de bozar (FEATURE_SPEC.md §9.6).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from .. import config, models, store

@dataclass(frozen=True)
class ClaimBinding:
    node_path: str
    claim_text: str
    chunk_id: Optional[int]   # bağlanamadıysa (korpus boşsa) None
    score: Optional[float]    # HAM COSINE; bağlanamadıysa None
    verdict: str               # 'grounded' | 'weak' | 'unsupported'


def verdict_for(score: Optional[float]) -> str:
    """Ham cosine skorundan verdict türetir (FIDELITY_MIN_SCORE = 0.45).

        grounded    : score >= FIDELITY_MIN_SCORE                     (>= 0.45)
        weak        : score >= FIDELITY_MIN_SCORE - WEAK_BAND_WIDTH  (0.35-0.45)
        unsupported : altı, veya score is None                        (< 0.35)

    Parantez içindeki sayılar bugünkü config değerleriyle; eşik tek doğruluk
    kaynağı olan rag/config.py'den okunur.
    """
    if score is None:
        return "unsupported"
    if score >= config.FIDELITY_MIN_SCORE:
        return "grounded"
    if score >= config.FIDELITY_MIN_SCORE - config.FIDELITY_WEAK_BAND_WIDTH:
        return "weak"
    return "unsupported"


def bind_claims(
    conn: sqlite3.Connection, claims: Sequence[tuple[str, str]]
) -> list[ClaimBinding]:
    """Her (node_path, claim_text) iddiasını en yakın chunk'a bağlar.

    İddia metinleri models.embed_texts(..., is_query=True) ile embed edilir,
    store.load_matrix() matrisiyle çarpılır, en yüksek cosine'ı veren chunk
    seçilir. Skor OLDUĞU GİBİ yazılır -- yeniden ölçeklenmez, germe yok.

    Korpus boşsa (matrix shape (0, 0)) hiçbir iddia bağlanamaz; hepsi
    chunk_id=None, score=None, verdict='unsupported' olarak döner.
    """
    if not claims:
        return []

    matrix, meta = store.load_matrix(conn)
    if matrix.shape[0] == 0:
        return [
            ClaimBinding(node_path, claim_text, None, None, verdict_for(None))
            for node_path, claim_text in claims
        ]

    texts = [claim_text for _, claim_text in claims]
    vectors = models.embed_texts(texts, is_query=True)

    bindings: list[ClaimBinding] = []
    for (node_path, claim_text), vector in zip(claims, vectors):
        v = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(v))
        if norm:
            v = v / norm
        sims = matrix @ v
        best_idx = int(np.argmax(sims))
        score = float(sims[best_idx])
        chunk_id = int(meta[best_idx]["id"])
        bindings.append(
            ClaimBinding(node_path, claim_text, chunk_id, score, verdict_for(score))
        )
    return bindings


def fidelity_score(bindings: Sequence[ClaimBinding]) -> Optional[float]:
    """grounded iddia sayısı / toplam iddia sayısı -- BİR ORANDIR, benzerlik değil.

    İddia yoksa None döner (1.0 ya da 0.0 değil): iddiasız bir artefaktın
    sadakati ölçülemez, 1.0 yazmak mükemmel bir skor uydurmak olurdu.
    """
    if not bindings:
        return None
    grounded = sum(1 for b in bindings if b.verdict == "grounded")
    return grounded / len(bindings)


# ---------------------------------------------------------------------------
# İKİNCİ KATMAN -- terim desteği (FEATURE_SPEC.md §10.6, Faz 2 EKİ).
#
# bind_claims'in AYRISINDA çalışır, bağlamadan SONRA. verdict_for / bind_claims
# / fidelity_score DAVRANIŞLARI bu bölümle DEĞİŞMEZ -- eval/fidelity_trap.py
# pinlediği 0.5487/grounded ölçümü hâlâ bind_claims'ten aynen çıkar
# (FEATURE_SPEC.md §10.1.2). Bu katman, cosine'ın kaçırdığı özel adları/model
# kimliklerini (bilinen entailment boşluğu, yukarıdaki modül docstring'i)
# sözcüksel doküman-frekansıyla yakalar -- rag/config.py'deki hibrit
# retrieval gerekçesinin birebir aynısı: anlamsal benzerlik özel adları
# kaçırır, alt dize eşleşmesi tam da onları yakalar.

_TERM_SPLIT_RE = re.compile(r"[^0-9A-Za-zÇĞİıÖŞÜçğıöşü\-.]+")


def _term_lower(text: str) -> str:
    """Türkçe-duyarlı küçültme: İ->i, I->ı, SONRA str.lower().

    Düz str.lower() 'İ' (U+0130) için BİRLEŞEN NOKTA üretir (iki kod
    noktasına ayrılan "i̇" -- görsel olarak "i" ile aynı ama karşılaştırmada
    eşleşmez). Bu yüzden Türkçe büyük harfler ÖNCE elle eşlenir, ardından
    kalan (çoğunlukla ASCII) harfler için normal lower() çağrılır.
    """
    return text.replace("İ", "i").replace("I", "ı").lower()


def _raw_terms(text: str) -> list[str]:
    """Metni terimlere böler ama küçültmez (FEATURE_SPEC.md §10.6, kural 1).

    Alfanümerik olmayan karakterlerden böler; token İÇİNDEKİ '-' ve '.'
    KORUNUR (aksi halde "GPT-4" ve "qwen2.5-7b" parçalanır). Baştaki/sondaki
    '-'/'.' atılır (cümle sonu noktası ya da tire bir token'a yapışıp kalmasın).

    Ham biçim korunur çünkü kural 4'ün varlık şartı BÜYÜK HARFE bakar; küçültme
    o bilgiyi yok eder.
    """
    tokens = []
    for raw in _TERM_SPLIT_RE.split(text):
        cleaned = raw.strip("-.")
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _term_tokens(text: str) -> list[str]:
    """_raw_terms + Türkçe-duyarlı küçültme (kural 1-2)."""
    return [_term_lower(raw) for raw in _raw_terms(text)]


_UPPERCASE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÇĞİIÖŞÜ")


def _entity_like(raw: str, index: int, is_title: bool = False) -> bool:
    """Token bir ÖZEL AD ya da MODEL KİMLİĞİ gibi mi duruyor (§10.6, kural 4b)?

    İki işaretten biri yeterli, ikisi de metnin KENDİ yazımından türer --
    sözlük, durak-kelime listesi ya da kök çözümleyici YOK:

      - rakam içerir -> "gpt-4", "qwen2.5-7b", "200-400" (model kimlikleri ve
        sürüm numaraları bu projenin alanında her zaman rakam taşır)
      - cümle başı OLMAYAN bir konumda büyük harf taşır -> "OpenAI", "SQLite"

    Cümle başı (index == 0) DIŞARIDA bırakılır: Türkçede her cümle büyük harfle
    başlar, dolayısıyla ilk token'ın büyük harfi özel ad işareti değildir.

    `is_title=True` ise BÜYÜK HARF KOLU HİÇ ÇALIŞMAZ; yalnızca rakam işareti
    kalır. Gerekçe ölçümden geldi (FEATURE_SPEC §11.4): metin bir BAŞLIK
    olduğunda büyük harf hiçbir bilgi taşımaz -- başlıkta zaten her sözcük
    büyük yazılır. Faz 3'ün ilk koşumunda modelin 7 etiketinin 3'ü tam bu
    yüzden düştü ("Retrieval-Augmented Generation Anlatımı", "Yakın Komşu Arama
    Teknikleri", "Embedding Ve Benzerlik Analizi") ve üçü de YANLIŞ POZİTİFTİ.
    Önce prompt'a "cümle düzeni kullan" kuralı eklendi; ÖLÇÜLDÜ ve İŞE
    YARAMADI (model kuralı yok sayıp "Embedding Ve Benzerlik Analizi" üretti --
    bu projenin "üretim yalnızca prompt ile kontrol edilir" varsayımının
    sınırı). Bu yüzden ayrım ÇAĞIRANA taşındı: cümle veren çağıran (rapor,
    quiz) varsayılanı kullanır ve DAVRANIŞI DEĞİŞMEZ -- Faz 2'nin ölçülmüş
    43/47 sonucu ve report_trap.py aynen geçerli kalır.

    Eşik ya da oran YOK: "başlık mı" sorusunu metnin biçimine bakarak TAHMİN
    etmiyoruz, çağıran zaten BİLİYOR.

    RAKAMSIZ TİRE/NOKTA İŞARETİ YOK -- ölçümle çıkarıldı (FEATURE_SPEC §10.6):
    üretim korpusunda (61 chunk) gerçek raporun 13 düşüşünden 4'ü yalnızca bu
    koldan geliyordu ve hepsi YANLIŞ POZİTİFTİ ("soru-cevap" -- Türkçe birleşik
    sözcük, hallüsinasyon değil). Aynı kol hiçbir gerçek yakalama üretmedi:
    tuzağın "gpt-4"ü rakamdan, "openaı"sı büyük harften zaten yakalanıyor.
    """
    if any(ch.isdigit() for ch in raw):
        return True
    if is_title:
        return False
    return index > 0 and any(ch in _UPPERCASE for ch in raw)


def _corpus_term_df(conn: sqlite3.Connection) -> tuple[dict[str, int], int]:
    """Her terimin korpusta kaç chunk'ta geçtiğini (doküman frekansı) sayar.

    Model YÜKLEMEZ -- saf metin taraması. unverified_terms her çağrıda yeniden
    hesaplar: bu korpus ölçeğinde (20-60 chunk) birkaç milisaniyedir ve
    rag/store.py'ye (bu modülün değiştirme yetkisi olmayan bir dosya) yeni bir
    önbellekleme sözleşmesi eklemeden basit kalır (CLAUDE.md §2.2).
    """
    rows = conn.execute("SELECT content FROM chunks").fetchall()
    n = len(rows)
    df: dict[str, int] = {}
    for row in rows:
        for token in set(_term_tokens(row["content"])):
            df[token] = df.get(token, 0) + 1
    return df, n


def distinctive_terms(
    conn: sqlite3.Connection, text: str, *, is_title: bool = False
) -> list[tuple[str, str]]:
    """Metnin AYIRT EDİCİ terimleri: (ham yazım, küçültülmüş) çiftleri.

    unverified_terms'in 1-4. kuralları burada uygulanır; 5. kural (bağlam
    chunk'larında geçiyor mu) UYGULANMAZ -- o, çağıranın sorusudur.

    İki tüketicisi var ve ikisinin de AYNI "ayırt edici" tanımını kullanması
    zorunlu (CLAUDE.md §1.3'ün aynı gerekçesi, tek doğruluk kaynağı):
      - unverified_terms (Faz 2 sadakat katmanı, aşağıda),
      - quiz'in boşluk/çeldirici seçimi (Faz 4, §12.4) -- bir soruda
        boşaltılacak terim, tam da korpusta ayırt edici olan terimdir.

    Faz 3'te unverified_terms'ten ÇIKARILDI; davranışı değişmedi
    (backend/tests/test_artifacts_report.py'nin dört terim testi aynen geçiyor).

    BİLİNEN SINIR: config.FIDELITY_TERM_MIN_LENGTH (4) yüzünden kısa sayılar
    ("130", "30", "16") ayırt edici SAYILMAZ. Sadakat katmanı için bu doğru
    kalibrasyon (kısa token gürültülüdür); quiz için bunun sonucu, kısa
    sayıların boşluk olarak seçilememesidir -- eşiği quiz için gevşetmek
    kuralı ikiye bölerdi, o yüzden gevşetilmedi (§12.4).
    """
    df, n = _corpus_term_df(conn)
    if n == 0:
        return []

    terms: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(_raw_terms(text)):
        token = _term_lower(raw)
        if token in seen:  # sırayı koruyarak tekilleştir
            continue
        seen.add(token)
        if len(token) < config.FIDELITY_TERM_MIN_LENGTH:
            continue
        ratio = df.get(token, 0) / n
        if ratio > config.FIDELITY_TERM_DF_MAX_RATIO:
            continue  # yaygın terim -- ayırt edici değil, kontrol edilmez
        if not _entity_like(raw, index, is_title):
            continue  # sıradan sözcük -- korpusta yokluğu hallüsinasyon işareti değil
        terms.append((raw, token))
    return terms


def unverified_terms(
    conn: sqlite3.Connection,
    claim_text: str,
    context_chunk_ids: Sequence[int],
    *,
    is_title: bool = False,
) -> list[str]:
    """İddiadaki AYIRT EDİCİ terimlerden bağlamda geçmeyenleri döndürür.

    Kural (FEATURE_SPEC.md §10.6, tek kural, sözlük yok):
      1-2) _raw_terms / _term_lower: alfanümerik olmayanlardan böl (- ve .
           korunur), Türkçe-duyarlı küçült.
      3) config.FIDELITY_TERM_MIN_LENGTH'ten kısa token atılır.
      4) Token AYIRT EDİCİ sayılır <=> (a) korpusta geçtiği chunk oranı
         config.FIDELITY_TERM_DF_MAX_RATIO'dan KÜÇÜK VEYA EŞİT (df=0 dahil)
         VE (b) _entity_like: özel ad / model kimliği gibi yazılmış.
      5) Ayırt edici token, bağlam chunk'larının birleştirilmiş metninde ALT
         DİZE olarak geçmiyorsa "doğrulanamamış" sayılır (bidirectional Türkçe
         ek eşleşmesi buradan gelir: "sqlite" ⊂ "sqlite'ın" her iki yönde).

    (b) şartı Faz 2'nin kapanma ölçümünde EKLENDİ ve ölçümle gerekçelendirildi
    (§10.6 "İKİNCİ ÖLÇÜM"): yalnız df'ye bakan biçim, eval.db üzerinde üretilen
    gerçek raporun 47 cümlesinden 42'sini düşürüyordu -- çünkü 20 chunk'lık bir
    korpusta sıradan Türkçe çekim ("dayanır", "olanak", "yanıt") da df=0 alıyor
    ve hallüsinasyondan ayırt edilemiyor. Varlık şartı ikisini ayırır: aynı
    koşumda 43/47 cümle rapora girdi, tuzak yalnızca DOĞRU iki terimle
    ("gpt-4", "openaı") düştü.

    context_chunk_ids BOŞSA çağıran taraf ClaimBinding.chunk_id'yi bağlam
    olarak GEÇMELİDİR (§10.6) -- bu fonksiyonun imzası chunk_id almaz, bu
    yüzden fallback ÇAĞIRANIN sorumluluğudur. Burada boş liste "muafiyet"
    olarak YORUMLANMAZ: context_chunk_ids gerçekten boş gelirse hiçbir chunk
    metni birleştirilmez, dolayısıyla iddianın tüm ayırt edici terimleri
    doğrulanamamış sayılır -- katman sessizce kapanmaz.
    """
    if context_chunk_ids:
        placeholders = ",".join("?" for _ in context_chunk_ids)
        rows = conn.execute(
            f"SELECT content FROM chunks WHERE id IN ({placeholders})",
            list(context_chunk_ids),
        ).fetchall()
        context_text = _term_lower(" ".join(row["content"] for row in rows))
    else:
        context_text = ""

    return [
        token
        for _raw, token in distinctive_terms(conn, claim_text, is_title=is_title)
        if token not in context_text
    ]


def should_drop(binding: ClaimBinding, unverified: Sequence[str]) -> Optional[str]:
    """Düşürme sebebini döndürür; düşürülmeyecekse None (FEATURE_SPEC.md §10.6).

    Kapalı küme:
        verdict == 'unsupported'                    -> 'unsupported'
        verdict == 'weak'                            -> 'weak'
        verdict == 'grounded' ama unverified boş değil -> 'unverified_terms'
        aksi halde                                   -> None (rapora girer)

    Saf fonksiyon: hiçbir I/O yapmaz, bind_claims/unverified_terms'in
    sonuçlarını birleştirir.
    """
    if binding.verdict == "unsupported":
        return "unsupported"
    if binding.verdict == "weak":
        return "weak"
    if binding.verdict == "grounded" and unverified:
        return "unverified_terms"
    return None
