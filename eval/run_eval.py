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

`--json` ile sonuçlar eval/results.json'a yazılır ve /api/metrics bu dosyayı
servis eder (docs/FEATURE_SPEC.md §6). Yazma BİRLEŞTİRMELİDİR: her model
çalıştırması yalnızca kendi `models[]` girdisini ekler/günceller,
`--sweep-threshold` yalnızca `threshold_sweep` anahtarını günceller. Aksi
halde ikinci çalıştırma birincinin sonucunu silerdi.

    python eval/run_eval.py --json                     # qwen2.5-7b sonucunu yaz
    python eval/run_eval.py --model phi-4-mini --json  # kıyas girdisini EKLE
    python eval/run_eval.py --sweep-threshold --json   # eşik taramasını EKLE
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import answer, config, ingest, models, retrieve, store  # noqa: E402

EVAL_DB = Path(__file__).resolve().parent / "eval.db"
EVAL_SET = Path(__file__).resolve().parent / "eval_set.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


# --------------------------------------------------------------------------- kalıcılaştırma


def _fresh_results() -> dict:
    """Boş iskelet (docs/FEATURE_SPEC.md §6.2 şeması)."""
    return {
        "generated_at": None,
        "config": {},
        "corpus": {},
        "models": [],
        "threshold_sweep": None,
    }


def _load_results(path: Path) -> dict:
    if not path.exists():
        return _fresh_results()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Bozuk dosya sessizce veri kaybettirmesin; sıfırdan başla.
        print(f"  [uyarı] {path.name} okunamadı, sıfırdan yazılıyor.")
        return _fresh_results()
    skeleton = _fresh_results()
    skeleton.update(data)
    return skeleton


