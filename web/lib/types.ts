/**
 * backend/schemas.py ile birebir eşleşen tipler. Alan adları dondurulmuştur
 * (docs/FEATURE_SPEC.md §2.1) -- burada değiştirmeden önce backend'i değiştir.
 */

export interface HealthResponse {
  status: "ready" | "warming" | "error"
  chat_model: string
  embedding_model: string
  min_score: number
  top_k: number
  document_count: number
  chunk_count: number
  ocr_available: boolean
}

export interface DocumentInfo {
  filename: string
  page_count: number
  chunk_count: number
  ingested_at: string
  has_ocr_chunks: boolean
}

export interface ChunkHit {
  score: number
  source: string
  /** 0 = markdown fixture (sayfa yok). */
  page: number
  content: string
  via_ocr: boolean
  citation: string
  passed_threshold: boolean
}

export interface RetrieveResponse {
  hits: ChunkHit[]
  threshold: number
  elapsed_ms: number
}

export interface DeleteResponse {
  deleted: boolean
}

/** {code, message} -- docs/FEATURE_SPEC.md §2.2'deki tüm hata kodları. */
export interface ApiErrorBody {
  code:
    | "EMPTY_QUERY"
    | "INVALID_PDF"
    | "DOCUMENT_NOT_FOUND"
    | "NO_DOCUMENTS"
    | "FILE_TOO_LARGE"
    | "NO_CONTENT"
    | "MODEL_WARMING"
    | "METRICS_NOT_GENERATED"
    | "INTERNAL"
  message: string
}

// --------------------------------------------------------------------------- SSE olayları

/** POST /api/chat akışı. backend/routes/chat.py ile birebir. */
export interface ChatRetrievalEvent {
  hits: ChunkHit[]
  threshold: number
  passed_count: number
  rejected_count: number
  elapsed_ms: number
}

export interface ChatTokenEvent {
  text: string
}

export interface ChatDoneEvent {
  answered: boolean
  reason: "below_threshold" | "llm_refused" | null
  sources: string[]
  elapsed_ms: number
  token_count: number
}

/** POST /api/documents akışı. backend/routes/documents.py ile birebir. */
export interface UploadProgressEvent {
  pct: number
  stage: string
}

export interface UploadCompleteEvent {
  filename: string
  page_count: number
  chunk_count: number
  skipped_pages: number[]
}

// --------------------------------------------------------------------------- Metrics
//
// backend/routes/metrics.py eval/results.json'ı OLDUĞU GİBİ servis eder.
// Şema docs/FEATURE_SPEC.md §6.2'de tanımlı; M1-M4 (Faz 4.7) tamamlanana
// kadar dosya yok, /api/metrics 503 METRICS_NOT_GENERATED döner.

export interface MetricsQuestionResult {
  id: string
  category: "answerable" | "unanswerable" | "edge_case"
  passed: boolean
  seconds: number
  expected_source: string | null
  source_found: boolean | null
  keywords_matched: number | null
  keywords_total: number | null
  answer: string
}

export interface MetricsModelResult {
  alias: string
  model_id: string
  is_active: boolean
  summary: {
    passed: number
    total: number
    by_category: Record<string, [number, number]>
    retrieval_hits: [number, number]
    avg_seconds: number
  }
  questions: MetricsQuestionResult[]
}

export interface MetricsThresholdSweepRow {
  threshold: number
  answerable_passed: number
  answerable_total: number
  other_passed: number
  other_total: number
}

export interface MetricsResponse {
  generated_at: string
  config: {
    min_score: number
    top_k: number
    chunk_words: number
    chunk_overlap_words: number
  }
  corpus: { chunk_count: number; document_count: number }
  models: MetricsModelResult[]
  threshold_sweep: {
    answerable_scores: number[]
    other_scores: number[]
    table: MetricsThresholdSweepRow[]
  }
}
