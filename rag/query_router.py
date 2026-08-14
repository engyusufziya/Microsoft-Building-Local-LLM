"""Sorgu sınıfı yönlendirme: her soru benzerlik aramasına gitmez.

NEDEN VAR (ölçümle):
    Dense retrieval anlam eşleştirir. "İlgili dökümanı bana özetle" sorgusu
    hiçbir İÇERİK terimi taşımaz -- eşleşecek bir konusu yoktur. Aynı Türkçe
    pasaja karşı ölçüldü:

        "RAG kaç adımdan oluşur?"      -> 0.766   (içerik sorusu)
        "İlgili dökümanı bana özetle"  -> 0.322   (meta sorgu)

    Fark -0.445. Belge İngilizceyse üstüne diller arası ceza (-0.077) binip
    0.273'e iner. Eşik 0.45 olduğu için sistem "bu bilgi belgelerde yok" der --
    oysa belge oradadır ve kullanıcı içerik değil, BELGENİN KENDİSİ hakkında
    bir şey sormuştur.

TASARIM KARARI:
    Eşiği düşürmek yanlış çözümdür; eşik tam da tasarlandığı gibi çalıştı ve
    projenin "bilmiyorum" garantisi ona dayanıyor. Bunun yerine sorgu, aramaya
    hiç gitmeden ayrı bir yola yönlendirilir.

    Sınıflandırma KURAL TABANLIDIR, LLM çağrısı yapmaz: yönlendirme her sorunun
    önünde durduğu için gecikme eklememeli, offline çalışmalı ve testte
    deterministik olmalı.

Üç yol:
    search    -> mevcut RAG yolu (varsayılan; davranışı değişmedi)
    summarize -> belgeyi benzerlikle arama, chunk'larını doğrudan belgeden al
    corpus    -> korpusun kendisi hakkında soru; LLM'e hiç gitme, store'dan cevapla
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

RouteKind = Literal["search", "summarize", "corpus"]


@dataclass(frozen=True)
class Route:
    kind: RouteKind
    # summarize yolunda, sorguda bir belge adı geçiyorsa o ad; yoksa None
    # (çağıran taraf tek belge varsa onu seçer, birden fazlaysa kullanıcıya sorar).
    target: Optional[str] = None


# --------------------------------------------------------------------------- normalizasyon

# Türkçe büyük/küçük harf tuzağı: "İlgili".lower() -> "i̇lgili" (i + birleşen
# nokta), düz bir `in` karşılaştırması bunu kaçırır. Ayrıca kullanıcı aksansız
# yazabilir ("dokuman", "ozetle"). Bu yüzden eşleştirme ASCII'ye katlanmış
# metin üzerinde yapılır.
_FOLD = str.maketrans(
    {
        "İ": "i", "I": "i", "ı": "i",
        "Ş": "s", "ş": "s",
        "Ğ": "g", "ğ": "g",
        "Ü": "u", "ü": "u",
        "Ö": "o", "ö": "o",
        "Ç": "c", "ç": "c",
        "Â": "a", "â": "a",
        "Î": "i", "î": "i",
        "Û": "u", "û": "u",
    }
)


def normalize(text: str) -> str:
    """Eşleştirme için metni ASCII'ye katlar ve küçültür."""
    return (text or "").translate(_FOLD).lower()


# --------------------------------------------------------------------------- desenler

# Türkçe eklemeli bir dil: "belge" -> "belgeyi", "belgeler", "belgelerde".
# Bu yüzden desenler KÖK olarak tutulur ve alt dize olarak aranır; ek almış
# bütün biçimleri tek desen yakalar.

# Korpusun kendisi hakkında sorular -- cevabı veritabanında, belge içinde değil.
_CORPUS_PATTERNS = (
    "kac belge", "kac tane belge", "kac dokuman", "kac dosya", "kac pdf",
    "hangi belge", "hangi dokuman", "hangi dosya",
    "belge listesi", "dosya listesi", "yuklu belge", "yukledigim belge",
    "neler yuklu", "nelerivar", "belgelerim",
    "how many document", "how many file", "how many pdf",
    "which document", "which file", "what document", "list document",
    "loaded document", "uploaded document",
)

# Özetleme/meta fiilleri.
_SUMMARIZE_PATTERNS = (
    "ozetle", "ozeti", "ozet ", "ozetler", "ozetleyebilir", "ozetler misin",
    "ne anlatiyor", "neyi anlatiyor", "nelerden bahsediyor", "neden bahsediyor",
    "konusu ne", "ne hakkinda", "icerigi ne", "genel bilgi ver",
    "summarize", "summary", "tldr", "tl;dr",
    "what is this about", "what's this about", "what is it about",
    "give me an overview", "overview of",
)

