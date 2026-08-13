"""Pydantic şemaları (docs/FEATURE_SPEC.md §2.1).

Alan adları dondurulmuştur; buradaki isimler frontend'in beklediği isimlerle
birebir aynı olmalı. Request gövdeleri (`ChatRequest`, `RetrieveRequest`)
FEATURE_SPEC'te alan alan tanımlı DEĞİL -- yalnızca endpoint'in "soru sor"
olduğu belirtilmiş. Bu dosyadaki `question`/`k` adları backend'in kendi
tasarım kararıdır (bkz. görev raporu).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ready", "warming", "error"]
    chat_model: str
    embedding_model: str
    min_score: float
    top_k: int
    document_count: int
    chunk_count: int
    ocr_available: bool


class DocumentInfo(BaseModel):
    filename: str
    page_count: int
    chunk_count: int
    ingested_at: str
    has_ocr_chunks: bool


class ChunkHit(BaseModel):
    score: float
    source: str
    page: int  # 0 = markdown fixture (sayfa yok)
    content: str
    via_ocr: bool
    citation: str
    passed_threshold: bool


class RetrieveResponse(BaseModel):
    hits: List[ChunkHit]
    threshold: float
    elapsed_ms: int


class RetrieveRequest(BaseModel):
    question: str
    k: Optional[int] = None


class ChatRequest(BaseModel):
    question: str
    k: Optional[int] = None


class DeleteResponse(BaseModel):
    deleted: bool


class ErrorResponse(BaseModel):
    code: str
    message: str


class IngestCompletePayload(BaseModel):
    """`event: complete` veri gövdesi (§3.4). Doğrudan pydantic response_model
    olarak kullanılmaz (SSE), sadece alan sözleşmesini belgelemek için var."""

    filename: str
    page_count: int
    chunk_count: int
    skipped_pages: List[int] = Field(default_factory=list)
