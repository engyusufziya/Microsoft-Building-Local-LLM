"""`/api/chat` -- soru sor, SSE (`retrieval` -> `token`* -> `done`).

docs/FEATURE_SPEC.md §1.2, §2, §3.1, §3.2, §3.3.

DİKKAT (§0.1 min_score tuzağı): `answer.answer_query_stream` çağrılırken
`min_score=config.MIN_SCORE` AÇIKÇA geçilir. `rag.answer.answer_query_stream`
kendi içinde `None` -> `config.MIN_SCORE` çevrimini zaten yapıyor olsa da,
burada açık geçmek niyeti kodda görünür kılar ve motor davranışı değişirse
(varsayılan mantık kaldırılırsa) backend sessizce bozulmaz.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from rag import answer, config, store
from rag.retrieve import Hit

from .. import schemas
from ..errors import ApiError
from ..sse import sse_event

router = APIRouter(tags=["chat"])


def _require_ready(request: Request) -> None:
    if request.app.state.model_status != "ready":
        raise ApiError(503, "MODEL_WARMING", "Modeller henüz yüklenmedi.")


def _hit_to_dict(hit: Hit, threshold: float) -> dict:
    return {
        "score": hit.score,
        "source": hit.source,
        "page": hit.page or 0,
        "content": hit.content,
        "via_ocr": hit.via_ocr,
        "citation": hit.citation(),
        "passed_threshold": hit.score >= threshold,
    }


@router.post("/chat")
async def chat_endpoint(body: schemas.ChatRequest, request: Request) -> StreamingResponse:
    question = (body.question or "").strip()
    if not question:
        raise ApiError(400, "EMPTY_QUERY", "Soru boş olamaz.")

    _require_ready(request)

    conn = request.app.state.conn
    if not store.list_documents(conn):
        raise ApiError(409, "NO_DOCUMENTS", "Korpus boş, önce belge yükleyin.")

    lock: asyncio.Lock = request.app.state.model_lock

    async def event_stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        q: "asyncio.Queue[Any]" = asyncio.Queue()
        _DONE = object()

        def run() -> None:
            try:
                # Kasıtlı: min_score AÇIKÇA config.MIN_SCORE -- bkz. modül docstring'i.
                for event in answer.answer_query_stream(
                    question, k=body.k, min_score=config.MIN_SCORE, conn=conn
                ):
                    loop.call_soon_threadsafe(q.put_nowait, ("event", event))
            except Exception as exc:  # pragma: no cover - beklenmeyen motor hatası
                loop.call_soon_threadsafe(q.put_nowait, ("error", str(exc)))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, _DONE)

        async with lock:
            threading.Thread(target=run, daemon=True).start()
            while True:
                item = await q.get()
                if item is _DONE:
                    break

                kind = item[0]
                if kind == "error":
                    yield sse_event("error", {"code": "INTERNAL", "message": item[1]})
                    return

                event = item[1]
                if isinstance(event, answer.RetrievalEvent):
                    yield sse_event(
                        "retrieval",
                        {
                            "hits": [_hit_to_dict(h, event.threshold) for h in event.hits],
                            "threshold": event.threshold,
                            "passed_count": event.passed_count,
                            "rejected_count": event.rejected_count,
                            "elapsed_ms": event.elapsed_ms,
                            # Additive alan (rag/query_router.py). Eski
                            # istemciler yok sayar; Inspector "summarize"
                            # modunda skor rozetlerini gizlemek için kullanır.
                            "mode": event.mode,
                        },
                    )
                elif isinstance(event, answer.TokenEvent):
                    yield sse_event("token", {"text": event.text})
                elif isinstance(event, answer.DoneEvent):
                    yield sse_event(
                        "done",
                        {
                            "answered": event.answered,
                            "reason": event.reason,
                            "sources": event.sources,
                            "elapsed_ms": event.elapsed_ms,
                            "token_count": event.token_count,
                        },
                    )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
