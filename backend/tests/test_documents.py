"""`/api/documents` -- liste, SSE yükleme, silme, has_ocr_chunks türetme."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from types import SimpleNamespace

import rag.ingest as rag_ingest
from rag import store


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Ham SSE metnini [(event, data), ...] listesine çevirir."""
    events = []
    for block in text.strip("\n").split("\n\n"):
        if not block.strip():
            continue
        event_line, data_line = block.split("\n", 1)
        event = event_line.removeprefix("event: ")
        data = json.loads(data_line.removeprefix("data: "))
        events.append((event, data))
    return events


def _upsert_fake_document(conn, filename: str, via_ocr: bool) -> None:
    chunk = SimpleNamespace(source=filename, page=1, content="içerik", via_ocr=via_ocr)
    store.upsert_document(conn, filename, page_count=1, chunks=[chunk], embeddings=[[0.1, 0.2, 0.3]])


# --------------------------------------------------------------------------- GET


def test_list_documents_empty(client):
    r = client.get("/api/documents")
    assert r.status_code == 200
    assert r.json() == []


def test_list_documents_derives_has_ocr_chunks(app, client):
    conn = app.state.conn
    _upsert_fake_document(conn, "ocr_doc.pdf", via_ocr=True)
    _upsert_fake_document(conn, "clean_doc.pdf", via_ocr=False)

    r = client.get("/api/documents")
    assert r.status_code == 200
    by_name = {d["filename"]: d for d in r.json()}
    assert by_name["ocr_doc.pdf"]["has_ocr_chunks"] is True
    assert by_name["clean_doc.pdf"]["has_ocr_chunks"] is False


def test_list_documents_belge_kimligini_yuzeye_cikarir(app, client):
    """`id` olmadan arayüz scope="document" isteğini KURAMIYORDU.

    POST /api/artifacts `document_id` (tamsayı) bekliyor; liste yalnızca
    filename döndürdüğü sürece Studio paneli belge kapsamlı artefakt
    isteyemezdi. Kimliğin gerçekten `documents.id` olduğu, üretilmiş bir
    değer olmadığı burada doğrulanır.
    """
    conn = app.state.conn
    _upsert_fake_document(conn, "a.pdf", via_ocr=False)
    _upsert_fake_document(conn, "b.pdf", via_ocr=False)

    r = client.get("/api/documents")
    assert r.status_code == 200
    by_name = {d["filename"]: d for d in r.json()}

    for filename, payload in by_name.items():
        row = conn.execute(
            "SELECT id FROM documents WHERE filename = ?", (filename,)
        ).fetchone()
        assert payload["id"] == row["id"]

    assert by_name["a.pdf"]["id"] != by_name["b.pdf"]["id"]


# --------------------------------------------------------------------------- DELETE


def test_delete_missing_document_returns_404(client):
    r = client.delete("/api/documents/does-not-exist.pdf")
    assert r.status_code == 404
    assert r.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_delete_existing_document(app, client):
    conn = app.state.conn
    _upsert_fake_document(conn, "to_delete.pdf", via_ocr=False)

    r = client.delete("/api/documents/to_delete.pdf")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert client.get("/api/documents").json() == []


# --------------------------------------------------------------------------- POST (SSE)


def test_upload_requires_ready_models(client):
    """model_status hâlâ 'warming' iken POST 503 MODEL_WARMING döner (SSE
    başlamadan, düz JSON hata olarak -- akış hiç açılmamış olmalı)."""
    r = client.post(
        "/api/documents", files={"file": ("test.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")}
    )
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_WARMING"


def test_upload_success_streams_progress_then_complete(ready_client, app, monkeypatch):
    calls = {}

    def fake_ingest_pdf(source, filename=None, conn=None, ocr=None, progress_cb=None):
        calls["filename"] = filename
        if progress_cb:
            progress_cb(0.0, "okunuyor")
            progress_cb(0.5, "5/10 chunk embed edildi")
            progress_cb(1.0, "Veritabanına yazıldı.")
        return rag_ingest.IngestResult(
            filename=filename, page_count=3, chunk_count=10, skipped_pages=[]
        )

    monkeypatch.setattr(rag_ingest, "ingest_pdf", fake_ingest_pdf)

    r = ready_client.post(
        "/api/documents",
        files={"file": ("rapor.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(r.text)
    kinds = [e for e, _ in events]
    assert kinds == ["progress", "progress", "progress", "complete"]
    assert events[-1][1] == {
        "filename": "rapor.pdf",
        "page_count": 3,
        "chunk_count": 10,
        "skipped_pages": [],
    }
    assert calls["filename"] == "rapor.pdf"


def test_upload_invalid_pdf_emits_error_event(ready_client, monkeypatch):
    from rag.pdf_loader import PdfLoadError

    def fake_ingest_pdf(source, filename=None, conn=None, ocr=None, progress_cb=None):
        raise PdfLoadError("PDF açılamadı; dosya bozuk.")

    monkeypatch.setattr(rag_ingest, "ingest_pdf", fake_ingest_pdf)

    r = ready_client.post(
        "/api/documents",
        files={"file": ("bozuk.pdf", io.BytesIO(b"not-a-pdf"), "application/pdf")},
    )
    # SSE zaten 200 ile başladı; hata event içinde taşınır.
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "INVALID_PDF"


def test_upload_no_content_emits_error_event(ready_client, monkeypatch):
    def fake_ingest_pdf(source, filename=None, conn=None, ocr=None, progress_cb=None):
        raise ValueError(f"'{filename}' içinden hiç chunk çıkarılamadı.")

    monkeypatch.setattr(rag_ingest, "ingest_pdf", fake_ingest_pdf)

    r = ready_client.post(
        "/api/documents",
        files={"file": ("bos.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "NO_CONTENT"


def test_upload_rejects_oversized_file(ready_client, monkeypatch):
    import backend.routes.documents as documents_module

    monkeypatch.setattr(documents_module, "MAX_UPLOAD_BYTES", 10)

    r = ready_client.post(
        "/api/documents",
        files={"file": ("buyuk.pdf", io.BytesIO(b"x" * 100), "application/pdf")},
    )
    assert r.status_code == 413
    assert r.json()["code"] == "FILE_TOO_LARGE"
