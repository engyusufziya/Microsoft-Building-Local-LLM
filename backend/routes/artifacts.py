"""`/api/artifacts` -- Studio artefakt hattı (SSE üretim, CRUD).

docs/FEATURE_SPEC.md §9.8. `rag/artifacts/base.py::generate_artifact` beş
adımlı hattı çalıştırır; Faz 1'de registry BOŞ olduğu için 3. adımda her
zaman `GenerationFailedError` fırlatır -- bu ölü kod değil, hattın Faz 1'deki
gerçek durumu (§9.5). Bu dosya yalnızca HTTP/SSE yüzeyi, şema dönüşümü ve
hata eşlemesidir; kümeleme/sadakat/CRUD mantığı `rag/`'dadır.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, AsyncIterator, List, Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from rag import store
from rag.artifacts import mindmap, quiz, report
from rag.artifacts import store as artifact_store
from rag.artifacts.base import GenerationFailedError, generate_artifact
from rag.topics import InsufficientCorpusError, cluster_corpus

from .. import schemas
from ..errors import ApiError
from ..sse import sse_event

router = APIRouter(tags=["artifacts"])

# Her `kind` markdown'ını KENDİ modülünde üretir; rota yalnızca seçer.
# Sözlük `ArtifactCreateRequest.kind` Literal'i üzerinde TAM: üç kind'in üçü de
# burada, dolayısıyla `_EXPORTERS[kind]` bir KeyError üretemez. Eksik kind için
# savunma kodu yazılmadı -- imkânsız senaryo için hata yolu (AGENTS.md §2.2).
# Faz 2'de bu bir sözlük değil, doğrudan `report.to_markdown` çağrısıydı ve
# mindmap/quiz üretilebilir olduğu anda sessizce BOŞ dosya döndürürdü.
_EXPORTERS = {
    "report": report.to_markdown,
    "mindmap": mindmap.to_markdown,
    "quiz": quiz.to_markdown,
}


def _require_ready(request: Request) -> None:
    if request.app.state.model_status != "ready":
        raise ApiError(503, "MODEL_WARMING", "Modeller henüz yüklenmedi.")


def _document_exists(conn, document_id: int) -> bool:
    row = conn.execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone()
    return row is not None


def _is_stale(conn, corpus_fingerprint: str) -> bool:
    """`is_stale` motorda yok, backend türetir (`has_ocr_chunks` deseninin aynısı).

    Ham parmak izi API yüzeyinde hiç görünmez -- yalnızca bu boolean çıkar
    (§9.8 [!note]).
    """
    return corpus_fingerprint != store.corpus_fingerprint(conn)


def _citation(source: Optional[str], page: Optional[int]) -> Optional[str]:
    """`rag/retrieve.py::Hit.citation()` ile BİREBİR aynı biçim."""
    if source is None:
        return None
    if page:
        return f"[Kaynak: {source} s.{page}]"
    return f"[Kaynak: {source}]"


def _to_claim_out(conn, claim: dict) -> schemas.ArtifactClaimOut:
    chunk_id = claim["chunk_id"]
    source: Optional[str] = None
    page: Optional[int] = None
    if chunk_id is not None:
        row = conn.execute(
            "SELECT source, page FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if row is not None:
            source = row["source"]
            page = row["page"]
    return schemas.ArtifactClaimOut(
        node_path=claim["node_path"],
        claim_text=claim["claim_text"],
        chunk_id=chunk_id,
        score=claim["score"],
        verdict=claim["verdict"],
        source=source,
        page=page,
        citation=_citation(source, page),
    )


def _dropped_count(payload: dict) -> int:
    """`unsupported_count` gibi TÜRETİLİR (§10.11) -- yeni sütun eklenmez.

    Rapordan ÇIKARILAN iddia sayısı; `unsupported_count` ile karıştırılmamalı
    (biri bağlanabilirliği, öbürü yayımlanabilirliği sayar, §10.6). `dropped`
    taşımayan artefakt kind'leri (mindmap/quiz) için 0.
    """
    return len(payload.get("dropped", []))


def _to_summary(conn, row: dict) -> schemas.ArtifactSummary:
    return schemas.ArtifactSummary(
        id=row["id"],
        kind=row["kind"],
        scope=row["scope"],
        document_id=row["document_id"],
        title=row["title"],
        fidelity_score=row["fidelity_score"],
        generation_ms=row["generation_ms"],
        created_at=row["created_at"],
        is_stale=_is_stale(conn, row["corpus_fingerprint"]),
    )


# --------------------------------------------------------------------------- GET / DELETE


@router.get("/artifacts", response_model=List[schemas.ArtifactSummary])
async def list_artifacts(
    request: Request, kind: Optional[str] = None, scope: Optional[str] = None
) -> List[schemas.ArtifactSummary]:
    conn = request.app.state.conn
    rows = artifact_store.list_artifacts(conn, kind=kind, scope=scope)
    return [_to_summary(conn, r) for r in rows]


@router.get("/artifacts/{artifact_id}", response_model=schemas.ArtifactDetail)
async def get_artifact(artifact_id: int, request: Request) -> schemas.ArtifactDetail:
    conn = request.app.state.conn
    row = artifact_store.get_artifact(conn, artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"'{artifact_id}' bulunamadı.")

    claims = [_to_claim_out(conn, c) for c in row["claims"]]
    unsupported_count = sum(1 for c in claims if c.verdict == "unsupported")

    return schemas.ArtifactDetail(
        id=row["id"],
        kind=row["kind"],
        scope=row["scope"],
        document_id=row["document_id"],
        title=row["title"],
        fidelity_score=row["fidelity_score"],
        generation_ms=row["generation_ms"],
        created_at=row["created_at"],
        is_stale=_is_stale(conn, row["corpus_fingerprint"]),
        params=row["params"],
        payload=row["payload"],
        claims=claims,
        unsupported_count=unsupported_count,
        dropped_count=_dropped_count(row["payload"]),
    )


@router.get("/artifacts/{artifact_id}/export")
async def export_artifact(
    artifact_id: int, request: Request, format: Literal["md"]
) -> Response:
    """Markdown dışa aktarım (§10.11 · §11.8 · §12.9). Rota İNCE: markdown'ın
    kendisini üreticinin kendi modülü üretir, burada yalnızca başlıklar kurulur.

    `format` Literal olduğu için `md` dışındaki değeri FastAPI 422'ye çevirir;
    ikinci bir biçim (html) §10.15'te reddedildi. BAYAT artefakt 200 döner:
    export bir OKUMA işlemidir (§9.8'in okuma kuralı), 409 üretmez.

    Dosya adı ASCII: artefakt başlığı Türkçe karakter taşıyabiliyor ve
    Content-Disposition başlığı latin-1 ile kodlanıyor -- `kind-id.md` hem
    deterministik hem güvenli.
    """
    conn = request.app.state.conn
    row = artifact_store.get_artifact(conn, artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"'{artifact_id}' bulunamadı.")

    filename = f"{row['kind']}-{artifact_id}.md"
    return Response(
        content=_EXPORTERS[row["kind"]](row["payload"]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/artifacts/{artifact_id}", response_model=schemas.DeleteResponse)
async def delete_artifact(artifact_id: int, request: Request) -> schemas.DeleteResponse:
    conn = request.app.state.conn
    deleted = artifact_store.delete_artifact(conn, artifact_id)
    if not deleted:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"'{artifact_id}' bulunamadı.")
    return schemas.DeleteResponse(deleted=True)


# --------------------------------------------------------------------------- POST (SSE)


@router.post("/artifacts")
async def create_artifact_endpoint(
    body: schemas.ArtifactCreateRequest, request: Request
) -> StreamingResponse:
    _require_ready(request)

    conn = request.app.state.conn

    if body.scope == "document":
        if body.document_id is None or not _document_exists(conn, body.document_id):
            raise ApiError(404, "DOCUMENT_NOT_FOUND", f"'{body.document_id}' bulunamadı.")

    # Kümelenemeyen korpus AKIŞ AÇILMADAN ÖNCE kontrol edilir (§9.8) --
    # kullanıcı bir SSE bağlantısı kurup sonra hata almaz. generate_artifact
    # zaten 2. adımda cluster_corpus'u kendi içinde tekrar çağırıyor; bu ön
    # kontrol yalnızca hata sinyalini akış açılmadan önce yakalamak için var
    # (bu korpus ölçeğinde -- ~20 chunk -- tekrar hesaplamanın maliyeti önemsiz).
    #
    # Ön kontrol İSTENEN KAPSAMLA yapılır: belge kapsamında korpus geneli
    # kümelenebiliyor diye "yeterli" demek, tek chunk'lık bir belge için akışı
    # açıp hatayı akışın içinde vermek olurdu.
    try:
        cluster_corpus(
            conn, document_id=body.document_id if body.scope == "document" else None
        )
    except InsufficientCorpusError as exc:
        raise ApiError(422, "INSUFFICIENT_CORPUS", str(exc)) from exc

    lock: asyncio.Lock = request.app.state.model_lock

    async def event_stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        q: "asyncio.Queue[Any]" = asyncio.Queue()
        _DONE = object()

        def emit_cb(event: str, payload: dict) -> None:
            # generate_artifact'in emit'i doğrudan SSE olay adını taşıyor
            # ("stage" | "progress") -- ek bir çeviri gerekmiyor.
            loop.call_soon_threadsafe(q.put_nowait, ("emit", event, payload))

        def run() -> None:
            try:
                artifact_id = generate_artifact(
                    conn,
                    kind=body.kind,
                    scope=body.scope,
                    document_id=body.document_id,
                    params=body.params,
                    emit=emit_cb,
                )
                loop.call_soon_threadsafe(q.put_nowait, ("complete", artifact_id))
            except GenerationFailedError as exc:
                loop.call_soon_threadsafe(q.put_nowait, ("error", "GENERATION_FAILED", str(exc)))
            except Exception as exc:  # pragma: no cover - beklenmeyen motor hatası
                loop.call_soon_threadsafe(q.put_nowait, ("error", "GENERATION_FAILED", str(exc)))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, _DONE)

        # Kilit üretim boyunca tutulur -- routes/documents.py'nin deseni (§9.8).
        async with lock:
            threading.Thread(target=run, daemon=True).start()
            while True:
                item = await q.get()
                if item is _DONE:
                    break

                item_kind = item[0]
                if item_kind == "emit":
                    _, event_name, payload = item
                    yield sse_event(event_name, payload)
                elif item_kind == "complete":
                    _, artifact_id = item
                    detail = artifact_store.get_artifact(conn, artifact_id)
                    unsupported_count = sum(
                        1 for c in detail["claims"] if c["verdict"] == "unsupported"
                    )
                    yield sse_event(
                        "complete",
                        {
                            "artifact_id": artifact_id,
                            "fidelity_score": detail["fidelity_score"],
                            "generation_ms": detail["generation_ms"],
                            "unsupported_count": unsupported_count,
                            # ADDITIVE (§10.11): unsupported_count kaldırılmaz,
                            # yeniden adlandırılmaz.
                            "dropped_count": _dropped_count(detail["payload"]),
                        },
                    )
                elif item_kind == "error":
                    _, code, message = item
                    yield sse_event("error", {"code": code, "message": message})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
