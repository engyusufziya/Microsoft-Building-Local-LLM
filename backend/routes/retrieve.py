"""`/api/retrieve` -- yalnızca retrieval, LLM'siz (docs/FEATURE_SPEC.md §2, §4.3).

DİKKAT (§0.1 min_score tuzağı): `retrieve.get_top_chunks` KASITLI olarak
`min_score=None` ile çağrılır -- eşik altındaki chunk'lar da dönmeli ki
Inspector "neyin neden elendiğini" gösterebilsin. Eleme yalnızca
`passed_threshold` bayrağıyla GÖRSEL olarak yapılır, retrieval'da değil.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request

from rag import config
from rag import retrieve as rag_retrieve

from .. import schemas
from ..errors import ApiError

router = APIRouter(tags=["retrieve"])


def _require_ready(request: Request) -> None:
    if request.app.state.model_status != "ready":
        raise ApiError(503, "MODEL_WARMING", "Modeller henüz yüklenmedi.")


@router.post("/retrieve", response_model=schemas.RetrieveResponse)
async def retrieve_endpoint(
    body: schemas.RetrieveRequest, request: Request
) -> schemas.RetrieveResponse:
    question = (body.question or "").strip()
    if not question:
        raise ApiError(400, "EMPTY_QUERY", "Soru boş olamaz.")

    _require_ready(request)

    conn = request.app.state.conn
    lock: asyncio.Lock = request.app.state.model_lock
    threshold = config.MIN_SCORE

    t0 = time.monotonic()
    async with lock:
        # Kasıtlı: min_score=None (bkz. modül docstring'i). get_top_chunks
        # sorgu embed etmek için modeli çağırır -> kilit altında ve worker
        # thread'de (event loop'u bloklamamak için).
        hits = await asyncio.to_thread(
            rag_retrieve.get_top_chunks, question, body.k, None, conn
        )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return schemas.RetrieveResponse(
        hits=[
            schemas.ChunkHit(
                score=h.score,
                source=h.source,
                page=h.page or 0,
                content=h.content,
                via_ocr=h.via_ocr,
                citation=h.citation(),
                passed_threshold=h.score >= threshold,
                chunk_id=h.chunk_id,
                chunk_index=h.chunk_index,
                chunk_total=h.chunk_total,
            )
            for h in hits
        ],
        threshold=threshold,
        elapsed_ms=elapsed_ms,
    )
