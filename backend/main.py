"""FastAPI uygulaması: CORS, warmup, statik dosya servisi, `/api/health`.

Warmup tasarım kararı (FEATURE_SPEC §7 net değildi, burada netleştirildi):
model yükleme `lifespan` içinde bir arka plan `asyncio.Task`'ı olarak
başlatılır ve `lifespan` HEMEN `yield` eder. Böylece sunucu istekleri kabul
etmeye hemen başlar ve `/api/health` gerçek zamanlı "warming" -> "ready"
geçişini raporlayabilir. Eğer warmup senkron biçimde `lifespan` içinde
`await` edilseydi, ASGI sunucusu lifespan tamamlanmadan hiç istek kabul
etmezdi ve frontend'in "yükleniyor" ekranı gösterebileceği bir pencere hiç
olmazdı.

Test modu: `RAG_BACKEND_SKIP_WARMUP=1` ortam değişkeni set edilirse arka plan
görevi hiç başlatılmaz, `model_status` sonsuza kadar "warming" kalır. Testler
gerçek Foundry Local'a dokunmadan hem "warming" davranışını doğrulayabilir
hem de model gerektiren endpoint'leri test ederken `app.state.model_status`'u
elle "ready" yapabilir. Aynı şekilde `RAG_BACKEND_DB_PATH` ortam değişkeni
(varsayılan: `rag.config.DB_PATH`) testlerin gerçek `rag.db`'ye dokunmadan
`:memory:` veya geçici bir dosya kullanmasını sağlar.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from rag import config, models, ocr, store

from . import schemas
from .routes import chat, documents, metrics, retrieve as retrieve_routes

SKIP_WARMUP_ENV = "RAG_BACKEND_SKIP_WARMUP"
DB_PATH_ENV = "RAG_BACKEND_DB_PATH"

WEB_OUT_DIR = config.PROJECT_ROOT / "web" / "out"


async def _run_warmup(app: FastAPI) -> None:
    """Embedding + chat modellerini yükler, `model_status`'u günceller.

    Her iki çağrı da senkron/bloklayıcı (Foundry Local SDK), bu yüzden
    event loop'u kilitlememek için `asyncio.to_thread` ile ayrı bir thread'de
    çalıştırılır.
    """
    try:
        await asyncio.to_thread(models.get_embedding_client)
        await asyncio.to_thread(models.get_chat_client)
        app.state.model_status = "ready"
    except Exception as exc:  # pragma: no cover - gerçek Foundry Local hatası
        app.state.model_status = "error"
        app.state.model_error = str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model_status = "warming"
    app.state.model_error = None
    app.state.model_lock = asyncio.Lock()

    db_path = os.environ.get(DB_PATH_ENV) or None
    app.state.conn = store.connect(db_path)

    if os.environ.get(SKIP_WARMUP_ENV):
        app.state.warmup_task = None
    else:
        app.state.warmup_task = asyncio.create_task(_run_warmup(app))

    try:
        yield
    finally:
        task = app.state.warmup_task
        if task is not None:
            task.cancel()
        app.state.conn.close()


class _SpaStaticFiles(StaticFiles):
    """`/metrics` gibi rotaları `metrics.html`'e düşürerek servis eder.

    Next.js statik export'u `/metrics` rotası için `out/metrics.html` (düz
    dosya) üretir; `out/metrics/` dizini yalnızca RSC payload'larını içerir ve
    `index.html` BARINDIRMAZ. Bu yüzden düz `StaticFiles(html=True)` yolu
    dizin sanıp `metrics/index.html` arar ve 404 döner (ölçüldü).

    Çözüm nginx'in `try_files $uri $uri.html` davranışının aynısı: dosya
    bulunamazsa `<yol>.html` denenir. URL'ler temiz kalır (`/metrics`,
    `/metrics/` değil) ve Next'in `trailingSlash` ayarına bağımlılık olmaz.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if response.status_code == 404 and path and not path.endswith(".html"):
            try:
                return await super().get_response(f"{path}.html", scope)
            except HTTPException:
                pass  # `.html` de yoksa orijinal 404 dönsün.
        return response


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            body = detail
        else:
            body = {"code": "INTERNAL", "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"code": "INTERNAL", "message": str(exc)})


def create_app() -> FastAPI:
    app = FastAPI(title="Local RAG Assistant API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_error_handlers(app)

    app.include_router(documents.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(retrieve_routes.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")

    @app.get("/api/health", response_model=schemas.HealthResponse)
    async def health(request: Request) -> schemas.HealthResponse:
        conn = request.app.state.conn
        docs = store.list_documents(conn)
        chunk_count = sum(d["chunk_count"] or 0 for d in docs)
        return schemas.HealthResponse(
            status=request.app.state.model_status,
            chat_model=config.CHAT_MODEL,
            embedding_model=config.EMBEDDING_MODEL,
            min_score=config.MIN_SCORE,
            top_k=config.TOP_K,
            document_count=len(docs),
            chunk_count=chunk_count,
            ocr_available=ocr.is_available(),
        )

    # Next.js statik export çıktısı. API rotalarının ALTINDA (sonra) mount
    # edilir ki /api/* önceliği korunsun. Build alınmamışsa mount edilmez;
    # backend tek başına (API-only) çalışmaya devam eder.
    if WEB_OUT_DIR.exists():
        app.mount("/", _SpaStaticFiles(directory=str(WEB_OUT_DIR), html=True), name="static")

    return app


app = create_app()
