"""
Ingestion hattı: belge -> sayfa -> chunk -> embedding -> SQLite.

Hem CLI'dan hem Streamlit'ten çağrılır; bu yüzden tüm iş fonksiyonlarda,
`main()` sadece CLI sarmalayıcısı.

    python -m rag.ingest --pdf Foundry_Local_Plan.pdf
    python -m rag.ingest --markdown-dir data
    python -m rag.ingest --list
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import chunking, config, models, ocr as ocr_module, pdf_loader, store

ProgressCb = Optional[Callable[[float, str], None]]


@dataclass
class IngestResult:
    filename: str
    page_count: int
    chunk_count: int
    skipped_pages: list[int]

    @property
    def has_warnings(self) -> bool:
        return bool(self.skipped_pages)

    def summary(self) -> str:
        parts = [f"{self.filename}: {self.page_count} sayfa, {self.chunk_count} chunk"]
        if self.skipped_pages:
            pages = ", ".join(str(p) for p in self.skipped_pages)
            parts.append(
                f"{len(self.skipped_pages)} sayfa okunamadı (metin katmanı yok): {pages}"
            )
        return " — ".join(parts)


def _embed_and_store(
    conn,
    filename: str,
    page_count: int,
    chunks: Sequence[chunking.Chunk],
    skipped_pages: list[int],
    progress_cb: ProgressCb,
    pdf_bytes: Optional[bytes] = None,
) -> IngestResult:
    """Chunk'ları gruplar halinde embed edip tek transaction'da veritabanına yazar."""
    if not chunks:
        raise ValueError(
            f"'{filename}' içinden hiç chunk çıkarılamadı. "
            f"Belge boş olabilir veya tüm sayfaları taranmış görüntü olabilir."
        )

    if progress_cb:
        progress_cb(0.0, f"{len(chunks)} chunk embed ediliyor...")

    # models.embed_texts kendi içinde EMBED_BATCH_SIZE'a göre gruplar, ama
    # ilerleme bildirimi için grupları burada da yürüyoruz.
    batch = config.EMBED_BATCH_SIZE
    contents = [c.content for c in chunks]
    vectors: list[list[float]] = []
    for start in range(0, len(contents), batch):
        vectors.extend(models.embed_texts(contents[start : start + batch]))
        if progress_cb:
            done = min(start + batch, len(contents))
            progress_cb(done / len(contents), f"{done}/{len(contents)} chunk embed edildi")

    store.upsert_document(conn, filename, page_count, chunks, vectors, pdf_bytes=pdf_bytes)

    if progress_cb:
        progress_cb(1.0, "Veritabanına yazıldı.")

    return IngestResult(filename, page_count, len(chunks), skipped_pages)


def ingest_pdf(
    source,
    filename: Optional[str] = None,
    conn=None,
    ocr=None,
    progress_cb: ProgressCb = None,
) -> IngestResult:
    """Tek bir PDF'i işler.

    `source` dosya yolu, bytes veya dosya benzeri nesne olabilir (Streamlit
    yükleyicisi dosya benzeri nesne verir). Dosya benzeri nesnede ad
    çıkarılamıyorsa `filename` verilmelidir.

    `ocr` varsayılan olarak otomatiktir: macOS Vision kuruluysa taranmış
    sayfalar OCR'lanır, değilse atlanıp uyarılır. Kapatmak için `ocr=False`,
    kendi motorunuzu takmak için bir çağrılabilir verin.
    """
    if ocr is None:
        ocr = ocr_module.get_hook()
    elif ocr is False:
        ocr = None
    if filename is None:
        if isinstance(source, (str, Path)):
            filename = Path(source).name
        else:
            filename = getattr(source, "name", None)
        if not filename:
            raise ValueError("filename çıkarılamadı, açıkça verin.")
    filename = Path(filename).name

    # Kaynak baytları BİR KEZ çözülür ve iki yere birden gider: metin çıkarma
    # ve saklama (§13.4). Dosya benzeri nesne iki kez okunamayacağı için
    # normalize etmek şart; ayrıca `extract_pages` de baytlarla çalışabiliyor.
    if isinstance(source, (str, Path)):
        pdf_bytes = Path(source).read_bytes()
    elif isinstance(source, (bytes, bytearray)):
        pdf_bytes = bytes(source)
    else:
        pdf_bytes = source.read()

    own_conn = conn is None
    conn = conn or store.connect()
    try:
        if progress_cb:
            progress_cb(0.0, f"{filename} okunuyor...")
        result = pdf_loader.extract_pages(pdf_bytes, ocr=ocr)
        chunks = chunking.chunk_pages(result.pages, filename)
        return _embed_and_store(
            conn,
            filename,
            result.page_count,
            chunks,
            result.skipped_pages,
            progress_cb,
            pdf_bytes=pdf_bytes,
        )
    finally:
        if own_conn:
            conn.close()


def ingest_markdown_dir(data_dir=None, conn=None, progress_cb: ProgressCb = None) -> list[IngestResult]:
    """`data/` altındaki .md fixture'larını işler. Değerlendirme setinin korpusu budur."""
    data_dir = Path(data_dir or config.PROJECT_ROOT / "data")
    paths = sorted(data_dir.glob("*.md"))
    if not paths:
        raise ValueError(f"{data_dir}/ içinde .md dosyası bulunamadı.")

    own_conn = conn is None
    conn = conn or store.connect()
    try:
        results = []
        for i, path in enumerate(paths, 1):
            text = path.read_text(encoding="utf-8")
            chunks = chunking.chunk_markdown(text, path.name)
            if progress_cb:
                progress_cb(i / len(paths), f"{path.name} işleniyor...")
            results.append(_embed_and_store(conn, path.name, 1, chunks, [], None))
        return results
    finally:
        if own_conn:
            conn.close()


