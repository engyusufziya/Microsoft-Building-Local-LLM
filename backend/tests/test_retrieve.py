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


# --------------------------------------------------- §13.4 çekmece künyesi


def test_hit_kunye_alanlari_api_yuzeyine_cikar(ready_client, monkeypatch):
    """`chunk_id/chunk_index/chunk_total` API'ye ULAŞMALI (§13.4).

    Çekmecenin `s.4 · bölüm 12/94 · benzerlik 0.71` künyesi bu üç alana
    dayanıyor. Spec'in ilk hâli "mevcut veriden gelir" diyordu ama gelmiyordu:
    `Hit` bu alanları taşımıyordu. Bu test o boşluğun geri açılmasını
    engelliyor.
    """
    monkeypatch.setattr(
        retrieve_module,
        "get_top_chunks",
        lambda *a, **k: [
            Hit(
                score=0.71,
                source="belge.pdf",
                page=4,
                content="içerik",
                chunk_id=57,
                chunk_index=12,
                chunk_total=94,
            )
        ],
    )

    hit = ready_client.post("/api/retrieve", json={"question": "soru"}).json()["hits"][0]

    assert (hit["chunk_id"], hit["chunk_index"], hit["chunk_total"]) == (57, 12, 94)
    # Künye alanları eklendi diye skor DEĞİŞMEDİ -- ham cosine (AGENTS.md §1.1).
    assert hit["score"] == 0.71


def test_kunye_alanlari_skoru_ve_elemeyi_ETKILEMEZ(ready_client, monkeypatch):
    """Künye yalnızca gösterim: passed_threshold hâlâ SADECE skordan türer."""
    monkeypatch.setattr(
        retrieve_module,
        "get_top_chunks",
        lambda *a, **k: [
            Hit(score=config.MIN_SCORE - 0.01, source="a.pdf", page=1, content="x",
                chunk_id=1, chunk_index=1, chunk_total=1),
            Hit(score=config.MIN_SCORE + 0.01, source="b.pdf", page=2, content="y",
                chunk_id=None, chunk_index=None, chunk_total=None),
        ],
    )

    hits = ready_client.post("/api/retrieve", json={"question": "soru"}).json()["hits"]

    # Künyesi DOLU olan eşiğin altında, künyesi BOŞ olan üstünde: bayrak
    # künyeye değil skora bakıyor.
    assert [h["passed_threshold"] for h in hits] == [False, True]


def test_chunk_sirasi_belge_ICINDE_sayilir(app, client):
    """`chunk_index` korpus genelinde değil BELGE içinde 1'den başlar."""
    from types import SimpleNamespace

    from rag import store

    def chunks(name, n):
        return [
            SimpleNamespace(source=name, page=1, content=f"{name}-{i}", via_ocr=False)
            for i in range(n)
        ]

    conn = app.state.conn
    store.upsert_document(conn, "ilk.pdf", 1, chunks("ilk", 3), [[0.1, 0.2, 0.3]] * 3)
    store.upsert_document(conn, "ikinci.pdf", 1, chunks("ikinci", 2), [[0.4, 0.5, 0.6]] * 2)

    _, meta = store.load_matrix(conn)
    by_source = {}
    for m in meta:
        by_source.setdefault(m["source"], []).append((m["chunk_index"], m["chunk_total"]))

    assert by_source["ilk"] == [(1, 3), (2, 3), (3, 3)]
    assert by_source["ikinci"] == [(1, 2), (2, 2)]
