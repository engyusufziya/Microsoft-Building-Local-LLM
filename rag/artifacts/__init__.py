"""
Studio artefakt hattı: base (protokol + ortak akış), fidelity (sadakat kapısı),
store (CRUD). Bu dosya yalnızca alt modülleri yeniden dışa açar; mantık
içermez.
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
from .fidelity import ClaimBinding, bind_claims, fidelity_score, verdict_for
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
    "verdict_for",
    "create_artifact",
    "delete_artifact",
    "get_artifact",
    "list_artifacts",
]
