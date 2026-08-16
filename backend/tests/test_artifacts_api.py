"""`/api/artifacts` -- CRUD + SSE üretim iskeleti (FEATURE_SPEC.md §9.8).

Faz 1'de registry boş olduğu için POST akışı her zaman `stage: selection` ve
`stage: clustering`'i gerçekten yayıp `GENERATION_FAILED` ile biter (§9.5).
GET/DELETE testleri `rag/artifacts/store.py::create_artifact` ile doğrudan
artefakt tohumlayarak `is_stale`/`citation` türetmelerini doğrular.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from rag.artifacts import base
from rag import store
from rag.artifacts.fidelity import ClaimBinding
from rag.artifacts.store import create_artifact

# Faz 2 rapor payload'ı (§10.5 dondurulmuş şema) -- export ve dropped_count
# türetmeleri bunun üzerinden doğrulanır.
_REPORT_PAYLOAD = {
    "kind": "report",
    "outline": ["executive_summary", "key_findings", "detailed_analysis", "tables", "citations"],
    "sections": [
        {
            "id": "exec",
            "kind": "executive_summary",
            "title": "Yönetici Özeti",
            "topic_id": None,
            "context_chunk_ids": [1],
            "paragraphs": [{"sentences": ["Rapora giren cümle."]}],
        }
    ],
    "tables": [{"id": "coverage", "title": "Belge × Konu Kapsama",
                "columns": ["Belge", "K0"], "rows": [["kaynak.pdf", 2]]}],
    "citations": [{"chunk_id": 1, "source": "kaynak.pdf", "page": 1,
                   "citation": "[Kaynak: kaynak.pdf s.1]"}],
    "dropped": [
        {"section_id": "exec", "text": "Bu sistem GPT-4 kullanır.",
         "reason": "unverified_terms", "score": 0.5487, "terms": ["gpt-4"]},
        {"section_id": "exec", "text": "Bağlanamayan iddia.",
         "reason": "unsupported", "score": None, "terms": []},
    ],
}


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Ham SSE metnini [(event, data), ...] listesine çevirir."""
    events = []
    for block in text.strip("\n").split("\n\n"):
        if not block.strip():
            continue
        event_line, data_line = block.split("\n", 1)
        event = event_line.removeprefix("event: ")
        data = json.loads(data_line.removeprefix("data: "))
        events.append((event, data))
    return events


def _upsert_fake_document(conn, filename: str, n_chunks: int = 2, page=1) -> int:
    """`n_chunks` chunk'lı sahte bir belge yazar, document_id döndürür."""
    chunks = [
        SimpleNamespace(source=filename, page=page, content=f"içerik {i}", via_ocr=False)
        for i in range(n_chunks)
    ]
    embeddings = [[0.1 * (i + 1), 0.2, 0.3] for i in range(n_chunks)]
    return store.upsert_document(
        conn, filename, page_count=1, chunks=chunks, embeddings=embeddings
    )


def _chunk_ids(conn, document_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM chunks WHERE document_id = ? ORDER BY id", (document_id,)
    ).fetchall()
    return [r["id"] for r in rows]


# --------------------------------------------------------------------------- GET (liste)


def test_list_artifacts_empty(client):
    r = client.get("/api/artifacts")
    assert r.status_code == 200
    assert r.json() == []


# --------------------------------------------------------------------------- GET (tekil) / DELETE


def test_get_artifact_not_found(client):
    r = client.get("/api/artifacts/999")
    assert r.status_code == 404
    assert r.json()["code"] == "ARTIFACT_NOT_FOUND"


def test_delete_artifact_not_found(client):
    r = client.delete("/api/artifacts/999")
    assert r.status_code == 404
    assert r.json()["code"] == "ARTIFACT_NOT_FOUND"


