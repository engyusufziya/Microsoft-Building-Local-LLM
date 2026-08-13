"""`/api/metrics` -- `eval/results.json`'ı doğrudan servis eder.

docs/FEATURE_SPEC.md §1.5, §6.3: eval istek anında ÇALIŞTIRILMAZ (~100 sn
sürer ve chat modeliyle çakışır). Dosya yoksa 503 + METRICS_NOT_GENERATED
döner -- sahte sayı gösterilmez.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from rag import config

router = APIRouter(tags=["metrics"])

RESULTS_PATH = config.PROJECT_ROOT / "eval" / "results.json"


@router.get("/metrics")
async def get_metrics() -> JSONResponse:
    if not RESULTS_PATH.exists():
        return JSONResponse(
            status_code=503,
            content={
                "code": "METRICS_NOT_GENERATED",
                "message": "Değerlendirme sonuçları henüz üretilmedi.",
            },
        )
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return JSONResponse(content=data)
