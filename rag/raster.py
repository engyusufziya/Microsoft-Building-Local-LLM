"""PDF sayfasını görüntüye çevirir — sayfa görüntülü alıntı (FEATURE_SPEC §13.4).

Rasterleyici `pypdfium2`. Spec'in ilk adayı PyMuPDF'ti ve **lisans** nedeniyle
reddedildi (AGPL-3.0 vs bu deponun MIT'i); gerekçe `requirements.txt`'te.
PDFium wheel'in içinde gömülü gelir: sistem `poppler` yok, ağ yok (§1.2).

Bu modül SAF: veritabanı görmez, HTTP görmez. Girdisi PDF baytları, çıktısı
görüntü baytları.
"""

from __future__ import annotations

import io

import pypdfium2 as pdfium

from . import config


class PageOutOfRange(LookupError):
    """İstenen sayfa belgede yok. Çağıran taraf bunu 404'e çevirir."""


def render_page(pdf_bytes: bytes, page: int) -> bytes:
    """`page` (1'den başlar) sayfasını `PAGE_IMAGE_FORMAT` baytları olarak döndürür.

    Sayfa aralık dışındaysa `PageOutOfRange` atar. Bozuk PDF `pypdfium2`'nin
    kendi `PdfiumError`'ını atar; çağıran taraf onu yakalar.
    """
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        if page < 1 or page > len(document):
            raise PageOutOfRange(f"sayfa {page} yok (belge {len(document)} sayfa)")

        image = document[page - 1].render(scale=config.PAGE_IMAGE_SCALE).to_pil()
        buffer = io.BytesIO()
        # WebP alfa kanalını taşıyabilir ama sayfa zemini zaten opak; RGB'ye
        # düşürmek baytları küçültüyor ve renk yönetimini basitleştiriyor.
        image.convert("RGB").save(
            buffer, config.PAGE_IMAGE_FORMAT, quality=config.PAGE_IMAGE_QUALITY
        )
        return buffer.getvalue()
    finally:
        document.close()


def media_type() -> str:
    """`PAGE_IMAGE_FORMAT` için HTTP içerik tipi."""
    return f"image/{config.PAGE_IMAGE_FORMAT.lower()}"