def _save_results(path: Path, data: dict, conn) -> None:
    """Ortak alanları tazeleyip diske yazar."""
    matrix, _ = store.load_matrix(conn)
    data["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    data["config"] = {
        "min_score": config.MIN_SCORE,
        "top_k": config.TOP_K,
        "chunk_words": config.CHUNK_WORDS,
        "chunk_overlap_words": config.CHUNK_OVERLAP_WORDS,
    }
    data["corpus"] = {
        "chunk_count": int(matrix.shape[0]),
        "document_count": len(store.list_documents(conn)),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n  -> {path} yazıldı")


def _merge_model_result(data: dict, model_result: dict) -> None:
    """Aynı alias varsa DEĞİŞTİR, yoksa EKLE. Diğer modellerin sonucu korunur."""
    alias = model_result["alias"]
    data["models"] = [m for m in data["models"] if m.get("alias") != alias]
    data["models"].append(model_result)
    # Aktif model config'ten belirlenir; kıyas çalıştırmaları bunu bozmasın.
    for m in data["models"]:
        m["is_active"] = m["alias"] == config.CHAT_MODEL


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
    # Tek kaynak: rag/answer.py::is_refusal. Reddetme tespiti (bulanık
    # eşleşme, kırılganlık gerekçesi orada) burada TEKRAR EDİLMEZ -- eval
    # harness'i production'ın kullandığı AYNI mantıkla ölçmeli, aksi halde
    # burada geçen bir soru production'da sessizce reddedilmeyebilir.
    return answer.is_refusal(text)


def run(model: str | None, conn, min_score: float | None) -> tuple[int, dict]:
    """Değerlendirmeyi çalıştırır. (çıkış_kodu, model_sonuç_dict) döndürür.

    Yazdırma davranışı değişmedi; dict yalnızca `--json` için ek olarak
    toplanır.
    """
    questions = load_questions()
    rows, failures, records = [], [], []
    retrieval_found = 0
    answerable_total = 0
    t_start = time.time()

    for q in questions:
        t0 = time.time()
        result = answer.answer_query(q["question"], model=model,
                                     min_score=min_score, conn=conn)
        dt = time.time() - t0
        cat = q["category"]
        ok, detail = True, ""
        found: bool | None = None
        n_kw: int | None = None
        kw_total: int | None = None

        if cat == "answerable":
            answerable_total += 1
            hits = retrieve.get_top_chunks(q["question"], min_score=min_score, conn=conn)
            sources = {h.source for h in hits}
            found = q["expected_source"] in sources
            retrieval_found += int(found)
            n_kw, missing = keyword_hit(result.text, q["expected_keywords"])
            kw_total = len(q["expected_keywords"])
            ok = found and not refused(result.text)
            detail = f"kaynak={'+' if found else '-'} kelime={n_kw}/{kw_total}"
            if missing:
                detail += f" eksik={missing}"
        elif cat == "unanswerable":
            ok = refused(result.text)
            detail = "reddetti" if ok else "REDDETMEDİ"
        elif cat == "edge_case":
            ok = refused(result.text) or len(result.text.split()) < 60
            detail = f"{len(result.text.split())} kelime"
        elif cat == "meta":
            # rag/query_router.py özetleme yolu. Ölçülen üretim hatasının
            # (bkz. eval_set.json Q16 notu) regresyon testi.
            if q.get("expects_clarification"):
                ok = (not result.answered) and "hangi belgeyi" in result.text.lower()
                detail = "netleştirdi" if ok else "netleştirmedi"
            else:
                ok = result.answered and not refused(result.text)
                detail = "özetlendi" if ok else "özetlenmedi/reddetti"
        elif cat == "corpus":
            # query_router 'corpus' yolu -- LLM çağrılmaz, cevap store'dan gelir.
            ok = result.answered and not refused(result.text)
            n_kw, missing = keyword_hit(result.text, q.get("expected_keywords", []))
            kw_total = len(q.get("expected_keywords", []))
            if kw_total:
                ok = ok and n_kw == kw_total
            detail = f"cevaplandı kelime={n_kw}/{kw_total}" if kw_total else \
                     ("cevaplandı" if ok else "cevaplanmadı")
        else:  # cross_lingual
            # answerable ile aynı retrieval-isabet testi; ayrı sayaçlarda
            # tutulur (retrieval_hits alanı yalnızca orijinal 10 answerable
            # soruyu ölçer -- FEATURE_SPEC §6.2, dondurulmuş anlam).
            hits = retrieve.get_top_chunks(q["question"], min_score=min_score, conn=conn)
            sources = {h.source for h in hits}
            found = q["expected_source"] in sources
            ok = found and not refused(result.text)
            detail = f"kaynak={'+' if found else '-'} (diller arası)"

        rows.append((q["id"], cat, ok, dt, detail))
        records.append({
            "id": q["id"],
            "category": cat,
            "passed": ok,
            "seconds": round(dt, 2),
            "expected_source": q.get("expected_source"),
            "source_found": found,
            "keywords_matched": n_kw,
            "keywords_total": kw_total,
            "answer": result.text,
        })
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

    alias = model or config.CHAT_MODEL
    loaded = models._models.get(alias)
    model_result = {
        "alias": alias,
        "model_id": loaded.id if loaded is not None else None,
        "is_active": alias == config.CHAT_MODEL,
        "summary": {
            "passed": passed,
            "total": len(rows),
            "by_category": {c: [sum(v), len(v)] for c, v in by_cat.items()},
            "retrieval_hits": [retrieval_found, answerable_total],
            "avg_seconds": round(total / len(rows), 2),
        },
        "questions": records,
    }
    return (0 if passed == len(rows) else 1), model_result


def sweep_threshold(conn) -> tuple[int, dict]:
    """MIN_SCORE'u taramak için: her soru için en yüksek skoru ölçer, LLM çağırmaz.

    Amaç, cevabı olan sorularla olmayanların skor aralıklarını görüp eşiği
    aradaki boşluğa koymak. (çıkış_kodu, sweep_dict) döndürür.
    """
    # 'meta' ve 'corpus' bu taramanın DIŞINDA tutulur: query_router.py onları
    # benzerlik aramasına hiç göndermiyor artık, bu yüzden bir "skor"ları
    # ölçmek yanıltıcı olur (meta sorguların skoru yapısal olarak düşüktür --
    # bkz. rag/config.py -- ve 'other' grubunu anlamsızca kirletir).
    #
    # 'cross_lingual' 'answerable' kovasına eklenir: ikisi de gerçekten
    # cevaplanabilir, retrieval'a giren sorulardır; ayrı tutulsaydı diller
    # arası cezanın (ölçüldü: -0.077) eşik kalibrasyonunda hiç görünmemesi
    # riski doğardı.
    questions = [q for q in load_questions() if q["category"] not in ("meta", "corpus")]
    answerable, other = [], []
    retrievable = {"answerable", "cross_lingual"}

    for q in questions:
        if not q["question"].strip():
            continue
        hits = retrieve.get_top_chunks(q["question"], min_score=None, conn=conn)
        top = hits[0].score if hits else 0.0
        is_answerable = q["category"] in retrievable
        correct = is_answerable and any(h.source == q["expected_source"] for h in hits)
        (answerable if is_answerable else other).append((q["id"], top, correct))
        mark = "+" if is_answerable else "-"
        print(f"  [{mark}] {q['id']}  en yüksek={top:.4f}  "
              f"{'kaynak bulundu' if correct else ''}")

    a_scores = [s for _, s, _ in answerable]
    o_scores = [s for _, s, _ in other]
    print(f"\n  cevaplanabilir  : min={min(a_scores):.4f}  max={max(a_scores):.4f}")
    print(f"  diğer           : min={min(o_scores):.4f}  max={max(o_scores):.4f}")

    table = []
    print(f"\n  {'eşik':>6}  {'geçen answerable':>17}  {'geçen diğer':>12}")
    for thr in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]:
        a = sum(1 for s in a_scores if s >= thr)
        o = sum(1 for s in o_scores if s >= thr)
        star = "  <-- şu anki" if abs(thr - config.MIN_SCORE) < 1e-9 else ""
        print(f"  {thr:6.2f}  {a:>10}/{len(a_scores)}  {o:>10}/{len(o_scores)}{star}")
        table.append({
            "threshold": thr,
            "answerable_passed": a,
            "answerable_total": len(a_scores),
            "other_passed": o,
            "other_total": len(o_scores),
        })
    print("\n  Not: 'diğer' grubunun geçmesi kötü değil -- konu yakın sorularda")
    print("  reddetme kararını LLM verir. Eşiğin işi konu DIŞI soruları elemek.")

    return 0, {
        "answerable_scores": [round(s, 4) for s in a_scores],
        "other_scores": [round(s, 4) for s in o_scores],
        "table": table,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RAG değerlendirme harness'i")
    parser.add_argument("--model", help=f"chat modeli (varsayılan: {config.CHAT_MODEL})")
    parser.add_argument("--ingest", action="store_true",
                        help="eval.db'yi data/*.md fixture'larından yeniden kur")
    parser.add_argument("--sweep-threshold", action="store_true",
                        help="MIN_SCORE taraması (LLM çağırmaz, hızlı)")
    parser.add_argument("--min-score", type=float, help="bu çalıştırma için eşiği geçersiz kıl")
    parser.add_argument("--json", nargs="?", const=str(RESULTS_PATH), metavar="YOL",
                        help=f"sonuçları JSON olarak yaz (varsayılan: {RESULTS_PATH.name}); "
                             "mevcut dosyayla BİRLEŞTİRİLİR")
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

        json_path = Path(args.json) if args.json else None

        if args.sweep_threshold:
            code, sweep = sweep_threshold(conn)
            if json_path:
                data = _load_results(json_path)
                data["threshold_sweep"] = sweep
                _save_results(json_path, data, conn)
            return code

        print(f"=== model: {args.model or config.CHAT_MODEL}, "
              f"eşik: {args.min_score if args.min_score is not None else config.MIN_SCORE} ===\n")
        code, model_result = run(args.model, conn, args.min_score)
        if json_path:
            data = _load_results(json_path)
            _merge_model_result(data, model_result)
            _save_results(json_path, data, conn)
        return code
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
