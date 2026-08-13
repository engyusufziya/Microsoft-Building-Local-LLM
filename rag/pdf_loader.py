"""
PDF metin çıkarma katmanı.

Sorumluluğu tek şey: bir PDF'i sayfa sayfa okunabilir düz metne çevirmek.
Chunk'lama, embedding ve veritabanı bu modülün işi değildir.

Girdi olarak dosya yolu, dosya benzeri nesne (Streamlit `st.file_uploader`
böyle bir nesne verir) veya ham `bytes` kabul edilir.

Hızlı deneme:
    python -m rag.pdf_loader Foundry_Local_Plan.pdf
"""

from __future__ import annotations

import io
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from pypdf import PdfReader

from . import config

__all__ = ["Page", "ExtractResult", "PdfLoadError", "extract_pages", "normalize_text"]


class PdfLoadError(RuntimeError):
    """PDF açılamadığında/okunamadığında atılır. Arayüz bu hatayı yakalayıp gösterir."""


@dataclass
class Page:
    """Tek bir PDF sayfasının temizlenmiş metni."""

    number: int  # 1-tabanlı sayfa numarası (kaynak atıfında "s.4" diye kullanılır)
    text: str
    via_ocr: bool = False


@dataclass
class ExtractResult:
    """`extract_pages` çıktısı."""

    pages: list[Page] = field(default_factory=list)  # sadece kullanılabilir metni olanlar
    skipped_pages: list[int] = field(default_factory=list)  # metni boş/çok kısa olanlar
    page_count: int = 0  # PDF'teki toplam sayfa sayısı


# --------------------------------------------------------------------------- metin temizliği

# Görünmez / metni kirleten karakterler. Yumuşak tire ve sıfır genişlikli
# karakterler tamamen silinir; egzotik boşluk türleri normal boşluğa çevrilir.
_INVISIBLE = dict.fromkeys(
    map(ord, "\u00ad\u200b\u200c\u200d\ufeff"), None
)
_ODD_SPACE = re.compile("[\u00a0\u2000-\u200a\u202f\u205f\u3000]")

# Satır sonunda tireyle bölünmüş kelime: "geliş-\ntirme".
# İki yanındaki parçaların tamamını yakalarız, çünkü karar vermek için
# kelimenin bütününü görmemiz gerekir.
_HYPHEN_BREAK = re.compile(
    "(?P<before>\\S*?[^\\W\\d_])[-\u2010\u2011][ \\t]*\\n[ \\t]*(?P<after>[^\\W\\d_]\\S*)"
)

# Kelime dağarcığı çıkarırken tokenları kırpmak için.
_TOKEN_TRIM = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)

# Uzun bağlantılar satır sonunda tiresiz bölünür ("...azuredevco\nmmunityblog...").
# Devam parçasında URL'e özgü bir karakter (/ ? # = & %) aranır; düz metin
# kelimelerinde bunlar bulunmadığı için "example.com\nfor detay" yanlışlıkla
# birleştirilmez.
_URL_BREAK = re.compile(r"((?:https?://|www\.)\S*)\n(\S*[/?#=&%]\S*)")

# Madde işaretleri: bunlarla başlayan satırlar ayrı paragraf sayılır.
_BULLET_LINE = re.compile(r"\n(?=[•‣▪◦·⁃∙]\s)")

_PARAGRAPH_MARK = "\x00"


def _vocabulary(raw_text: str) -> tuple[set[str], set[str]]:
    """Belgenin tamamından iki sözlük çıkarır: bitişik kelimeler ve tireli birleşikler.

    Satır sonu tiresiyle bölünmüş parçalar ("on-" / "device") sözlüğe girmemeli,
    yoksa kendi kararımızı kendimiz doğrulamış oluruz; bu yüzden önce silinirler.
    """
    scrubbed = _HYPHEN_BREAK.sub(" ", raw_text)

    plain: set[str] = set()
    hyphenated: set[str] = set()
    for token in scrubbed.split():
        token = _TOKEN_TRIM.sub("", token).lower()
        if not token:
            continue
        if "-" in token:
            hyphenated.add(token)
            # Birleşiğin parçaları da gerçek kelime sayılır: "high-level" görüldüyse
            # "level" tek başına hiç geçmese bile anlamlı bir kelimedir.
            plain.update(part for part in token.split("-") if part)
        else:
            plain.add(token)
    return plain, hyphenated


