"""
OCR yedek yolu — metin katmanı olmayan (taranmış) PDF sayfaları için.

macOS Vision framework kullanılır: Neural Engine'de çalışır, ek model indirmesi
gerektirmez, ağa çıkmaz. Türkçe desteği çalışma anında doğrulanır, varsayılmaz.

Neden VLM değil: Foundry Local katalogundaki görüntü alabilen modeller
(qwen3-vl-*) yalnızca CPU varyantına sahip ve sayfa başına on saniyeler alıyor.
Daha önemlisi bir VLM metni okumaz, ÜRETİR -- okuyamadığı kelimeyi makul
görünen başkasıyla doldurabilir. RAG korpusunda bu, kaynağa sadakati tam da
alıntı yapılan cümlede sessizce bozar.

Görüntüler pypdf'in `page.images`'ı ile alınır; ek bağımlılık gerektirmez.
Taranmış bir sayfa tipik olarak tek büyük JPEG'dir. Vektörle çizilmiş
şemalardaki metin bu yolla yakalanmaz (sayfa rasterizasyonu gerekirdi).

    python -m rag.ocr belge.pdf        # sayfaları OCR'layıp yazdırır
    python -m rag.ocr --check          # Türkçe desteğini doğrular
"""

from __future__ import annotations

import sys
from typing import Optional

# Vision isteğe bağlı bağımlılık: kurulu değilse ingest OCR'sız çalışmaya
# devam eder, sadece taranmış sayfalar atlanır.
try:
    import Quartz
    import Vision
    from Foundation import NSData

    _AVAILABLE = True
except ImportError:  # pragma: no cover
    _AVAILABLE = False

LANGUAGES = ["tr-TR", "en-US"]


def is_available() -> bool:
    """Vision kurulu ve kullanılabilir mi."""
    return _AVAILABLE


def supported_languages() -> list[str]:
    if not _AVAILABLE:
        return []
    request = Vision.VNRecognizeTextRequest.alloc().init()
    langs, _ = request.supportedRecognitionLanguagesAndReturnError_(None)
    return list(langs or [])


def recognize_image(data: bytes) -> str:
    """Tek bir görüntüden metni çıkarır. Başarısızlıkta boş string döner."""
    if not _AVAILABLE:
        return ""

    ns_data = NSData.dataWithBytes_length_(data, len(data))
    source = Quartz.CGImageSourceCreateWithData(ns_data, None)
    if source is None or Quartz.CGImageSourceGetCount(source) == 0:
        return ""
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if image is None:
        return ""

    request = Vision.VNRecognizeTextRequest.alloc().init()
    # accurate: hızdan ödün verip doğruluk seçilir. OCR metni zaten daha az
    # güvenilir; burada hız için kalite feda etmenin anlamı yok.
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(LANGUAGES)
    request.setUsesLanguageCorrection_(True)

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, _ = handler.performRequests_error_([request], None)
    if not ok:
        return ""

    lines = []
    for observation in request.results() or []:
        candidate = observation.topCandidates_(1)
        if candidate and len(candidate):
            lines.append(str(candidate[0].string()))
    return "\n".join(lines)


def ocr_page(page) -> str:
    """`pdf_loader.extract_pages(ocr=...)` kancası.

    pypdf sayfa nesnesindeki gömülü görüntüleri sırayla OCR'lar ve birleştirir.
    """
    if not _AVAILABLE:
        return ""

    parts = []
    try:
        images = list(page.images)
    except Exception:
        return ""

    for image in images:
        try:
            text = recognize_image(image.data)
        except Exception:
            continue
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def get_hook() -> Optional[callable]:
    """Vision varsa OCR kancasını, yoksa None döndürür.

    Çağıran taraf (ingest) bunu doğrudan `extract_pages(ocr=...)`'a geçirebilir.
    """
    return ocr_page if _AVAILABLE else None


# --------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if not _AVAILABLE:
        print("Vision kurulu değil. Kurmak için: pip install pyobjc-framework-Vision")
        return 1

    if not argv or "--check" in argv:
        langs = supported_languages()
        print(f"Vision kullanılabilir. Desteklenen dil sayısı: {len(langs)}")
        for lang in LANGUAGES:
            mark = "+" if lang in langs else "-"
            print(f"  [{mark}] {lang}")
        missing = [l for l in LANGUAGES if l not in langs]
        if missing:
            print(f"UYARI: {missing} desteklenmiyor, o diller İngilizce olarak okunur.")
        return 0

    from pypdf import PdfReader

    for path in argv:
        reader = PdfReader(path)
        print(f"=== {path}: {len(reader.pages)} sayfa ===")
        for i, page in enumerate(reader.pages, 1):
            text = ocr_page(page)
            n_img = len(list(page.images)) if hasattr(page, "images") else 0
            print(f"  s.{i}: {n_img} görüntü, OCR {len(text.split())} kelime")
            if text.strip():
                print(f"      {text[:200].replace(chr(10), ' ')}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
