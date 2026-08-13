"""`/api/chat` -- SSE akışı, üç `reason` dalı, min_score tuzağı, streaming guard.

docs/FEATURE_SPEC.md §1.2, §3.1, §3.2, §3.3.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import rag.answer as answer_module
import rag.models as models_module
import rag.retrieve as retrieve_module
from rag import config
from rag.retrieve import Hit

from .test_documents import _parse_sse, _upsert_fake_document  # noqa: F401 (reuse helper)


def _hit(score: float, source: str = "belge_01_rag_nedir.md", page: int = 0) -> Hit:
    return Hit(score=score, source=source, page=page, content="içerik", via_ocr=False)


# --------------------------------------------------------------------------- ön-kontroller


def test_chat_empty_query_returns_400(client):
    r = client.post("/api/chat", json={"question": "   "})
    assert r.status_code == 400
    assert r.json()["code"] == "EMPTY_QUERY"


def test_chat_model_warming_returns_503_before_no_documents_check(client):
    """model_status hâlâ 'warming' iken -- korpus da boş olsa -- 503
    MODEL_WARMING dönmeli, 409 NO_DOCUMENTS değil (kontrol sırası)."""
    r = client.post("/api/chat", json={"question": "RAG nedir?"})
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_WARMING"


def test_chat_no_documents_returns_409(ready_client):
    r = ready_client.post("/api/chat", json={"question": "RAG nedir?"})
    assert r.status_code == 409
    assert r.json()["code"] == "NO_DOCUMENTS"


# --------------------------------------------------------------------------- min_score tuzağı


def test_chat_passes_config_min_score_explicitly(ready_client, app, monkeypatch):
    """FEATURE_SPEC §0.1: /api/chat, answer_query_stream'i min_score=config.MIN_SCORE
    ile çağırmalı (None DEĞİL, config'in kendisi)."""
    _upsert_fake_document(app.state.conn, "belge_01_rag_nedir.md", via_ocr=False)

    captured = {}

    def fake_stream(question, k=None, min_score=None, model=None, conn=None):
        captured["min_score"] = min_score
        yield answer_module.RetrievalEvent(
            hits=[], threshold=min_score, passed_count=0, rejected_count=0, elapsed_ms=1
        )
        yield answer_module.DoneEvent(
            answered=False, reason="below_threshold", sources=[], elapsed_ms=2, token_count=0
        )

    monkeypatch.setattr(answer_module, "answer_query_stream", fake_stream)

    r = ready_client.post("/api/chat", json={"question": "RAG nedir?"})
    assert r.status_code == 200
    assert captured["min_score"] == config.MIN_SCORE
    assert captured["min_score"] is not None


# --------------------------------------------------------------------------- üç `reason` dalı


def test_chat_normal_answer_streams_tokens_then_done(ready_client, app, monkeypatch):
    _upsert_fake_document(app.state.conn, "belge_01_rag_nedir.md", via_ocr=False)

    hits = [_hit(0.83), _hit(0.30)]  # biri geçti, biri elendi

    def fake_stream(question, k=None, min_score=None, model=None, conn=None):
        yield answer_module.RetrievalEvent(
            hits=hits, threshold=0.45, passed_count=1, rejected_count=1, elapsed_ms=10
        )
        yield answer_module.TokenEvent(text="RAG ")
        yield answer_module.TokenEvent(text="üç adımdan oluşur.")
        yield answer_module.DoneEvent(
            answered=True,
            reason=None,
            sources=["[Kaynak: belge_01_rag_nedir.md]"],
            elapsed_ms=50,
            token_count=2,
        )

    monkeypatch.setattr(answer_module, "answer_query_stream", fake_stream)

    r = ready_client.post("/api/chat", json={"question": "RAG kaç adımdan oluşur?"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    kinds = [e for e, _ in events]
    assert kinds == ["retrieval", "token", "token", "done"]

    retrieval = events[0][1]
    assert retrieval["threshold"] == 0.45
    assert retrieval["passed_count"] == 1
    assert retrieval["rejected_count"] == 1
    # passed_threshold backend'de hesaplanır (score >= threshold)
    assert retrieval["hits"][0]["passed_threshold"] is True
    assert retrieval["hits"][1]["passed_threshold"] is False

    done = events[-1][1]
    assert done["answered"] is True
    assert done["reason"] is None
    assert done["sources"] == ["[Kaynak: belge_01_rag_nedir.md]"]


def test_chat_below_threshold_short_circuits_without_tokens(ready_client, app, monkeypatch):
    _upsert_fake_document(app.state.conn, "belge_01_rag_nedir.md", via_ocr=False)

    def fake_stream(question, k=None, min_score=None, model=None, conn=None):
        yield answer_module.RetrievalEvent(
            hits=[_hit(0.20)], threshold=0.45, passed_count=0, rejected_count=1, elapsed_ms=5
        )
        yield answer_module.DoneEvent(
            answered=False, reason="below_threshold", sources=[], elapsed_ms=6, token_count=0
        )

    monkeypatch.setattr(answer_module, "answer_query_stream", fake_stream)

    r = ready_client.post("/api/chat", json={"question": "İstanbul'un nüfusu kaçtır?"})
    events = _parse_sse(r.text)
    kinds = [e for e, _ in events]
    assert kinds == ["retrieval", "done"]  # token YOK
    assert events[-1][1]["reason"] == "below_threshold"
    assert events[-1][1]["answered"] is False


def test_chat_llm_refused_still_streams_raw_tokens(ready_client, app, monkeypatch):
    """FEATURE_SPEC §3.2: llm_refused'ta akış sırasında modelin GERÇEK
    çıktısı (Türkçe ret metni) token olarak gider; frontend `done` gelince
    değiştirir. Backend bunu KENDİSİ değiştirmemeli."""
    _upsert_fake_document(app.state.conn, "belge_01_rag_nedir.md", via_ocr=False)

    def fake_stream(question, k=None, min_score=None, model=None, conn=None):
        yield answer_module.RetrievalEvent(
            hits=[_hit(0.74)], threshold=0.45, passed_count=1, rejected_count=0, elapsed_ms=8
        )
        yield answer_module.TokenEvent(text=config.NO_ANSWER_TEXT)
        yield answer_module.DoneEvent(
            answered=False, reason="llm_refused", sources=[], elapsed_ms=40, token_count=1
        )

    monkeypatch.setattr(answer_module, "answer_query_stream", fake_stream)

    r = ready_client.post("/api/chat", json={"question": "Foundry Local'da fine-tuning nasıl yapılır?"})
    events = _parse_sse(r.text)
    kinds = [e for e, _ in events]
    assert kinds == ["retrieval", "token", "done"]
    assert events[1][1]["text"] == config.NO_ANSWER_TEXT  # ham metin değiştirilmedi
    assert events[-1][1]["reason"] == "llm_refused"
    assert events[-1][1]["sources"] == []


# --------------------------------------------------------------------------- streaming guard (rag/answer.py, gerçek kod)


def test_chat_streaming_guard_survives_empty_choices_chunks(ready_client, app, monkeypatch):
    """FEATURE_SPEC §3.3: Foundry Local akışında ara sıra boş `chunk.choices`
    gelir; guard olmadan IndexError patlar. Burada `answer_query_stream`
    MONKEYPATCH'LENMEZ (gerçek rag/answer.py kodu çalışır) -- yalnızca daha alt
    seviyedeki `models.get_chat_client` ve `retrieve.get_top_chunks` sahtelenir.
    Bu test guard'ın (rag katmanında) çalıştığını backend'in gerçek isteğiyle
    uçtan uca doğrular."""
    _upsert_fake_document(app.state.conn, "belge_01_rag_nedir.md", via_ocr=False)

    class _Delta:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.delta = _Delta(content)

    class _Chunk:
        def __init__(self, content=None, empty=False):
            self.choices = [] if empty else [_Choice(content)]

    class _FakeChatClient:
        def complete_streaming_chat(self, messages):
            return iter(
                [
                    _Chunk(empty=True),  # ÖLÇÜLDÜ davranışı: boş chunk.choices
                    _Chunk("Merhaba"),
                    _Chunk(empty=True),
                    _Chunk(" dünya"),
                ]
            )

    def fake_get_top_chunks(query, k=None, min_score=None, conn=None):
        # min_score=None ile çağrıldığında (retrieval her zaman filtresiz
        # çalışır, answer_query_stream kendi içinde filtreler) eşik üstü tek
        # sonuç döner.
        return [_hit(0.9)]

    monkeypatch.setattr(retrieve_module, "get_top_chunks", fake_get_top_chunks)
    monkeypatch.setattr(models_module, "get_chat_client", lambda alias=None: _FakeChatClient())

    r = ready_client.post("/api/chat", json={"question": "RAG kaç adımdan oluşur?"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    kinds = [e for e, _ in events]
    assert "error" not in kinds  # IndexError patlasaydı burada error event'i görürdük
    token_texts = [d["text"] for k, d in events if k == "token"]
    assert token_texts == ["Merhaba", " dünya"]
    done = events[-1][1]
    assert done["answered"] is True
    assert done["reason"] is None