def _join_hyphen_break(match: "re.Match[str]", plain: set[str], hyphenated: set[str]) -> str:
    """Satır sonundaki tirenin gerçek tire mi yoksa hecelemeden mi geldiğine karar verir.

    Körü körüne tire silmek "on-device" -> "ondevice" gibi bozulmalar üretir;
    körü körüne korumak da "geliş-tirme" bırakır. Bu yüzden belgenin geri kalanına
    bakıp kanıt toplarız.
    """
    before = match.group("before")
    after = match.group("after")

    left = _TOKEN_TRIM.sub("", before).lower()
    right = _TOKEN_TRIM.sub("", after).lower()

    # 1) URL / zaten tireli parçalar: dokunma, sadece satır sonunu kaldır.
    #    (Kelime sonundaki nokta gibi noktalama sayılmaz, o yüzden kırpılmış
    #    hallere bakarız.)
    if any(ch in left + right for ch in "-/:.@_"):
        return f"{before}-{after}"

    # 2) Bitişik hali belgenin başka yerinde geçiyorsa hecelemedir -> birleştir.
    if f"{left}{right}" in plain:
        return f"{before}{after}"

    # 3) Tireli hali başka yerde geçiyorsa gerçek tiredir -> koru.
    if f"{left}-{right}" in hyphenated:
        return f"{before}-{after}"

    # 4) Sağdaki parça tek başına geçen anlamlı bir kelimeyse gerçek birleşiktir.
    #    Ayırt edici olan sağ parçadır: hecelemede sağda kelime kalıntısı olur
    #    ("geliş-tirme" -> "tirme" belgede geçmez), gerçek birleşikte ise tam
    #    kelime durur ("passage-level" -> "level", "on-device" -> "device").
    if right in plain:
        return f"{before}-{after}"

    # 5) Soldaki parça kısaltmaysa ("OS-specific") tire gerçektir.
    if len(left) >= 2 and before.isupper():
        return f"{before}-{after}"

    # 6) Varsayılan: satır sonu hecelemesi.
    return f"{before}{after}"


def normalize_text(text: str, vocabulary: Optional[tuple[set[str], set[str]]] = None) -> str:
    """PDF'ten gelen ham metni okunabilir hale getirir.

    - Tireyle bölünmüş kelimeleri birleştirir ("geliş-\\ntirme" -> "geliştirme")
    - Tek satır sonlarını boşluğa çevirir, paragraf aralarını (çift satır sonu) korur
    - Tekrarlayan boşlukları sadeleştirir, görünmez karakterleri atar

    Türkçe karakterler korunur: NFKD gibi ayrıştırıcı bir normalizasyon
    KULLANILMAZ, sadece NFC ile birleştirme yapılır.

    `vocabulary` verilirse tire kararları belgenin tamamına bakarak alınır;
    verilmezse sadece bu metin parçasına bakılır.
    """
    if not text:
        return ""

    # NFC güvenlidir: "ğ" gibi harfleri bozmaz, aksine ayrık gelmişse birleştirir.
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_INVISIBLE)
    text = _ODD_SPACE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Satır başı/sonundaki boşluklar paragraf tespitini bozar, önce temizlenir.
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

    # Bölünmüş bağlantılar tireden önce onarılır; bir URL birden fazla satıra
    # yayılmış olabileceği için değişiklik durana kadar tekrarlanır.
    for _ in range(4):
        text, changed = _URL_BREAK.subn(r"\1\2", text)
        if not changed:
            break

    plain, hyphenated = vocabulary if vocabulary is not None else _vocabulary(text)
    text = _HYPHEN_BREAK.sub(lambda m: _join_hyphen_break(m, plain, hyphenated), text)

    # Madde işaretli satırlar kendi paragrafları olsun ki liste yapısı kaybolmasın.
    text = _BULLET_LINE.sub("\n\n", text)

    # Paragraf sınırlarını işaretle, kalan tek satır sonlarını boşluğa çevir, geri koy.
    text = re.sub(r"\n{2,}", _PARAGRAPH_MARK, text)
    text = text.replace("\n", " ")
    text = text.replace(_PARAGRAPH_MARK, "\n\n")

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _word_count(text: str) -> int:
    return len(text.split())


# --------------------------------------------------------------------------- okuma

