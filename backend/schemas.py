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


# --------------------------------------------------------------------------- Studio artefaktları (§9.8)


class ArtifactClaimOut(BaseModel):
    node_path: str
    claim_text: str
    chunk_id: Optional[int]
    score: Optional[float]  # HAM COSINE -- dokunulmaz (CLAUDE.md §1.1)
    verdict: Literal["grounded", "weak", "unsupported"]
    source: Optional[str]  # chunk'ın belgesi; chunk_id yoksa None
    page: Optional[int]  # 0 = markdown fixture
    citation: Optional[str]  # "[Kaynak: dosya.pdf s.4]"


class ArtifactSummary(BaseModel):
    id: int
    kind: Literal["mindmap", "report", "quiz"]
    scope: Literal["corpus", "document"]
    document_id: Optional[int]
    title: str
    fidelity_score: Optional[float]  # ORAN, benzerlik değil (§9.1)
    generation_ms: Optional[int]
    created_at: str  # ISO 8601
    is_stale: bool  # TÜRETİLİR -- bkz. routes/artifacts.py


class ArtifactDetail(ArtifactSummary):
    params: dict
    payload: dict
    claims: List[ArtifactClaimOut]
    unsupported_count: int  # TÜRETİLİR: verdict == 'unsupported'


class ArtifactCreateRequest(BaseModel):
    kind: Literal["mindmap", "report", "quiz"]
    scope: Literal["corpus", "document"] = "corpus"
    document_id: Optional[int] = None
    params: dict = {}
