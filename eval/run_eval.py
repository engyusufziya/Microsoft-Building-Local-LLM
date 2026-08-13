"""
Değerlendirme harness'i: eval_set.json'daki 15 soruyu çalıştırıp ölçer.

Ölçülenler:
  - retrieval isabeti : beklenen kaynak belge top-k içinde mi (answerable)
  - anahtar kelime    : cevapta beklenen terimler geçiyor mu (answerable)
  - reddetme          : cevaplanamaz sorularda "bilmiyorum" dönüyor mu
  - süre              : soru başına saniye

Eval korpusu data/*.md fixture'larıdır ve DEMO veritabanından ayrı tutulur,
böylece kullanıcının yüklediği PDF'ler sonuçları etkilemez.

    python eval/run_eval.py --ingest          # eval.db'yi fixture'lardan kur
    python eval/run_eval.py
    python eval/run_eval.py --model phi-4-mini
    python eval/run_eval.py --sweep-threshold # MIN_SCORE taraması (LLM çağırmaz)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import answer, config, ingest, retrieve, store  # noqa: E402

EVAL_DB = Path(__file__).resolve().parent / "eval.db"
EVAL_SET = Path(__file__).resolve().parent / "eval_set.json"


def load_questions() -> list[dict]:
    return json.loads(EVAL_SET.read_text(encoding="utf-8"))["questions"]


def keyword_hit(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    """Anahtar kelimeler ayırt edici kökler; küçük/büyük harf duyarsız substring eşleşmesi.

    (Eval setini yazan not: tam eşitlik aramak yanlış negatif üretir --
    belgelerde sayılar yazıyla geçiyor, "1'e yaklaş" gibi kökler var.)
    """
    low = text.lower()
    missing = [k for k in keywords if k.lower() not in low]
    return len(keywords) - len(missing), missing


def refused(text: str) -> bool:
    return config.NO_ANSWER_TEXT.rstrip(".").lower() in text.lower()


def run(model: str | None, conn, min_score: float | None) -> int:
    questions = load_questions()
    rows, failures = [], []
    t_start = time.time()

    for q in questions:
        t0 = time.time()
        result = answer.answer_query(q["question"], model=model,
                                     min_score=min_score, conn=conn)
        dt = time.time() - t0
        cat = q["category"]
        ok, detail = True, ""

        if cat == "answerable":
            hits = retrieve.get_top_chunks(q["question"], min_score=min_score, conn=conn)
            sources = {h.source for h in hits}
            found = q["expected_source"] in sources
            n_kw, missing = keyword_hit(result.text, q["expected_keywords"])
            ok = found and not refused(result.text)
            detail = f"kaynak={'+' if found else '-'} kelime={n_kw}/{len(q['expected_keywords'])}"
            if missing:
                detail += f" eksik={missing}"
        elif cat == "unanswerable":
            ok = refused(result.text)
            detail = "reddetti" if ok else "REDDETMEDİ"
        else:  # edge_case
            ok = refused(result.text) or len(result.text.split()) < 60
            detail = f"{len(result.text.split())} kelime"

        rows.append((q["id"], cat, ok, dt, detail))
        if not ok:
            failures.append((q["id"], q["question"], result.text[:160], detail))

        print(f"  {'PASS' if ok else 'FAIL'}  {q['id']}  {cat:12s} {dt:5.1f}sn  {detail}")

    total = time.time() - t_start
    by_cat: dict[str, list[bool]] = {}
    for _, cat, ok, _, _ in rows:
        by_cat.setdefault(cat, []).append(ok)

    print(f"\n  {'-' * 60}")
    for cat, oks in by_cat.items():
        print(f"  {cat:14s} {sum(oks)}/{len(oks)}")
    passed = sum(ok for _, _, ok, _, _ in rows)
    print(f"  {'TOPLAM':14s} {passed}/{len(rows)}")
    print(f"  süre: toplam {total:.0f}sn, ortalama {total / len(rows):.1f}sn/soru")

    if failures:
        print(f"\n  --- başarısızlar ---")
        for qid, question, text, detail in failures:
            print(f"  {qid} ({detail})\n    S: {question}\n    C: {text}\n")

    return 0 if passed == len(rows) else 1


def sweep_threshold(conn) -> int:
    """MIN_SCORE'u taramak için: her soru için en yüksek skoru ölçer, LLM çağırmaz.

    Amaç, cevabı olan sorularla olmayanların skor aralıklarını görüp eşiği
    aradaki boşluğa koymak.
    """
    questions = load_questions()
    answerable, other = [], []

    for q in questions:
        if not q["question"].strip():
            continue
        hits = retrieve.get_top_chunks(q["question"], min_score=None, conn=conn)
        top = hits[0].score if hits else 0.0
        correct = (q["category"] == "answerable"
                   and any(h.source == q["expected_source"] for h in hits))
        (answerable if q["category"] == "answerable" else other).append((q["id"], top, correct))
        mark = "+" if q["category"] == "answerable" else "-"
        print(f"  [{mark}] {q['id']}  en yüksek={top:.4f}  "
              f"{'kaynak bulundu' if correct else ''}")

    a_scores = [s for _, s, _ in answerable]
    o_scores = [s for _, s, _ in other]
    print(f"\n  cevaplanabilir  : min={min(a_scores):.4f}  max={max(a_scores):.4f}")
    print(f"  diğer           : min={min(o_scores):.4f}  max={max(o_scores):.4f}")

    print(f"\n  {'eşik':>6}  {'geçen answerable':>17}  {'geçen diğer':>12}")
    for thr in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]:
        a = sum(1 for s in a_scores if s >= thr)
        o = sum(1 for s in o_scores if s >= thr)
        star = "  <-- şu anki" if abs(thr - config.MIN_SCORE) < 1e-9 else ""
        print(f"  {thr:6.2f}  {a:>10}/{len(a_scores)}  {o:>10}/{len(o_scores)}{star}")
    print("\n  Not: 'diğer' grubunun geçmesi kötü değil -- konu yakın sorularda")
    print("  reddetme kararını LLM verir. Eşiğin işi konu DIŞI soruları elemek.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RAG değerlendirme harness'i")
    parser.add_argument("--model", help=f"chat modeli (varsayılan: {config.CHAT_MODEL})")
    parser.add_argument("--ingest", action="store_true",
                        help="eval.db'yi data/*.md fixture'larından yeniden kur")
    parser.add_argument("--sweep-threshold", action="store_true",
                        help="MIN_SCORE taraması (LLM çağırmaz, hızlı)")
    parser.add_argument("--min-score", type=float, help="bu çalıştırma için eşiği geçersiz kıl")
    args = parser.parse_args(argv)

    if args.ingest or not EVAL_DB.exists():
        print(f"=== eval.db kuruluyor (data/*.md) ===")
        conn = store.connect(EVAL_DB)
        try:
            for r in ingest.ingest_markdown_dir(conn=conn):
                print(f"  {r.summary()}")
        finally:
            conn.close()
        print()

    conn = store.connect(EVAL_DB)
    try:
        matrix, _ = store.load_matrix(conn)
        print(f"=== eval korpusu: {matrix.shape[0]} chunk ===\n")
        if args.sweep_threshold:
            return sweep_threshold(conn)
        print(f"=== model: {args.model or config.CHAT_MODEL}, "
              f"eşik: {args.min_score if args.min_score is not None else config.MIN_SCORE} ===\n")
        return run(args.model, conn, args.min_score)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