def _to_reader(source: Union[str, Path, bytes, bytearray, object]) -> PdfReader:
    """Yol / dosya benzeri nesne / bytes -> PdfReader."""
    stream: object

    if isinstance(source, (bytes, bytearray)):
        stream = io.BytesIO(bytes(source))
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise PdfLoadError(f"PDF bulunamadı: {path}")
        stream = path
    elif hasattr(source, "read"):
        # Streamlit UploadedFile ve benzerleri. Daha önce okunmuş olabilir,
        # başa sarmayı deneriz; bellek içi kopya alarak tekrar okunabilir kılarız.
        try:
            source.seek(0)  # type: ignore[attr-defined]
        except Exception:
            pass
        data = source.read()  # type: ignore[attr-defined]
        if isinstance(data, str):
            raise PdfLoadError(
                "PDF metin modunda açılmış. Dosyayı ikili modda ('rb') açın."
            )
        if not data:
            raise PdfLoadError("Yüklenen dosya boş.")
        stream = io.BytesIO(data)
    else:
        raise PdfLoadError(
            f"Desteklenmeyen kaynak türü: {type(source).__name__}. "
            f"Dosya yolu, dosya benzeri nesne veya bytes bekleniyor."
        )

    try:
        reader = PdfReader(stream)
    except Exception as exc:
        raise PdfLoadError(
            f"PDF açılamadı; dosya bozuk veya geçerli bir PDF değil. Ayrıntı: {exc}"
        ) from exc

    if reader.is_encrypted:
        # Bazı PDF'ler boş parolayla korunur; bunları açabiliriz.
        try:
            opened = reader.decrypt("")
        except Exception:
            opened = 0
        if not opened:
            raise PdfLoadError(
                "PDF parola korumalı. Lütfen parolasız bir kopyasını yükleyin."
            )

    return reader


def _raw_pages(reader: PdfReader) -> list[str]:
    """Her sayfanın ham metnini döndürür; okunamayan sayfa boş string olur."""
    texts: list[str] = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            # Tek bir bozuk sayfa yüzünden tüm belgeyi reddetmeyiz;
            # metni boş sayılır ve OCR'a/atlananlara düşer.
            texts.append("")
    return texts


def extract_pages(
    source: Union[str, Path, bytes, bytearray, object],
    ocr: Optional[Callable[[object], str]] = None,
) -> ExtractResult:
    """PDF'i sayfa sayfa okur ve temizlenmiş metni döndürür.

    Args:
        source: Dosya yolu, dosya benzeri nesne veya `bytes`.
        ocr: Metin katmanı yetersiz sayfalar için kanca (Faz 1.5'te takılacak).
            pypdf sayfa nesnesini alır ve metin döndürür; 0-tabanlı sayfa indeksi
            `page.page_number` üzerinden okunabilir. `None` ise böyle sayfalar
            `skipped_pages` listesine yazılır.

    Raises:
        PdfLoadError: Dosya açılamazsa, bozuksa veya parola korumalıysa.
    """
    reader = _to_reader(source)
    raw_texts = _raw_pages(reader)

    if not raw_texts:
        raise PdfLoadError("PDF hiç sayfa içermiyor.")

    # Tire kararları için sözlük belgenin TAMAMINDAN çıkarılır: bir kelimenin
    # bitişik hali çoğu zaman başka bir sayfada geçer.
    vocabulary = _vocabulary("\n".join(raw_texts))

    result = ExtractResult(page_count=len(raw_texts))

    for index, raw in enumerate(raw_texts):
        number = index + 1
        text = normalize_text(raw, vocabulary)

        if _word_count(text) >= config.MIN_WORDS_PER_PAGE:
            result.pages.append(Page(number=number, text=text))
            continue

        # Metin katmanı yok/yetersiz: taranmış sayfa olabilir.
        if ocr is None:
            result.skipped_pages.append(number)
            continue

        try:
            ocr_text = normalize_text(ocr(reader.pages[index]) or "")
        except Exception as exc:
            print(f"  [uyarı] s.{number} OCR başarısız: {exc}", file=sys.stderr)
            ocr_text = ""

        if _word_count(ocr_text) >= config.MIN_WORDS_PER_PAGE:
            result.pages.append(Page(number=number, text=ocr_text, via_ocr=True))
        else:
            result.skipped_pages.append(number)

    return result


# --------------------------------------------------------------------------- elle deneme

def _demo(paths: Iterable[str]) -> int:
    for path in paths:
        try:
            result = extract_pages(path)
        except PdfLoadError as exc:
            print(f"{path}: HATA - {exc}")
            return 1
        print(f"\n=== {path} ===")
        print(f"  toplam sayfa : {result.page_count}")
        print(f"  metni olan   : {len(result.pages)}")
        print(f"  atlanan      : {result.skipped_pages or '-'}")
        if result.pages:
            first = result.pages[0]
            print(f"  s.{first.number} ilk 300 karakter:\n{first.text[:300]}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(_demo(sys.argv[1:]))
    print(__doc__)
