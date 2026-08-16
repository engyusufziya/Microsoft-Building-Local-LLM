"""
Studio artefakt hattı: base (protokol + ortak akış), fidelity (sadakat kapısı),
store (CRUD), report (Faz 2 -- Rapor Üreteci). Bu dosya yalnızca alt modülleri
yeniden dışa açar; mantık içermez.

`report`'un import edilmesi KENDİSİ Faz 2'nin tek satırlık kaydını tetikler:
report.py'nin sonundaki `register(ReportGenerator())` modül yüklenirken
çalışır (bkz. rag/artifacts/report.py).
"""

from __future__ import annotations

from .base import (
    ArtifactGenerator,
    GeneratedArtifact,
    GenerationContext,
    GenerationFailedError,
    ProgressCb,
    generate_artifact,
    get_generator,
    register,
)
from .fidelity import (
    ClaimBinding,
    bind_claims,
    fidelity_score,
    should_drop,
    unverified_terms,
    verdict_for,
)
from .report import ReportGenerator, to_markdown
from .store import create_artifact, delete_artifact, get_artifact, list_artifacts

__all__ = [
    "ArtifactGenerator",
    "GeneratedArtifact",
    "GenerationContext",
    "GenerationFailedError",
    "ProgressCb",
    "generate_artifact",
    "get_generator",
    "register",
    "ClaimBinding",
    "bind_claims",
    "fidelity_score",
    "should_drop",
    "unverified_terms",
    "verdict_for",
    "ReportGenerator",
    "to_markdown",
    "create_artifact",
    "delete_artifact",
    "get_artifact",
    "list_artifacts",
]
