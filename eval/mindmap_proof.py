"""
Faz 3 kapanma ölçümü: zihin haritasının korpustan çıktığının ve her düğümün
kaynağa bağlı olduğunun gösterimi (docs/FEATURE_SPEC.md §11.10).

Ölçtüğü iddia: **haritayı LLM çizmiyor.** Düğümler, üyelikler ve kenarlar
kümelemeden deterministik geliyor; modelin tek katkısı ETİKET ve o etiket de
sadakat kapısından geçmek zorunda. Geçemezse düğüm SİLİNMEZ -- adı korpustan
türer ve öneri `dropped`'a yazılır.

    fidelity_trap.py  -> "kapı bu iddiayı grounded sayıyor"      (sınır, pin)
    report_trap.py    -> "ürün bu cümleyi YAYIMLAMIYOR"          (Faz 2)
    mindmap_proof.py  -> "yapı modelden GELMİYOR, etiket denetleniyor"

Korpus `eval.db`'dir; üretim `rag.db`'sine DOKUNULMAZ.

Rutin teslim kapısına EKLENMEZ -- küme sayısı kadar LLM çağrısı yapar.
Bir kez koşulur, sonucu PROJE_DURUMU.md'ye yazılır.

Kullanım:
    .venv/bin/python eval/mindmap_proof.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_eval  # noqa: E402
from rag import config, store  # noqa: E402
from rag.artifacts import base, mindmap  # noqa: E402
from rag.artifacts.store import get_artifact  # noqa: E402
from rag.topics import cluster_corpus, topic_similarity  # noqa: E402


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


def _clustering_is_stable(topics) -> bool:
    """Yeni bir bağlantıda kümeleme birebir aynı sonucu veriyor mu (§9.4)?"""
    conn = store.connect(run_eval.EVAL_DB)
    try:
        return [t.chunk_ids for t in topics] == [
            t.chunk_ids for t in cluster_corpus(conn)
        ]
    finally:
        conn.close()


def main(argv=None) -> int:
    _ensure_corpus()

    conn = store.connect(run_eval.EVAL_DB)
    try:
        topics = cluster_corpus(conn)
        chunk_count = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
        print("=== Faz 3 kapanma ölçümü: zihin haritası, gerçek model ===\n")
        print(f"  Korpus      : eval.db, {chunk_count} chunk, {len(topics)} küme")
        print(f"  LLM çağrısı : {len(topics)} (küme başına 1 etiket)")
        print(f"  Kenar eşiği : {config.MINDMAP_EDGE_MIN_SIMILARITY} (ham cosine)\n")

        artifact_id = base.generate_artifact(
            conn,
            kind="mindmap",
            scope="corpus",
            document_id=None,
            params={},
            emit=lambda name, payload: print(f"  [{name}] {payload}"),
        )
        artifact = get_artifact(conn, artifact_id)

        sources_by_chunk = {
            r["id"]: r["source"] for r in conn.execute("SELECT id, source FROM chunks")
        }
    finally:
        conn.close()

    payload = artifact["payload"]
    nodes = payload["nodes"]
    edges = payload["edges"]
    dropped = payload["dropped"]
    topic_nodes = [n for n in nodes if n["kind"] == "topic"]
    claims = artifact["claims"]

    print(f"\n--- Kaydedilen artefakt (id={artifact_id}) geri okundu ---\n")
    print(f"  Düğüm        : {len(nodes)} (1 kök + {len(topic_nodes)} konu)")
    print(f"  Kenar        : {len(edges)}")
    print(f"  Düşen etiket : {len(dropped)}")
    score = artifact["fidelity_score"]
    print(f"  fidelity_score: {'—' if score is None else format(score, '.4f')}"
          "  (ORAN: grounded/toplam)")

    print("\n  Düğümler:")
    for node in topic_nodes:
        sources = sorted({sources_by_chunk[c] for c in node["chunk_ids"]})
        mark = "model" if node["label_source"] == "model" else "YEDEK"
        print(f"    {node['id']:>4} [{mark}] {node['label']!r}")
        print(f"           {node['size']} chunk · {sources}")

    if edges:
        print("\n  Kenarlar (ham cosine):")
        for edge in edges:
            print(f"    {edge['from']} — {edge['to']}  {edge['weight']:.4f}")
    else:
        print("\n  Kenar yok (kümeler eşiğin altında -- HATA DEĞİL).")

    if dropped:
        print("\n  Düşen etiket önerileri:")
        for item in dropped:
            score = "—" if item["score"] is None else f"{item['score']:.4f}"
            print(f"    K{item['topic_id']} {item['text']!r} · {item['reason']} · {score}")

    markdown = mindmap.to_markdown(payload)

    # --- kontroller ---------------------------------------------------------
    all_chunk_ids = sorted(sources_by_chunk)
    mapped_chunk_ids = sorted(c for n in topic_nodes for c in n["chunk_ids"])
    label_claims = {c["node_path"]: c for c in claims if c["node_path"].startswith("/nodes/")}
    model_nodes = [
        (i, n) for i, n in enumerate(nodes) if n.get("label_source") == "model"
    ]
    recomputed = {
        (f"n{a.id}", f"n{b.id}"): topic_similarity(a, b)
        for i, a in enumerate(topics)
        for b in topics[i + 1:]
    }

    checks = [
        ("kök düğüm tek ve korpustan", len([n for n in nodes if n["kind"] == "root"]) == 1
         and nodes[0]["label_source"] == "corpus"),
        ("küme başına tam bir düğüm", len(topic_nodes) == len(topics)),
        ("korpusun HER chunk'ı bir düğümde", mapped_chunk_ids == all_chunk_ids),
        ("her düğümün her chunk'ı için atıf var",
         all(len(n["citations"]) == len(n["chunk_ids"]) for n in topic_nodes)),
        ("atıflar [Kaynak: ...] biçiminde",
         all(c["citation"].startswith("[Kaynak: ")
             for n in topic_nodes for c in n["citations"])),
        ("her kenar eşiği AŞIYOR",
         all(e["weight"] > config.MINDMAP_EDGE_MIN_SIMILARITY for e in edges)),
        ("kenar ağırlığı = topic_similarity (ham cosine, yeniden ölçeklenmemiş)",
         all(abs(e["weight"] - recomputed[(e["from"], e["to"])]) < 1e-6 for e in edges)),
        ("her MODEL etiketinin artifact_claims satırı var",
         all(f"/nodes/{i}/label" in label_claims for i, _n in model_nodes)),
        ("iddia skorları ham cosine aralığında",
         all(c["score"] is None or -1.0 <= c["score"] <= 1.0 for c in claims)),
        ("YEDEK etiket iddia olarak sayılmadı",
         len(label_claims) == len(model_nodes)),
        ("düşen etiketin METNİ markdown gövdesinde YOK",
         all(item["text"] == "" or item["text"] not in markdown for item in dropped)),
        ("markdown'da http(s):// yok",
         "http://" not in markdown and "https://" not in markdown),
        ("kümeleme determinizmi (ikinci çağrı birebir aynı)", _clustering_is_stable(topics)),
    ]

    print("\n--- §11.10 tablosu ---\n")
    for label, ok in checks:
        print(f"  [{'OK ' if ok else 'HAYIR'}] {label}")

    if all(ok for _, ok in checks):
        print(
            "\n  PASS -- harita korpustan çıkıyor, her düğüm kaynağa bağlı, "
            "modelin katkısı yalnızca DENETLENEN etiket."
        )
        return 0

    print(
        "\n  FAIL -- Faz 3'ün kapanma koşulu karşılanmadı. Bu, "
        "MINDMAP_EDGE_MIN_SIMILARITY'yi ya da FIDELITY_MIN_SCORE'u değiştirme "
        "gerekçesi DEĞİLDİR (CLAUDE.md §1.4): önce kök neden aranır."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
