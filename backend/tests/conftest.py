"""Ortak test fixture'ları.

Foundry Local'a HİÇ dokunulmaz: `RAG_BACKEND_SKIP_WARMUP=1` lifespan'in
warmup görevini hiç başlatmamasını sağlar (`model_status` "warming" kalır),
`RAG_BACKEND_DB_PATH=:memory:` gerçek `rag.db` yerine bellek içi bir
veritabanı kullanır. Model gerektiren testler `app.state.model_status`'u
elle "ready" yapar ve `rag.*` fonksiyonlarını monkeypatch'ler.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("RAG_BACKEND_SKIP_WARMUP", "1")
os.environ.setdefault("RAG_BACKEND_DB_PATH", ":memory:")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def app():
    """Her test için taze bir uygulama + izole bellek içi veritabanı."""
    from backend.main import create_app

    return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ready_client(app):
    """Model yüklenmiş gibi davranan istemci (gerçek model yüklenmeden).

    ÖNEMLİ: `model_status = "ready"` lifespan başlangıcından SONRA set
    edilmeli -- `lifespan` her `TestClient` girişinde `model_status`'u
    "warming" ile sıfırlar, önceden set etmek sessizce ezilir.
    """
    with TestClient(app) as c:
        app.state.model_status = "ready"
        yield c
