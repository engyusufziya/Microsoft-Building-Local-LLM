"""
Metni embedding'e hazır parçalara (chunk) böler.

İki giriş noktası var:
  - `chunk_pages`  : PDF sayfaları için kelime penceresi (overlap'li)
  - `chunk_markdown`: data/*.md fixture'ları için paragraf bazlı bölme

Her chunk TEK bir sayfaya aittir; chunk'lar sayfa sınırını aşmaz. Buna
cevap üretirken "s.4" şeklinde kaynak atıfı verebilmek için ihtiyacımız var.

Hızlı deneme:
    python -m rag.chunking Foundry_Local_Plan.pdf
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from . import config
from .pdf_loader import Page

__all__ = ["Chunk", "chunk_pages", "chunk_markdown"]

# Son pencerenin bir öncekine göre getirdiği YENİ kelime sayısı bu eşiğin
# altındaysa ayrı chunk üretmeye değmez: içeriğinin neredeyse tamamı zaten
# önceki chunk'ta vardır, ayrı tutmak top-k'da bir yeri boşuna işgal eder.
# Bu yüzden son pencere öncekine katılır (~25 kelime mertebesi). Eşik ayrı bir
# ayar değil, config'teki overlap'ten türetilir.
_MIN_TAIL_WORDS = config.CHUNK_OVERLAP_WORDS

# Markdown başlık satırı: "## Başlık" (sondaki kapanış #'leri isteğe bağlı).
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")


@dataclass
class Chunk:
    """Veritabanına yazılacak tek bir metin parçası."""

    source: str  # dosya adı (kaynak atıfında gösterilir)
    page: int  # 1-tabanlı sayfa; markdown fixture'larında 0
    content: str
    via_ocr: bool = False


# --------------------------------------------------------------------------- pencereleme

def _windows(total: int, size: Optional[int] = None) -> List[Tuple[int, int]]:
    """`total` kelimelik bir dizi için (başlangıç, bitiş) pencerelerini üretir.

    Pencere boyu `size` (varsayılan CHUNK_WORDS), adım
    `size - CHUNK_OVERLAP_WORDS`'tür; yani ardışık iki pencere
    CHUNK_OVERLAP_WORDS kelime örtüşür. Yalnızca son pencere, kısa artığı
    yutmak için `size`'ı aşabilir.
    """
    if total <= 0:
        return []

    size = size or config.CHUNK_WORDS
    step = max(1, size - config.CHUNK_OVERLAP_WORDS)

    spans: List[Tuple[int, int]] = []
    start = 0
    while start < total:
        end = min(start + size, total)
        spans.append((start, end))
        if end >= total:
            break
        start += step

    # Son pencere yeterince yeni içerik getirmiyorsa öncekine katılır.
    if len(spans) > 1 and total - spans[-2][1] <= _MIN_TAIL_WORDS:
        spans[-2] = (spans[-2][0], total)
        spans.pop()

    return spans


def _split_words(words: Sequence[str], size: Optional[int] = None) -> List[str]:
    """Kelime listesini overlap'li metin parçalarına böler."""
    return [" ".join(words[start:end]) for start, end in _windows(len(words), size)]


# --------------------------------------------------------------------------- PDF

def chunk_pages(pages: Iterable[Page], source: str) -> List[Chunk]:
    """PDF sayfalarını chunk'lara böler.

    Args:
        pages: `pdf_loader.extract_pages(...).pages`
        source: Kaynak dosya adı (ör. "Foundry_Local_Plan.pdf").

    Bölme her sayfa için ayrı yapılır; bir chunk asla iki sayfadan metin
    içermez, böylece sayfa atıfı her zaman doğrudur.
    """
    chunks: List[Chunk] = []
    for page in pages:
        words = page.text.split()
        for piece in _split_words(words):
            if piece.strip():
                chunks.append(
                    Chunk(
                        source=source,
                        page=page.number,
                        content=piece,
                        via_ocr=page.via_ocr,
                    )
                )
    return chunks


# --------------------------------------------------------------------------- Markdown

def _heading_prefix(stack: Sequence[Tuple[int, str]]) -> str:
    """Açık başlıkları "Üst > Alt" biçiminde birleştirir."""
    return " > ".join(title for _, title in stack)


def chunk_markdown(text: str, source: str, max_words: Optional[int] = None) -> List[Chunk]:
    """Markdown fixture'ını paragraf sınırlarında chunk'lara böler.

    Kök dizindeki `ingest.py` içindeki `chunk_text()` mantığını temel alır:
    ardışık paragraflar `max_words` sınırını aşmayacak şekilde gruplanır.
    Fark: başlık atılmaz, chunk'ın başına önek olarak eklenir. Başlık
    anlamsal sinyal taşır ve embedding'e katkı verir.

    `max_words` varsayılanı MARKDOWN_CHUNK_WORDS'tür (PDF'ten daha küçük):
    fixture belgeleri kısa olduğundan CHUNK_WORDS ile her belge tek chunk'a
    düşer ve retrieval ölçülemez hale gelir.

    Sayfa kavramı olmadığı için page=0 kullanılır.
    """
    max_words = max_words or config.MARKDOWN_CHUNK_WORDS
    chunks: List[Chunk] = []
    stack: List[Tuple[int, str]] = []  # (seviye, başlık)
    buffer: List[str] = []
    buffer_words = 0

    def emit(body: str, prefix: str) -> None:
        body = body.strip()
        if not body:
            return
        content = f"{prefix}\n\n{body}" if prefix else body
        chunks.append(Chunk(source=source, page=0, content=content))

    def flush(prefix: str) -> None:
        nonlocal buffer, buffer_words
        if not buffer:
            return
        body = "\n\n".join(buffer)

        # Kısa artık: aynı başlık altındaki bir önceki chunk'a kat.
        if (
            len(body.split()) <= _MIN_TAIL_WORDS
            and chunks
            and chunks[-1].content.startswith(prefix)
        ):
            chunks[-1].content += "\n\n" + body
        else:
            emit(body, prefix)

        buffer = []
        buffer_words = 0

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    for para in paragraphs:
        heading = _HEADING.match(para)
        if heading:
            # Başlık değişiyor: biriken metni mevcut başlıkla kapat.
            flush(_heading_prefix(stack))
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2).strip()))
            continue

        prefix = _heading_prefix(stack)
        words = para.split()

        # Tek başına sınırı aşan paragraf: kelime penceresiyle bölünür.
        if len(words) > max_words:
            flush(prefix)
            for piece in _split_words(words, max_words):
                emit(piece, prefix)
            continue

        if buffer and buffer_words + len(words) > max_words:
            flush(prefix)

        buffer.append(para)
        buffer_words += len(words)

    flush(_heading_prefix(stack))
    return chunks


# --------------------------------------------------------------------------- elle deneme

def _demo(paths: Iterable[str]) -> int:
    from .pdf_loader import PdfLoadError, extract_pages

    for raw_path in paths:
        path = Path(raw_path)
        if path.suffix.lower() == ".md":
            produced = chunk_markdown(path.read_text(encoding="utf-8"), path.name)
        else:
            try:
                result = extract_pages(path)
            except PdfLoadError as exc:
                print(f"{path}: HATA - {exc}")
                return 1
            produced = chunk_pages(result.pages, path.name)

        print(f"\n=== {path.name}: {len(produced)} chunk ===")
        for chunk in produced[:2]:
            print(f"  [s.{chunk.page}] {chunk.content[:160]}...")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(_demo(sys.argv[1:]))
    print(__doc__)
