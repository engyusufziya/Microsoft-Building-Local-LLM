"""
Studio artefakt hattı: base (protokol + ortak akış), fidelity (sadakat kapısı),
store (CRUD), report (Faz 2), mindmap (Faz 3). Bu dosya yalnızca alt modülleri
yeniden dışa açar; mantık içermez.

Üreticilerin import edilmesi KENDİSİ kayıtlarını tetikler: her modülün
sonundaki `register(...)` çağrısı modül yüklenirken çalışır. Registry Faz 1'de
boştu; Faz 3 sonunda `report` ve `mindmap` dolu, `quiz` Faz 4'te gelecek.

`to_markdown` isim ÇAKIŞMASI kasıtlı olarak çözülmedi: her üreticinin kendi
markdown'ı var ve doğru olan onu MODÜLÜNDEN çağırmaktır
(`report.to_markdown`). Bu dosya geriye dönük uyumluluk için yalnızca
raporunkini `to_markdown` adıyla dışa açar (Faz 2'den beri öyleydi);
backend/routes/artifacts.py kind'e göre modülden seçer.
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
    distinctive_terms,
    fidelity_score,
    should_drop,
    unverified_terms,
    verdict_for,
)
from .mindmap import MindMapGenerator
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
    "distinctive_terms",
    "fidelity_score",
    "should_drop",
    "unverified_terms",
    "verdict_for",
    "MindMapGenerator",
    "ReportGenerator",
    "to_markdown",
    "create_artifact",
    "delete_artifact",
    "get_artifact",
    "list_artifacts",
]
