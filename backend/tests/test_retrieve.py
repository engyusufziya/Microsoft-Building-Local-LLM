"""`/api/retrieve` -- min_score=None tuzağı, passed_threshold türetimi."""

from __future__ import annotations

import rag.retrieve as retrieve_module
from rag import config
from rag.retrieve import Hit


def test_retrieve_empty_query_returns_400(client):
    r = client.post("/api/retrieve", json={"question": ""})
    assert r.status_code == 400
    assert r.json()["code"] == "EMPTY_QUERY"


def test_retrieve_model_warming_returns_503(client):
    r = client.post("/api/retrieve", json={"question": "RAG nedir?"})
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_WARMING"


def test_retrieve_calls_get_top_chunks_with_min_score_none(ready_client, monkeypatch):
    """FEATURE_SPEC §0.1: /api/retrieve KASITLI olarak min_score=None ile
    çağırmalı -- config.MIN_SCORE DEĞİL. Bunu unutmak sessiz bozulmaya yol
    açar (§0.1 uyarısı), bu yüzden None'ı `is` ile doğruluyoruz."""
    captured = {}

    def fake_get_top_chunks(query, k, min_score, conn):
        captured["min_score"] = min_score
        captured["query"] = query
        return []

    monkeypatch.setattr(retrieve_module, "get_top_chunks", fake_get_top_chunks)

    r = ready_client.post("/api/retrieve", json={"question": "İstanbul'un nüfusu kaçtır?"})
    assert r.status_code == 200
    assert captured["min_score"] is None
    assert captured["query"] == "İstanbul'un nüfusu kaçtır?"


def test_retrieve_response_includes_below_threshold_hits_with_flag(ready_client, monkeypatch):
    """Inspector eşik altındakileri de görmeli: get_top_chunks filtresiz
    dönerken response'daki passed_threshold bayrağı skor >= config.MIN_SCORE
    olarak GÖRSEL eleme yapmalı."""
    hits = [
        Hit(score=0.83, source="belge_01_rag_nedir.md", page=0, content="a", via_ocr=False),
        Hit(score=0.20, source="belge_02_embedding_ve_benzerlik.md", page=0, content="b", via_ocr=False),
    ]

    monkeypatch.setattr(
        retrieve_module, "get_top_chunks", lambda query, k, min_score, conn: hits
    )

    r = ready_client.post("/api/retrieve", json={"question": "RAG nedir?"})
    assert r.status_code == 200
    body = r.json()
    assert body["threshold"] == config.MIN_SCORE
    assert len(body["hits"]) == 2
    assert body["hits"][0]["score"] == 0.83
    assert body["hits"][0]["passed_threshold"] is True
    assert body["hits"][1]["score"] == 0.20
    assert body["hits"][1]["passed_threshold"] is False
    assert body["hits"][1]["citation"] == "[Kaynak: belge_02_embedding_ve_benzerlik.md]"


def test_retrieve_page_zero_for_markdown_fixture(ready_client, monkeypatch):
    hits = [Hit(score=0.9, source="belge_01.md", page=0, content="a", via_ocr=False)]
    monkeypatch.setattr(
        retrieve_module, "get_top_chunks", lambda query, k, min_score, conn: hits
    )
    body = ready_client.post("/api/retrieve", json={"question": "x"}).json()
    assert body["hits"][0]["page"] == 0
