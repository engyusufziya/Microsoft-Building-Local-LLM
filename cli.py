"""
Komut satırı arayüzü — offline belge asistanı.

    python cli.py                    # etkileşimli soru-cevap
    python cli.py --show-chunks      # getirilen bağlamı da göster
    python cli.py "RAG nedir?"       # tek soru sor ve çık
"""

from __future__ import annotations

import argparse
import sys

from rag import answer, config, store


def _print_answer(result, show_chunks: bool) -> None:
    if show_chunks:
        if result.hits:
            print("\n  --- getirilen bağlam ---")
            for hit in result.hits:
                flag = " [OCR]" if hit.via_ocr else ""
                print(f"  {hit.score:.4f}  {hit.citation()}{flag}")
                print(f"          {hit.content[:120]}...")
        else:
            print("\n  --- eşiği geçen bağlam yok ---")
    print(f"\n{result.formatted()}\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline belge Q&A asistanı.")
    parser.add_argument("question", nargs="*", help="tek seferlik soru")
    parser.add_argument("--show-chunks", action="store_true",
                        help="getirilen chunk'ları ve skorlarını göster")
    parser.add_argument("--model", help=f"chat modeli (varsayılan: {config.CHAT_MODEL})")
    parser.add_argument("--db", help="veritabanı yolu")
    args = parser.parse_args(argv)

    conn = store.connect(args.db)
    try:
        docs = store.list_documents(conn)
        if not docs:
            print("Veritabanı boş. Önce belge yükleyin:")
            print("  python -m rag.ingest --pdf dosya.pdf")
            return 1

        def ask(q):
            return answer.answer_query(q, model=args.model, conn=conn)

        if args.question:
            _print_answer(ask(" ".join(args.question)), args.show_chunks)
            return 0

        total = sum(d["chunk_count"] for d in docs)
        print(f"Yüklü belgeler ({len(docs)} belge, {total} chunk):")
        for d in docs:
            print(f"  - {d['filename']} ({d['chunk_count']} chunk)")
        print(f"\nModel: {args.model or config.CHAT_MODEL}")
        print("Çıkmak için 'q' veya Ctrl-D.\n")

        while True:
            try:
                q = input("Soru> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if q.lower() in {"q", "quit", "exit", "çık"}:
                return 0
            if not q:
                continue
            _print_answer(ask(q), args.show_chunks)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
