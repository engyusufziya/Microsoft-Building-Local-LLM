"""`/api/quiz/*` -- deneme gönderimi ve geçmişi (FEATURE_SPEC.md §12.10).

Foundry Local'a HİÇ dokunulmaz: short_answer içeren quiz'lerde `embed_texts`
monkeypatch'lenir. `backend/` ince kalır -- puanlamanın kendisi
rag/artifacts/quiz.py'de test edilir (test_artifacts_quiz.py); burada ölçülen
HTTP yüzeyi: durum kodları, şema alanları, kalıcılaştırma ve kilit koşulu.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from rag import store
from rag.artifacts.fidelity import ClaimBinding
from rag.artifacts.store import create_artifact


def _upsert_fake_document(conn, filename: str = "a.md") -> None:
    """artifact_claims.chunk_id FOREIGN KEY taşıyor -- iddia yazabilmek için
    korpusta gerçek bir chunk olmalı (PRAGMA foreign_keys açık)."""
    store.upsert_document(
        conn, filename, page_count=1,
        chunks=[SimpleNamespace(source=filename, page=1, content="içerik", via_ocr=False)],
        embeddings=[[0.1, 0.2, 0.3]],
    )


def _unit(angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


def _question(qid, qtype, answer, choices=()):
    return {
        "id": qid, "type": qtype, "topic_id": 0, "prompt": "Soru?",
        "choices": list(choices), "answer": answer, "chunk_id": 1,
        "source": "a.md", "citation": "[Kaynak: a.md s.1]",
        "evidence": "Korpustan gelen gerekçe cümlesi.",
    }


_QUIZ_PAYLOAD = {
    "kind": "quiz",
    "questions": [
        _question("q0", "multiple_choice", "SQLite", ["SQLite", "Foundry"]),
        _question("q1", "true_false", "false", ["true", "false"]),
    ],
    "dropped": [],
}

_QUIZ_WITH_SHORT_ANSWER = {
    "kind": "quiz",
    "questions": [
        _question("q0", "fill_blank", "SQLite"),
        _question("q1", "short_answer", "Vektörler yerel veritabanında saklanır."),
    ],
    "dropped": [],
}


def _seed_quiz(conn, payload=None):
    _upsert_fake_document(conn)
    return create_artifact(
        conn,
        kind="quiz",
        scope="corpus",
        document_id=None,
        title="Korpus Quiz",
        params={},
        payload=payload or _QUIZ_PAYLOAD,
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=1.0,
        generation_ms=1234,
        claims=[ClaimBinding("/questions/0/evidence", "Korpustan gelen gerekçe cümlesi.",
                             1, 0.83, "grounded")],
    )


def _seed_report(conn):
    return create_artifact(
        conn, kind="report", scope="corpus", document_id=None, title="Korpus Raporu",
        params={}, payload={"kind": "report", "sections": [], "tables": [],
                            "citations": [], "dropped": []},
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=None, generation_ms=1, claims=[],
    )


# --------------------------------------------------------------------------- POST attempt


def test_attempt_deterministik_puanlar_ve_kaydeder(client, app):
    quiz_id = _seed_quiz(app.state.conn)

    r = client.post(
        f"/api/quiz/{quiz_id}/attempt",
        json={"answers": {"q0": "sqlite", "q1": "true"}, "started_at": "2026-08-16T10:00:00"},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["artifact_id"] == quiz_id
    assert body["correct_count"] == 1
    assert body["deterministic_total"] == 2
    assert body["similarity_total"] == 0
    assert body["score"] == pytest.approx(0.5)
    assert [x["correct"] for x in body["results"]] == [True, False]
    assert body["results"][0]["citation"] == "[Kaynak: a.md s.1]"
    assert body["results"][0]["evidence"] == "Korpustan gelen gerekçe cümlesi."
    assert body["results"][0]["similarity"] is None

    # Deneme KALICI: geçmişte görünüyor ve başlangıç zamanı istemciden geldi.
    history = client.get(f"/api/quiz/{quiz_id}/attempts").json()
    assert len(history) == 1
    assert history[0]["id"] == body["attempt_id"]
    assert history[0]["started_at"] == "2026-08-16T10:00:00"
    assert history[0]["score"] == pytest.approx(0.5)


def test_attempt_started_at_yoksa_sunucu_saati_kullanilir(client, app):
    quiz_id = _seed_quiz(app.state.conn)
    r = client.post(f"/api/quiz/{quiz_id}/attempt", json={"answers": {}})
    assert r.status_code == 200

    history = client.get(f"/api/quiz/{quiz_id}/attempts").json()
    assert history[0]["started_at"] == r.json()["completed_at"]


def test_attempt_model_gerektirmeyen_quiz_warming_iken_de_calisir(client, app):
    """Deterministik quiz'de embedding'e ihtiyaç yok; modeller ısınırken bile
    deneme gönderilebilmeli (`client` fixture'ında model_status "warming")."""
    quiz_id = _seed_quiz(app.state.conn)
    assert app.state.model_status == "warming"

    r = client.post(f"/api/quiz/{quiz_id}/attempt", json={"answers": {"q0": "SQLite"}})
    assert r.status_code == 200
    assert r.json()["correct_count"] == 1


def test_attempt_short_answer_varsa_model_hazir_degilse_503(client, app):
    quiz_id = _seed_quiz(app.state.conn, _QUIZ_WITH_SHORT_ANSWER)
    r = client.post(f"/api/quiz/{quiz_id}/attempt", json={"answers": {"q1": "cevap"}})
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_WARMING"


def test_attempt_short_answer_benzerligi_dondurur(ready_client, app, monkeypatch):
    """§12.8: `correct` None kalır, `similarity` HAM COSINE'dır ve skora
    KATILMAZ."""
    quiz_id = _seed_quiz(app.state.conn, _QUIZ_WITH_SHORT_ANSWER)
    vectors = {
        "kullanıcı cevabı": _unit(60),
        "Vektörler yerel veritabanında saklanır.": _unit(0),
    }
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [vectors[t] for t in texts]
    )

    r = ready_client.post(
        f"/api/quiz/{quiz_id}/attempt",
        json={"answers": {"q0": "SQLite", "q1": "kullanıcı cevabı"}},
    )
    assert r.status_code == 200
    body = r.json()

    short = body["results"][1]
    assert short["correct"] is None
    assert short["similarity"] == pytest.approx(0.5, abs=1e-6)  # cos 60°
    assert body["deterministic_total"] == 1
    assert body["similarity_total"] == 1
    assert body["score"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- hata sözleşmesi


def test_bilinmeyen_quiz_404(client):
    assert client.post("/api/quiz/999/attempt", json={"answers": {}}).status_code == 404
    r = client.get("/api/quiz/999/attempts")
    assert r.status_code == 404
    assert r.json()["code"] == "ARTIFACT_NOT_FOUND"


def test_rapor_kimligiyle_quiz_endpointi_404(client, app):
    """Rapor kimliğiyle çağırmak "quiz {id}" kaynağının olmadığı anlamına
    gelir -- yeni bir hata kodu açılmaz (§2.2 listesi additive kalır)."""
    report_id = _seed_report(app.state.conn)
    r = client.post(f"/api/quiz/{report_id}/attempt", json={"answers": {}})
    assert r.status_code == 404
    assert r.json()["code"] == "ARTIFACT_NOT_FOUND"


def test_attempts_bos_liste_hata_degil(client, app):
    quiz_id = _seed_quiz(app.state.conn)
    r = client.get(f"/api/quiz/{quiz_id}/attempts")
    assert r.status_code == 200
    assert r.json() == []


def test_denemeler_en_yeni_once_siralanir(client, app):
    quiz_id = _seed_quiz(app.state.conn)
    for _ in range(3):
        client.post(f"/api/quiz/{quiz_id}/attempt", json={"answers": {}})
    ids = [a["id"] for a in client.get(f"/api/quiz/{quiz_id}/attempts").json()]
    assert ids == sorted(ids, reverse=True)


def test_artefakt_silinince_denemeler_de_gider(client, app):
    """quiz_attempts.artifact_id ON DELETE CASCADE (PRAGMA foreign_keys açık)."""
    conn = app.state.conn
    quiz_id = _seed_quiz(conn)
    client.post(f"/api/quiz/{quiz_id}/attempt", json={"answers": {}})

    assert client.delete(f"/api/artifacts/{quiz_id}").status_code == 200
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM quiz_attempts WHERE artifact_id = ?", (quiz_id,)
    ).fetchone()
    assert rows["n"] == 0
