"""
Faz 4 kapanma ölçümü: quiz'in her cevabının korpusta DOĞRULANABİLİR olduğunun
gösterimi (docs/FEATURE_SPEC.md §12.12).

Ölçtüğü iddia: **cevap anahtarı uydurulmuyor.** Üç tipin cevabı korpustan
birebir gelir (boşluk terimi, kaynak atfı), dördüncüsünün (short_answer)
referans cevabı sadakat kapısından geçmek zorundadır; geçemezse soru quiz'e
ALINMAZ. Çeldiriciler LLM'e yazdırılmaz -- başka kümelerin gerçek terimleridir
ve soru chunk'ında GEÇMEDİKLERİ doğrulanır.

    fidelity_trap.py  -> "kapı bu iddiayı grounded sayıyor"       (sınır, pin)
    report_trap.py    -> "ürün bu cümleyi YAYIMLAMIYOR"           (Faz 2)
    mindmap_proof.py  -> "yapı modelden GELMİYOR"                 (Faz 3)
    quiz_proof.py     -> "cevap anahtarı KORPUSTAN doğrulanıyor"  (Faz 4)

`--trap` ile koşulursa short_answer'ın referans cevabına tuzak cümlesi
BİLEREK enjekte edilir ("model hallüsine etseydi" senaryosu) ve o sorunun
quiz'e alınmadığı gösterilir. Enjeksiyon çıktıda açıkça yazılır.

Korpus `eval.db`'dir; üretim `rag.db`'sine DOKUNULMAZ. Rutin kapıya EKLENMEZ.

Kullanım:
    .venv/bin/python eval/quiz_proof.py
    .venv/bin/python eval/quiz_proof.py --trap
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_eval  # noqa: E402
from rag import store  # noqa: E402
from rag.artifacts import base, quiz  # noqa: E402
from rag.artifacts.store import get_artifact, list_attempts  # noqa: E402
from rag.topics import cluster_corpus  # noqa: E402

TRAP_CLAIM = (
    "Bu sistem varsayılan olarak GPT-4 kullanır ve verileri OpenAI "
    "sunucularına gönderir."
)


def _ensure_corpus() -> None:
    if run_eval.EVAL_DB.exists():
        return
    print("=== eval.db kuruluyor (data/*.md) ===")
    conn = store.connect(run_eval.EVAL_DB)
    try:
        for r in run_eval.ingest.ingest_markdown_dir(conn=conn):
            print(f"  {r.summary()}")
    finally:
        conn.close()
    print()


def _install_injection() -> None:
    """İLK short_answer çağrısının referans cevabına tuzak cümlesini ekler.

    `quiz._generate_short_answer` sarılır; modelin kendisine dokunulmaz.
    """
    original = quiz._generate_short_answer
    state = {"injected": False}

    def wrapper(client, context):
        generated = original(client, context)
        if generated is None or state["injected"]:
            return generated
        state["injected"] = True
        question, answer = generated
        return question, f"{answer} {TRAP_CLAIM}"

    quiz._generate_short_answer = wrapper


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    trap_mode = "--trap" in argv

    _ensure_corpus()
    if trap_mode:
        _install_injection()

    conn = store.connect(run_eval.EVAL_DB)
    try:
        topics = cluster_corpus(conn)
        chunk_count = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
        print("=== Faz 4 kapanma ölçümü: quiz, gerçek model ===\n")
        print(f"  Korpus      : eval.db, {chunk_count} chunk, {len(topics)} küme")
        print("  LLM çağrısı : yalnızca short_answer seçilen kümeler için")
        if trap_mode:
            print("  ENJEKSİYON  : tuzak cümlesi İLK short_answer'ın REFERANS")
            print("                CEVABINA elle eklendi (organik hallüsinasyon DEĞİL)")
        print()

        artifact_id = base.generate_artifact(
            conn,
            kind="quiz",
            scope="corpus",
            document_id=None,
            params={},
            emit=lambda name, payload: print(f"  [{name}] {payload}"),
        )
        artifact = get_artifact(conn, artifact_id)

        chunks = {
            r["id"]: dict(r)
            for r in conn.execute("SELECT id, source, content FROM chunks")
        }
        doc_text: dict[str, str] = {}
        for row in chunks.values():
            doc_text[row["source"]] = doc_text.get(row["source"], "") + " " + row["content"]

        # Cevap anahtarıyla bir deneme gönder: doğru cevaplar TAM puan almalı.
        payload = artifact["payload"]
        key_answers = {q["id"]: q["answer"] for q in payload["questions"]}
        scored_key = quiz.score_attempt(payload, key_answers)
        wrong_answers = {q["id"]: "kesinlikle alakasiz bir cevap" for q in payload["questions"]}
        scored_wrong = quiz.score_attempt(payload, wrong_answers)

        from rag.artifacts.store import create_attempt

        create_attempt(
            conn,
            artifact_id=artifact_id,
            started_at="ölçüm",
            completed_at="ölçüm",
            score=scored_key["score"],
            answers=key_answers,
        )
        attempts = list_attempts(conn, artifact_id)
    finally:
        conn.close()

    questions = payload["questions"]
    dropped = payload["dropped"]
    claims = artifact["claims"]
    by_type: dict[str, int] = {}
    for q in questions:
        by_type[q["type"]] = by_type.get(q["type"], 0) + 1

    print(f"\n--- Kaydedilen artefakt (id={artifact_id}) geri okundu ---\n")
    print(f"  Soru          : {len(questions)}  {by_type}")
    print(f"  Düşen soru    : {len(dropped)}")
    score = artifact["fidelity_score"]
    print(f"  fidelity_score: {'—' if score is None else format(score, '.4f')}"
          "  (ORAN: grounded/toplam)")

    print("\n  Sorular:")
    for q in questions:
        print(f"    [{q['type']}] K{q['topic_id']}  {q['citation']}")
        print(f"      {q['prompt'][:120]}")
        if q["choices"]:
            print(f"      şıklar: {q['choices']}")
        print(f"      cevap : {q['answer']!r}")

    if dropped:
        print("\n  Quiz'e alınmayan sorular:")
        for item in dropped:
            item_score = "—" if item["score"] is None else f"{item['score']:.4f}"
            print(f"    K{item['topic_id']} · {item['reason']} · {item_score} · terimler={item['terms']}")

    print("\n  Cevap anahtarıyla deneme:")
    print(f"    skor        : {scored_key['score']}  "
          f"({scored_key['correct_count']}/{scored_key['deterministic_total']})")
    print(f"    benzerlik   : {scored_key['similarity_total']} soru (puana KATILMAZ)")
    print(f"  Alakasız cevapla deneme skoru: {scored_wrong['score']}")

    markdown = quiz.to_markdown(payload)

    # --- kontroller ---------------------------------------------------------
    def answer_is_verifiable(q: dict) -> bool:
        """Cevap anahtarı korpustan DOĞRULANABİLİR mi?"""
        chunk = chunks.get(q["chunk_id"])
        if chunk is None:
            return False
        if q["type"] in ("multiple_choice", "fill_blank"):
            # Boşluk terimi hem gerekçe cümlesinde hem kaynak chunk'ta geçmeli.
            return q["answer"] in q["evidence"] and q["evidence"] in chunk["content"]
        if q["type"] == "true_false":
            # İddia edilen belge adı metadata ile tutarlı olmalı.
            claimed_true = q["answer"] == "true"
            named = [s for s in doc_text if s in q["prompt"]]
            return (
                q["evidence"] in chunk["content"]
                and len(named) >= 1
                and (chunk["source"] in named) == claimed_true
            )
        # short_answer: referans cevap sadakat kapısından GEÇMİŞ olmalı.
        return any(
            c["claim_text"] == q["answer"] and c["verdict"] == "grounded"
            for c in claims
        )

    def distractors_are_real_and_wrong(q: dict) -> bool:
        if q["type"] != "multiple_choice":
            return True
        chunk = chunks[q["chunk_id"]]
        others = [c for c in q["choices"] if c != q["answer"]]
        return (
            len(q["choices"]) == len(set(q["choices"]))
            and q["answer"] in q["choices"]
            and all(c.lower() not in chunk["content"].lower() for c in others)
            and all(
                any(c.lower() in row["content"].lower() for row in chunks.values())
                for c in others
            )
        )

    trap_claim = next((c for c in claims if TRAP_CLAIM in c["claim_text"]), None)
    trap_in_body = any(TRAP_CLAIM in q["answer"] for q in questions)

    checks = [
        ("her küme için en fazla bir soru", len(questions) + len(dropped) <= len(topics)),
        ("her sorunun cevabı korpusta DOĞRULANABİLİR",
         all(answer_is_verifiable(q) for q in questions)),
        ("çeldiriciler korpustan ve kaynak chunk'ta GEÇMİYOR",
         all(distractors_are_real_and_wrong(q) for q in questions)),
        ("her sorunun bir artifact_claims satırı var",
         len([c for c in claims if c["node_path"].startswith("/questions/")]) == len(questions)),
        ("iddia skorları ham cosine aralığında",
         all(c["score"] is None or -1.0 <= c["score"] <= 1.0 for c in claims)),
        ("cevap anahtarı TAM puan alıyor",
         scored_key["score"] is None or scored_key["score"] == 1.0),
        ("alakasız cevap puan almıyor",
         scored_wrong["score"] is None or scored_wrong["score"] == 0.0),
        ("short_answer bir eşiğe indirgenmiyor (correct=None)",
         all(r["correct"] is None for r in scored_key["results"]
             if r["type"] == "short_answer")),
        ("deneme kalıcılaştı", len(attempts) >= 1),
        ("markdown'da http(s):// yok",
         "http://" not in markdown and "https://" not in markdown),
        ("markdown cevap anahtarını AYRI bölümde veriyor",
         "## Sorular" in markdown and "## Cevap Anahtarı" in markdown),
        ("düşen sorunun METNİ markdown gövdesinde YOK",
         all(item["text"] not in markdown for item in dropped)),
    ]

    if trap_mode:
        checks.extend([
            ("tuzak artifact_claims'te var", trap_claim is not None),
            ("tuzaklı soru quiz'e ALINMADI", not trap_in_body),
            ("tuzak /dropped/ altında",
             trap_claim is not None and trap_claim["node_path"].startswith("/dropped/")),
            ("quiz gövdesinde 'gpt'/'openai' YOK",
             not any(
                 needle in (q["prompt"] + q["answer"] + q["evidence"]).lower()
                 for q in questions
                 for needle in ("gpt", "openai", "openaı")
             )),
        ])

    print("\n--- §12.12 tablosu ---\n")
    for label, ok in checks:
        print(f"  [{'OK ' if ok else 'HAYIR'}] {label}")

    if all(ok for _, ok in checks):
        print("\n  PASS -- her sorunun cevabı korpusta doğrulanabilir; "
              "çeldiriciler gerçek ama yanlış.")
        return 0

    print("\n  FAIL -- Faz 4'ün kapanma koşulu karşılanmadı. Bu, "
          "FIDELITY_MIN_SCORE'u değiştirme gerekçesi DEĞİLDİR (AGENTS.md §1.4).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
