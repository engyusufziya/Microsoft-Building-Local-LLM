"""`/api/quiz/*` -- quiz denemesi gönderimi ve geçmişi (FEATURE_SPEC §12.10).

`backend/` ince kalır (CLAUDE.md §1.5): puanlama mantığı
`rag/artifacts/quiz.py::score_attempt`'tedir, denemeler
`rag/artifacts/store.py`'de saklanır. Bu dosya yalnızca HTTP yüzeyi, şema
dönüşümü ve hata eşlemesidir.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List

from fastapi import APIRouter, Request

from rag.artifacts import store as artifact_store
from rag.artifacts.quiz import score_attempt

from .. import schemas
from ..errors import ApiError

router = APIRouter(tags=["quiz"])


def _load_quiz(conn, artifact_id: int) -> dict:
    """Quiz artefaktını getirir; yoksa VEYA quiz değilse 404.

    Bir rapor kimliğiyle `/api/quiz/{id}/attempt` çağırmak, "quiz {id}"
    kaynağının var olmadığı anlamına gelir -- 404 ARTIFACT_NOT_FOUND doğru
    cevaptır ve yeni bir hata kodu açmaz (§2.2 kod listesi additive kalır).
    """
    row = artifact_store.get_artifact(conn, artifact_id)
    if row is None or row["kind"] != "quiz":
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"'{artifact_id}' bir quiz değil.")
    return row


@router.post("/quiz/{artifact_id}/attempt", response_model=schemas.AttemptResult)
async def submit_attempt(
    artifact_id: int, body: schemas.QuizAttemptRequest, request: Request
) -> schemas.AttemptResult:
    """Denemeyi puanlar ve kaydeder.

    Model kilidi: quiz'de short_answer sorusu varsa puanlama EMBEDDING çağrısı
    yapar. Kilit `/api/documents` ve `/api/artifacts` ile aynı kilittir (§7) --
    bir üretim sürerken gelen deneme, üretim bitene kadar bekler; ikisi aynı
    anda modele girmez.
    """
    conn = request.app.state.conn
    row = _load_quiz(conn, artifact_id)

    has_short_answer = any(
        q.get("type") == "short_answer" for q in row["payload"].get("questions", [])
    )
    if has_short_answer and request.app.state.model_status != "ready":
        raise ApiError(503, "MODEL_WARMING", "Modeller henüz yüklenmedi.")

    lock: asyncio.Lock = request.app.state.model_lock
    if has_short_answer:
        async with lock:
            scored = await asyncio.to_thread(score_attempt, row["payload"], body.answers)
    else:
        # Model yok -> kilit yok: tamamen deterministik puanlama, aynı anda
        # süren bir üretimi beklemesi için sebep yok.
        scored = score_attempt(row["payload"], body.answers)

    completed_at = datetime.now().isoformat(timespec="seconds")
    attempt_id = artifact_store.create_attempt(
        conn,
        artifact_id=artifact_id,
        started_at=body.started_at or completed_at,
        completed_at=completed_at,
        score=scored["score"],
        answers=body.answers,
    )

    return schemas.AttemptResult(
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        score=scored["score"],
        correct_count=scored["correct_count"],
        deterministic_total=scored["deterministic_total"],
        similarity_total=scored["similarity_total"],
        completed_at=completed_at,
        results=[schemas.QuizAnswerResult(**r) for r in scored["results"]],
    )


@router.get("/quiz/{artifact_id}/attempts", response_model=List[schemas.AttemptSummary])
async def list_attempts(artifact_id: int, request: Request) -> List[schemas.AttemptSummary]:
    conn = request.app.state.conn
    _load_quiz(conn, artifact_id)
    return [
        schemas.AttemptSummary(**row)
        for row in artifact_store.list_attempts(conn, artifact_id)
    ]
