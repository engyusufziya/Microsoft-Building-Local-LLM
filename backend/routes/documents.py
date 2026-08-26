"""`/api/documents` -- belge listesi, PDF yükleme (SSE), silme.

docs/FEATURE_SPEC.md §1.1, §1.4, §2, §3.4.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, AsyncIterator, List

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import StreamingResponse

from rag import ingest, store
from rag.pdf_loader import PdfLoadError

from .. import schemas
from ..errors import ApiError
from ..sse import sse_event

router = APIRouter(tags=["documents"])

# rag/config.py'de böyle bir sınır yok (motor dosya boyutuyla ilgilenmez);
# bu backend'e özgü bir güvenlik marjı.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _require_ready(request: Request) -> None:
    if request.app.state.model_status != "ready":
        raise ApiError(503, "MODEL_WARMING", "Modeller henüz yüklenmedi.")


@router.get("/documents", response_model=List[schemas.DocumentInfo])
async def list_documents(request: Request) -> List[schemas.DocumentInfo]:
    conn = request.app.state.conn
    docs = store.list_documents(conn)

    # has_ocr_chunks motorda yok (FEATURE_SPEC §2.1 uyarısı): store.py'ye
    # dokunmadan ek bir sorguyla türetilir ve filename/source üzerinden
    # birleştirilir.
    ocr_rows = conn.execute(
        "SELECT source, SUM(via_ocr) > 0 AS has_ocr FROM chunks GROUP BY source"
    ).fetchall()
    ocr_map = {row["source"]: bool(row["has_ocr"]) for row in ocr_rows}

    # `id` de motorda yok -- has_ocr_chunks'ın AYNI deseniyle türetilir,
    # store.py'ye dokunulmaz. Artefakt yolunun `document_id`'si buradan gelir
    # (§9.7): onsuz arayüz scope="document" isteğini kuramıyordu.
    id_rows = conn.execute("SELECT id, filename FROM documents").fetchall()
    id_map = {row["filename"]: row["id"] for row in id_rows}

    return [
        schemas.DocumentInfo(
            id=id_map[d["filename"]],
            filename=d["filename"],
            page_count=d["page_count"],
            chunk_count=d["chunk_count"],
            ingested_at=d["ingested_at"],
            has_ocr_chunks=ocr_map.get(d["filename"], False),
        )
        for d in docs
    ]


@router.delete("/documents/{filename}", response_model=schemas.DeleteResponse)
async def delete_document(filename: str, request: Request) -> schemas.DeleteResponse:
    conn = request.app.state.conn
    deleted = store.delete_document(conn, filename)
    if not deleted:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", f"'{filename}' bulunamadı.")
    # delete_document zaten kendi içinde önbelleği geçersiz kılıyor; burada
    # tekrar çağrılması FEATURE_SPEC §1.4'teki akışı birebir izlemek için
    # (zararsız, idempotent).
    store.clear_cache()
    return schemas.DeleteResponse(deleted=True)


@router.post("/documents")
async def upload_document(request: Request, file: UploadFile = File(...)) -> StreamingResponse:
    _require_ready(request)

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(
            413,
            "FILE_TOO_LARGE",
            f"Dosya {MAX_UPLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor.",
        )

    filename = file.filename or "belge.pdf"
    conn = request.app.state.conn
    lock: asyncio.Lock = request.app.state.model_lock

    async def event_stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        q: "asyncio.Queue[Any]" = asyncio.Queue()
        _DONE = object()

        def progress_cb(pct: float, stage: str) -> None:
            loop.call_soon_threadsafe(q.put_nowait, ("progress", pct, stage))

        def run() -> None:
            try:
                result = ingest.ingest_pdf(
                    data, filename=filename, conn=conn, progress_cb=progress_cb
                )
                loop.call_soon_threadsafe(q.put_nowait, ("complete", result))
            except PdfLoadError as exc:
                loop.call_soon_threadsafe(q.put_nowait, ("error", "INVALID_PDF", str(exc)))
            except ValueError as exc:
                # ingest._embed_and_store hiç chunk çıkmadığında ValueError atar.
                loop.call_soon_threadsafe(q.put_nowait, ("error", "NO_CONTENT", str(exc)))
            except Exception as exc:  # pragma: no cover - beklenmeyen motor hatası
                loop.call_soon_threadsafe(q.put_nowait, ("error", "INTERNAL", str(exc)))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, _DONE)

        # Kilit ingest süresince tutulur: eşzamanlı chat/retrieve/ingest
        # istekleri aynı embedding modelini paylaşamaz (FEATURE_SPEC §7).
        async with lock:
            threading.Thread(target=run, daemon=True).start()
            while True:
                item = await q.get()
                if item is _DONE:
                    break

                kind = item[0]
                if kind == "progress":
                    _, pct, stage = item
                    yield sse_event("progress", {"pct": pct, "stage": stage})
                elif kind == "complete":
                    _, result = item
                    yield sse_event(
                        "complete",
                        {
                            "filename": result.filename,
                            "page_count": result.page_count,
                            "chunk_count": result.chunk_count,
                            "skipped_pages": result.skipped_pages,
                        },
                    )
                elif kind == "error":
                    _, code, message = item
                    yield sse_event("error", {"code": code, "message": message})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
