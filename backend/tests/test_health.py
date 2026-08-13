"""`/api/health` -- warmup durumu, config değerlerinin doğru servis edilmesi."""

from __future__ import annotations

from rag import config


def test_health_reports_warming_before_models_load(client):
    """RAG_BACKEND_SKIP_WARMUP=1 sayesinde warmup görevi hiç başlamaz;
    status sonsuza kadar "warming" kalır -- gerçek model yüklenmeden
    doğrulanabilen tek durum budur."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "warming"


def test_health_config_values_come_from_rag_config(client):
    body = client.get("/api/health").json()
    assert body["chat_model"] == config.CHAT_MODEL
    assert body["embedding_model"] == config.EMBEDDING_MODEL
    assert body["min_score"] == config.MIN_SCORE
    assert body["top_k"] == config.TOP_K
    assert body["document_count"] == 0
    assert body["chunk_count"] == 0
    assert isinstance(body["ocr_available"], bool)


def test_health_reports_ready_once_status_flipped(ready_client):
    body = ready_client.get("/api/health").json()
    assert body["status"] == "ready"
