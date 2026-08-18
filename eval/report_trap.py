"""
Faz 2 kapanma ölçümü: tuzağın ÜRÜN DAVRANIŞI hâline geldiğinin gösterimi
(docs/FEATURE_SPEC.md §10.13).

`eval/fidelity_trap.py` bir SINIRI sabitler: `bind_claims` grounding ölçer,
entailment ölçmez; ürünle çelişen ama konuya yakın tuzak iddia hâlâ
`0.5487 / grounded` çıkar ve bu BEKLENEN sonuçtur. Bu script farklı bir şey
gösterir: aynı iddia, gerçek rapor hattından geçtiğinde RAPORA GİRMİYOR.

    fidelity_trap.py  -> "kapı bu iddiayı grounded sayıyor"     (sınır, pin)
    report_trap.py    -> "ürün bu iddiayı YAYIMLAMIYOR"          (telafi)

İkisi çelişmez, farklı katmanları ölçerler (§10.1.2). Bu koşum
FIDELITY_MIN_SCORE'u değiştirme gerekçesi ÜRETEMEZ (AGENTS.md §1.4).

ENJEKSİYON -- gizlenmiyor: model bu cümleyi kendiliğinden üretmedi. Bir
bölümün LLM çıktısına tuzak cümlesi BİLEREK eklendi ("model hallüsine
etseydi" senaryosu). Hattın geri kalanı gerçekten çalışır: bağlama -> ikinci
katman -> payload -> kalıcılaştırma -> geri okuma.

Korpus `eval.db`'dir (pinin ölçüldüğü korpus, §10.2): "GPT"/"OpenAI"
oradaki 20 chunk'ın hiçbirinde geçmiyor, dolayısıyla düşürme deterministik.
Üretim `rag.db`'sine DOKUNULMAZ.

Rutin teslim kapısına EKLENMEZ -- 12 yerine küme sayısı kadar+2 LLM çağrısı
ile dakikalar sürer. Bir kez koşulur, sonucu PROJE_DURUMU.md'ye yazılır.

Kullanım:
    .venv/bin/python eval/report_trap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_eval  # noqa: E402
from rag import store  # noqa: E402
from rag.artifacts import base, report  # noqa: E402
from rag.artifacts.store import get_artifact  # noqa: E402
from rag.topics import cluster_corpus  # noqa: E402

TRAP_CLAIM = (
    "Bu sistem varsayılan olarak GPT-4 kullanır ve verileri OpenAI "
    "sunucularına gönderir."
)
# Türkçe-duyarlı küçültme "OpenAI" -> "openaı" üretir (I -> ı, §10.6 kural 2).
EXPECTED_TERMS = ("gpt-4", "openaı")
FIDELITY_MIN_RATIO = 0.90


def _install_injection() -> None:
    """İLK bölüm çağrısının LLM çıktısına tuzak cümlesini ekler.

    `report._generate_section_text` sarılır; modelin kendisine dokunulmaz,
    yalnızca döndürdüğü metin uzatılır. Enjeksiyon TEK kez uygulanır ki
    "kaç iddia düşürüldü" sayısı belirsizleşmesin.
    """
    original = report._generate_section_text
    state = {"injected": False}

    def wrapper(client, context):
        text = original(client, context)
        if not state["injected"]:
            state["injected"] = True
            return f"{text} {TRAP_CLAIM}"
        return text

    report._generate_section_text = wrapper


def main(argv=None) -> int:
    if not run_eval.EVAL_DB.exists():
        print("=== eval.db kuruluyor (data/*.md) ===")
        conn = store.connect(run_eval.EVAL_DB)
        try:
            for r in run_eval.ingest.ingest_markdown_dir(conn=conn):
                print(f"  {r.summary()}")
        finally:
            conn.close()
        print()

    _install_injection()

    conn = store.connect(run_eval.EVAL_DB)
    try:
        topics = cluster_corpus(conn)
        print("=== Faz 2 kapanma ölçümü: enjekte edilmiş tuzak, gerçek rapor hattı ===\n")
        print(f"  Korpus       : eval.db, {len(topics)} küme")
        print(f"  LLM çağrısı  : {len(topics) + 2} (1 bulgular + {len(topics)} detay + 1 özet)")
        print("  ENJEKSİYON   : tuzak cümlesi İLK bölümün LLM çıktısına elle eklendi")
        print("                 (organik bir hallüsinasyon DEĞİL, senaryo simülasyonu)\n")

        artifact_id = base.generate_artifact(
            conn,
            kind="report",
            scope="corpus",
            document_id=None,
            params={},
            emit=lambda name, payload: print(f"  [{name}] {payload}"),
        )

        artifact = get_artifact(conn, artifact_id)
    finally:
        conn.close()

    payload = artifact["payload"]
    dropped = payload["dropped"]
    claims = artifact["claims"]

    trap_claim = next((c for c in claims if c["claim_text"] == TRAP_CLAIM), None)
    trap_index = next((i for i, d in enumerate(dropped) if d["text"] == TRAP_CLAIM), None)
    trap_dropped = dropped[trap_index] if trap_index is not None else None

    body = " ".join(
        sentence
        for section in payload["sections"]
        for paragraph in section["paragraphs"]
        for sentence in paragraph["sentences"]
    ).lower()
    body_hits = sum(body.count(needle) for needle in ("gpt", "openai", "openaı"))

    kept_count = sum(1 for c in claims if c["node_path"].startswith("/sections/"))
    reasons: dict[str, int] = {}
    for item in dropped:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1

    print(f"\n--- Kaydedilen artefakt (id={artifact_id}) geri okundu ---\n")
    print(f"  Toplam iddia        : {len(claims)}")
    print(f"  Rapora giren        : {kept_count}")
    print(f"  Düşürülen           : {len(dropped)}  {reasons or ''}")
    print(f"  fidelity_score      : {artifact['fidelity_score']:.4f}  (ORAN: grounded/toplam)")
    print(f"  Gövdede 'gpt'/'openai': {body_hits} eşleşme")

    if trap_claim is not None:
        print("\n  Tuzağın artifact_claims satırı:")
        print(f"    score     : {trap_claim['score']:.4f}   (fidelity_trap.py pini: 0.5487)")
        print(f"    verdict   : {trap_claim['verdict']}   (pin: grounded -- BEKLENEN)")
        print(f"    node_path : {trap_claim['node_path']}")
    if trap_dropped is not None:
        print("\n  Tuzağın payload['dropped'] girdisi:")
        print(f"    reason    : {trap_dropped['reason']}")
        print(f"    terms     : {trap_dropped['terms']}")

    checks = [
        ("tuzak artifact_claims'te var", trap_claim is not None),
        ("tuzak grounded çıktı (pin korundu)",
         trap_claim is not None and trap_claim["verdict"] == "grounded"),
        ("tuzak /dropped/ altında, sections'ta DEĞİL",
         trap_claim is not None and trap_claim["node_path"] == f"/dropped/{trap_index}"),
        ("düşürme sebebi unverified_terms",
         trap_dropped is not None and trap_dropped["reason"] == "unverified_terms"),
        ("terimler gpt-4 ve openaı içeriyor",
         trap_dropped is not None
         and all(term in trap_dropped["terms"] for term in EXPECTED_TERMS)),
        ("dropped_count tuzağı içeriyor (>=1)", len(dropped) >= 1),
        ("rapor gövdesinde gpt/openai YOK", body_hits == 0),
        (f"fidelity_score >= {FIDELITY_MIN_RATIO}",
         artifact["fidelity_score"] is not None
         and artifact["fidelity_score"] >= FIDELITY_MIN_RATIO),
    ]

    print("\n--- §10.13 tablosu ---\n")
    for label, ok in checks:
        print(f"  [{'OK ' if ok else 'HAYIR'}] {label}")

    if all(ok for _, ok in checks):
        print(
            "\n  PASS -- kapı iddiayı hâlâ grounded sayıyor (sınır duruyor, "
            "gizlenmiyor) ama ÜRÜN onu yayımlamıyor."
        )
        return 0

    print(
        "\n  FAIL -- Faz 2'nin kapanma koşulu karşılanmadı. Bu, "
        "FIDELITY_MIN_SCORE'u değiştirme gerekçesi DEĞİLDİR (AGENTS.md §1.4, "
        "§10.13): ikinci katmanın (fidelity.unverified_terms / should_drop) "
        "ya da rapor hattının düşürme yolunun kök nedeni araştırılmalı."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