# --------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Belgeleri RAG veritabanına yükler.")
    parser.add_argument("--pdf", nargs="+", metavar="DOSYA", help="işlenecek PDF dosyaları")
    parser.add_argument("--markdown-dir", nargs="?", const="data", metavar="KLASÖR",
                        help="işlenecek .md klasörü (varsayılan: data)")
    parser.add_argument("--db", metavar="YOL", help="veritabanı yolu (varsayılan: rag.db)")
    parser.add_argument("--list", action="store_true", help="yüklü belgeleri listeler")
    parser.add_argument("--delete", metavar="DOSYA_ADI", help="bir belgeyi siler")
    args = parser.parse_args(argv)

    conn = store.connect(args.db)
    try:
        if args.list:
            docs = store.list_documents(conn)
            if not docs:
                print("Veritabanı boş.")
            for d in docs:
                print(f"  {d['filename']:45s} {d['page_count']:4d} sayfa "
                      f"{d['chunk_count']:5d} chunk  {d['ingested_at']}")
            return 0

        if args.delete:
            ok = store.delete_document(conn, args.delete)
            print(f"'{args.delete}' {'silindi' if ok else 'bulunamadı'}.")
            return 0 if ok else 1

        if not args.pdf and not args.markdown_dir:
            parser.error("--pdf, --markdown-dir, --list veya --delete verin.")

        def progress(pct, msg):
            print(f"\r  {pct * 100:5.1f}%  {msg:<55}", end="", flush=True)

        if args.pdf:
            for path in args.pdf:
                print(f"\n=== {path} ===")
                result = ingest_pdf(path, conn=conn, progress_cb=progress)
                print(f"\n  {result.summary()}")

        if args.markdown_dir:
            print(f"\n=== {args.markdown_dir}/ ===")
            for result in ingest_markdown_dir(args.markdown_dir, conn=conn, progress_cb=progress):
                print(f"\n  {result.summary()}")

        matrix, _ = store.load_matrix(conn)
        print(f"\n\nVeritabanı toplamı: {matrix.shape[0]} chunk, vektör boyutu {matrix.shape[1]}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