def test_delete_artifact_success(app, client):
    conn = app.state.conn
    _upsert_fake_document(conn, "kaynak.pdf")
    artifact_id = create_artifact(
        conn,
        kind="mindmap",
        scope="corpus",
        document_id=None,
        title="Test",
        params={},
        payload={},
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=None,
        generation_ms=10,
        claims=[],
    )
    r = client.delete(f"/api/artifacts/{artifact_id}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert client.get(f"/api/artifacts/{artifact_id}").status_code == 404


# --------------------------------------------------------------------------- citation / is_stale


def test_get_artifact_citation_matches_hit_citation(app, client):
    """Kriter 5: citation biçimi rag/retrieve.py::Hit.citation() ile birebir aynı."""
    conn = app.state.conn
    doc_id = _upsert_fake_document(conn, "belge.pdf", n_chunks=1, page=4)
    chunk_id = _chunk_ids(conn, doc_id)[0]

    bindings = [
        ClaimBinding("/nodes/0", "bağlı iddia", chunk_id, 0.9, "grounded"),
        ClaimBinding("/nodes/1", "bağlanamayan iddia", None, None, "unsupported"),
    ]
    artifact_id = create_artifact(
        conn,
        kind="report",
        scope="corpus",
        document_id=None,
        title="Rapor",
        params={},
        payload={"x": 1},
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=0.5,
        generation_ms=100,
        claims=bindings,
    )

    r = client.get(f"/api/artifacts/{artifact_id}")
    assert r.status_code == 200
    body = r.json()
    claims_by_path = {c["node_path"]: c for c in body["claims"]}

    bound = claims_by_path["/nodes/0"]
    assert bound["source"] == "belge.pdf"
    assert bound["page"] == 4
    assert bound["citation"] == "[Kaynak: belge.pdf s.4]"
    assert bound["score"] == 0.9  # HAM COSINE -- dokunulmamış (AGENTS.md §1.1)

    unbound = claims_by_path["/nodes/1"]
    assert unbound["chunk_id"] is None
    assert unbound["source"] is None
    assert unbound["page"] is None
    assert unbound["citation"] is None

    assert body["unsupported_count"] == 1
    assert "corpus_fingerprint" not in body  # Kriter 6: ham parmak izi yüzeyde YOK
    assert "corpus_fingerprint" not in client.get("/api/artifacts").json()[0]


def test_get_artifact_page_zero_citation_has_no_page_suffix(app, client):
    """`page` yoksa (markdown fixture) -> `[Kaynak: dosya.md]`, sayfa eki yok."""
    conn = app.state.conn
    doc_id = _upsert_fake_document(conn, "notlar.md", n_chunks=1, page=None)
    chunk_id = _chunk_ids(conn, doc_id)[0]
    bindings = [ClaimBinding("/nodes/0", "iddia", chunk_id, 0.6, "grounded")]
    artifact_id = create_artifact(
        conn,
        kind="report",
        scope="corpus",
        document_id=None,
        title="R",
        params={},
        payload={},
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=1.0,
        generation_ms=5,
        claims=bindings,
    )
    r = client.get(f"/api/artifacts/{artifact_id}")
    claim = r.json()["claims"][0]
    assert claim["citation"] == "[Kaynak: notlar.md]"


def test_is_stale_false_then_true_after_corpus_changes(app, client):
    """Kriter 4: artefakt yaz -> is_stale=false; korpus değişir -> is_stale=true,
    ve 200 döner, 409 DEĞİL (artefakt silinmez/yeniden üretilmez, §9.2)."""
    conn = app.state.conn
    _upsert_fake_document(conn, "ilk.pdf")
    fp = store.corpus_fingerprint(conn)
    artifact_id = create_artifact(
        conn,
        kind="mindmap",
        scope="corpus",
        document_id=None,
        title="Harita",
        params={},
        payload={},
        corpus_fingerprint=fp,
        fidelity_score=None,
        generation_ms=1,
        claims=[],
    )

    r1 = client.get(f"/api/artifacts/{artifact_id}")
    assert r1.status_code == 200
    assert r1.json()["is_stale"] is False

    # Korpusu değiştir: yeni belge ekle -> documents satırları değişir, parmak izi değişir.
    _upsert_fake_document(conn, "ikinci.pdf")

    r2 = client.get(f"/api/artifacts/{artifact_id}")
    assert r2.status_code == 200  # 409 DEĞİL
    assert r2.json()["is_stale"] is True

    # GET /api/artifacts (liste) de aynı türetmeyi uygulamalı.
    listed = {a["id"]: a for a in client.get("/api/artifacts").json()}
    assert listed[artifact_id]["is_stale"] is True


# --------------------------------------------------------------------------- POST (SSE)


def test_create_artifact_requires_ready_models(client):
    r = client.post("/api/artifacts", json={"kind": "mindmap", "scope": "corpus"})
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_WARMING"
    # Akış hiç açılmadı: düz JSON hata (SSE değil).
    assert not r.headers["content-type"].startswith("text/event-stream")


def test_create_artifact_unknown_document_returns_404(ready_client, app):
    conn = app.state.conn
    _upsert_fake_document(conn, "var.pdf")

    r = ready_client.post(
        "/api/artifacts",
        json={"kind": "mindmap", "scope": "document", "document_id": 999},
    )
    assert r.status_code == 404
    assert r.json()["code"] == "DOCUMENT_NOT_FOUND"
    assert not r.headers["content-type"].startswith("text/event-stream")


def test_create_artifact_missing_document_id_returns_404(ready_client):
    r = ready_client.post("/api/artifacts", json={"kind": "mindmap", "scope": "document"})
    assert r.status_code == 404
    assert r.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_create_artifact_insufficient_corpus_returns_422(ready_client):
    """Kriter 2: INSUFFICIENT_CORPUS akış açılmadan ÖNCE, ayrı olarak doğrulanır."""
    r = ready_client.post("/api/artifacts", json={"kind": "mindmap", "scope": "corpus"})
    assert r.status_code == 422
    assert r.json()["code"] == "INSUFFICIENT_CORPUS"
    assert not r.headers["content-type"].startswith("text/event-stream")


def test_create_artifact_streams_stage_then_generation_failed(ready_client, app):
    """Kriter 3: `stage:selection` ve `stage:clustering` GERÇEKTEN yayılır,
    ardından `event:error` + `GENERATION_FAILED` gelir (Faz 1'de registry
    boş -- rag/artifacts/base.py §9.5)."""
    conn = app.state.conn
    _upsert_fake_document(conn, "a.pdf", n_chunks=2)

    r = ready_client.post("/api/artifacts", json={"kind": "mindmap", "scope": "corpus"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(r.text)
    kinds = [e for e, _ in events]
    stages = [d["stage"] for e, d in events if e == "stage"]

    # generate_artifact 1-2-3. adımlarda selection/clustering/generation
    # stage'lerini sırayla yayar (generation, registry boş olduğu için
    # hemen ardından GenerationFailedError'a düşer).
    assert stages[:2] == ["selection", "clustering"]
    assert kinds[0] == "stage"
    assert kinds[-1] == "error"
    assert events[-1][1]["code"] == "GENERATION_FAILED"
    # complete VE error birden gelmez.
    assert kinds.count("complete") == 0
    assert kinds.count("error") == 1


# --------------------------------------------------------------------------- dropped_count (§10.11)


def _seed_report(conn, payload=None, claims=()):
    return create_artifact(
        conn,
        kind="report",
        scope="corpus",
        document_id=None,
        title="Korpus Raporu",
        params={},
        payload=_REPORT_PAYLOAD if payload is None else payload,
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=0.9,
        generation_ms=1000,
        claims=list(claims),
    )


def test_get_artifact_dropped_count_payloaddan_turetilir(app, client):
    """§10.11: yeni sütun YOK -- len(payload["dropped"]). unsupported_count'tan
    AYRI bir sayıdır (§10.6): burada biri 2, öbürü 1."""
    conn = app.state.conn
    doc_id = _upsert_fake_document(conn, "kaynak.pdf")
    chunk_id = _chunk_ids(conn, doc_id)[0]
    claims = [
        ClaimBinding("/sections/0/paragraphs/0/sentences/0", "Rapora giren cümle.",
                     chunk_id, 0.72, "grounded"),
        ClaimBinding("/dropped/0", "Bu sistem GPT-4 kullanır.", chunk_id, 0.5487, "grounded"),
        ClaimBinding("/dropped/1", "Bağlanamayan iddia.", None, None, "unsupported"),
    ]
    artifact_id = _seed_report(conn, claims=claims)

    body = client.get(f"/api/artifacts/{artifact_id}").json()
    assert body["dropped_count"] == 2
    assert body["unsupported_count"] == 1


def test_dropped_count_dropped_tasimayan_payloadda_sifir(app, client):
    """mindmap/quiz gibi `dropped` taşımayan artefaktlarda 0 -- KeyError değil."""
    conn = app.state.conn
    _upsert_fake_document(conn, "kaynak.pdf")
    artifact_id = create_artifact(
        conn, kind="mindmap", scope="corpus", document_id=None, title="H",
        params={}, payload={"nodes": []},
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=None, generation_ms=1, claims=[],
    )
    assert client.get(f"/api/artifacts/{artifact_id}").json()["dropped_count"] == 0


def test_complete_olayi_dropped_count_tasir(ready_client, app, monkeypatch):
    """§10.11: `complete` olayına ADDITIVE eklenir -- unsupported_count
    kaldırılmaz, yeniden adlandırılmaz."""
    conn = app.state.conn
    _upsert_fake_document(conn, "a.pdf", n_chunks=2)

    class _Dummy:
        kind = "report"

        def generate(self, ctx):
            return base.GeneratedArtifact(
                title="Korpus Raporu",
                payload=_REPORT_PAYLOAD,
                claims=[
                    ("/sections/0/paragraphs/0/sentences/0", "Rapora giren cümle."),
                    ("/dropped/0", "Bu sistem GPT-4 kullanır."),
                    ("/dropped/1", "Bağlanamayan iddia."),
                ],
            )

    monkeypatch.setitem(base._registry, "report", _Dummy())
    monkeypatch.setattr(
        "rag.models.embed_texts",
        lambda texts, is_query=False: [[1.0, 0.0, 0.0] for _ in texts],
    )

    r = ready_client.post("/api/artifacts", json={"kind": "report", "scope": "corpus"})
    events = _parse_sse(r.text)
    assert [e for e, _ in events][-1] == "complete"
    complete = events[-1][1]
    assert complete["dropped_count"] == 2
    assert "unsupported_count" in complete
    assert set(complete) == {
        "artifact_id", "fidelity_score", "generation_ms",
        "unsupported_count", "dropped_count",
    }


# --------------------------------------------------------------------------- export (§10.11)


def test_export_markdown_basarili(app, client):
    conn = app.state.conn
    artifact_id = _seed_report(conn)

    r = client.get(f"/api/artifacts/{artifact_id}/export?format=md")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    assert r.headers["content-disposition"] == f'attachment; filename="report-{artifact_id}.md"'

    md = r.text
    assert "## Yönetici Özeti" in md
    assert "Rapora giren cümle." in md
    # §10.12: düşürülen iddianın METNİ değil, yalnızca SAYISI geçer.
    assert "GPT-4" not in md
    assert "2 iddia" in md
    # AGENTS.md §1.2: harici kaynak yok.
    assert "http://" not in md and "https://" not in md


def test_export_bilinmeyen_artefakt_404(client):
    r = client.get("/api/artifacts/999/export?format=md")
    assert r.status_code == 404
    assert r.json()["code"] == "ARTIFACT_NOT_FOUND"


def test_export_gecersiz_format_422(app, client):
    """`format=html` §10.15'te reddedildi -- FastAPI doğrulaması 422 verir."""
    conn = app.state.conn
    artifact_id = _seed_report(conn)
    assert client.get(f"/api/artifacts/{artifact_id}/export?format=html").status_code == 422
    assert client.get(f"/api/artifacts/{artifact_id}/export").status_code == 422


def test_export_bayat_artefakt_200(app, client):
    """Export bir OKUMA işlemidir: bayat artefakt 409 değil 200 döner (§9.8)."""
    conn = app.state.conn
    artifact_id = _seed_report(conn)
    _upsert_fake_document(conn, "sonradan.pdf")  # korpus değişti -> is_stale

    assert client.get(f"/api/artifacts/{artifact_id}").json()["is_stale"] is True
    assert client.get(f"/api/artifacts/{artifact_id}/export?format=md").status_code == 200