# Belge göndergeleri. Meta sorguyu içerik sorusundan ayıran şey, fiilin
# NESNESİNİN belgenin kendisi olmasıdır ("belgeyi özetle") -- bir konu değil
# ("RAG'i özetle"). Bu yüzden özetleme yolu fiil + gönderge ister.
_DOC_REFERENTS = (
    "belge", "dokuman", "dosya", "pdf", "metin", "icerik", "yazi", "rapor",
    "document", "file", "text", "paper", "report",
)

# İşaret zamirleri tek başına gönderge sayılmaz ("bu nedir" bir içerik
# sorusudur). Yalnızca sorgu KISA ve fiil varsa yeterli kabul edilir:
# "Özetle", "Bunu özetle", "Kısaca özetle".
_SHORT_QUERY_WORDS = 4


def _contains_any(text: str, patterns) -> bool:
    return any(p in text for p in patterns)


_MIN_TOKEN_LEN = 4


def _find_target(text: str, filenames) -> Optional[str]:
    """Sorguda kastedilen belgeyi bulur.

    Kullanıcı tam dosya adını yazmaz -- "Summer School Foundry Local Plan.pdf"
    belgesini "Foundry planını özetle" diye kasteder. Bu yüzden eşleştirme
    dosya adının AYIRT EDİCİ SÖZCÜKLERİ üzerinden yapılır: en çok sözcüğü
    sorguda geçen belge kazanır.

    Sözcükler alt dize olarak aranır; Türkçe eklemeli olduğu için "plan"
    sözcüğü "planını" içinde de yakalanır. Kısa sözcükler (<4 harf) rastgele
    eşleşme üretir, elenir. _DOC_REFERENTS ("belge", "dosya", ...) de elenir --
    ÖLÇÜLDÜ: bu corpus'taki her dosya "belge_" ile başlıyor (belge_01_...,
    belge_02_...), yani "belge" hiçbir şeyi AYIRT ETMEZ; elenmezse her belge
    en az 1 puan alır ve rastgele biri "hedef" gibi görünür.

    Birden fazla belge AYNI (en yüksek) skoru paylaşıyorsa None döner --
    tahmin etmek yerine çağıran taraf kullanıcıya sorar
    (rag/answer.py::_resolve_summary_target).
    """
    candidates: list[tuple[str, int]] = []

    for name in filenames or ():
        stem = normalize(name).rsplit(".", 1)[0]

        # Tam gövde eşleşmesi en güçlü sinyal; tartışmasız kazanır.
        if len(stem) >= _MIN_TOKEN_LEN and stem in text:
            return name

        tokens = [
            t for t in stem.replace("_", " ").replace("-", " ").split()
            if len(t) >= _MIN_TOKEN_LEN and t not in _DOC_REFERENTS
        ]
        candidates.append((name, sum(1 for t in tokens if t in text)))

    if not candidates:
        return None

    best_score = max(score for _, score in candidates)
    if best_score == 0:
        return None
    winners = [name for name, score in candidates if score == best_score]
    return winners[0] if len(winners) == 1 else None


def classify(query: str, filenames=None) -> Route:
    """Sorguyu üç yoldan birine ayırır.

    filenames verilirse özetleme yolunda hedef belge adı da çözülür.
    Hiçbir desen eşleşmezse varsayılan `search`'tür -- yani yönlendirme
    mevcut davranışı yalnızca GENİŞLETİR, daraltmaz.
    """
    text = normalize(query).strip()
    if not text:
        return Route("search")

    # Özetleme deseni ÖNCE gelir. "Yüklü belgelerin tamamını özetle" hem
    # korpus deseni ("yuklu belge", listeleme sorularını yakalamak için) HEM
    # özetleme fiili ("ozetle") taşır -- ÖLÇÜLDÜ, ilk sürümde bu sıra tersti
    # ve sorgu yanlışlıkla korpus yoluna gidip belge listesi döndürüyordu,
    # özetlemiyordu. Fiil niyeti (ne yapılacak) gönderge örtüşmesinden (hangi
    # kelimeler geçiyor) daha güvenilir bir sinyal: "kaç belge yükledim" gibi
    # saf korpus sorularında hiçbir özetleme fiili YOKTUR, bu yüzden bu sıra
    # korpus sınıflandırmasını bozmaz.
    if _contains_any(text, _SUMMARIZE_PATTERNS):
        has_referent = _contains_any(text, _DOC_REFERENTS)
        is_short = len(text.split()) <= _SHORT_QUERY_WORDS
        if has_referent or is_short:
            return Route("summarize", target=_find_target(text, filenames))

    if _contains_any(text, _CORPUS_PATTERNS):
        return Route("corpus")

    return Route("search")
