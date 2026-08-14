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
    // Studio katmanı (§2.2) -- additive, yukarıdaki dokuzu değiştirmez.
    | "ARTIFACT_NOT_FOUND"
    | "ARTIFACT_STALE"
    | "INSUFFICIENT_CORPUS"
    | "GENERATION_FAILED"
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

// --------------------------------------------------------------------------- Studio (Faz 1)
//
// backend/schemas.py ile birebir eşleşir (docs/FEATURE_SPEC.md §9.8). Faz
// 1'de yalnızca iskelet: `studio-panel` bu tiplere karşı istek atmıyor
// (§9.9.4), ama backend'i geliştiren agentla sözleşme burada kilitleniyor.

export interface ArtifactClaim {
  node_path: string
  claim_text: string
  chunk_id: number | null
  /** HAM COSINE -- Hit.score ile aynı ölçek, dokunulmaz (AGENTS.md §1.1). */
  score: number | null
  verdict: "grounded" | "weak" | "unsupported"
  /** chunk'ın belgesi. */
  source: string | null
  /** 0 = markdown fixture (sayfa yok). */
  page: number | null
  citation: string | null
}

export interface ArtifactSummary {
  id: number
  kind: "mindmap" | "report" | "quiz"
  scope: "corpus" | "document"
  document_id: number | null
  title: string
  /** ORAN (grounded / toplam iddia), benzerlik skoru DEĞİL (§9.1). */
  fidelity_score: number | null
  generation_ms: number | null
  /** ISO 8601. */
  created_at: string
  /** TÜRETİLİR: backend `corpus_fingerprint`'i karşılaştırıp üretir. */
  is_stale: boolean
}

export interface ArtifactDetail extends ArtifactSummary {
  params: Record<string, unknown>
  payload: Record<string, unknown>
  claims: ArtifactClaim[]
  /** TÜRETİLİR: verdict === 'unsupported' sayısı. */
  unsupported_count: number
}

export interface ArtifactCreateRequest {
  kind: "mindmap" | "report" | "quiz"
  /** Backend varsayılanı "corpus". */
  scope?: "corpus" | "document"
  document_id?: number | null
  params?: Record<string, unknown>
}

// --------------------------------------------------------------------------- Studio SSE olayları
//
// POST /api/artifacts akışı (§9.8). Sıralama garantisi: `stage` her zaman
// ilk olay; `progress` yalnızca iki `stage` arasında gelir; `complete`
// veya `error` (ApiErrorBody) her zaman son olaydır.

export interface ArtifactStageEvent {
  stage: "selection" | "clustering" | "generation" | "fidelity"
  label: string
}

/**
 * DİKKAT: bu `pct` /api/documents'ınkiyle AYNI ÖLÇEKTE DEĞİL -- burada
 * 0-100 tam sayı, yükleme akışında 0.0-1.0 kesirli (§9.5 [!warning]).
 * Bu yüzden iki akış arasında paylaşılan bir ilerleme yardımcısı yazılmaz.
 */
export interface ArtifactProgressEvent {
  pct: number
  detail: string
}

export interface ArtifactCompleteEvent {
  artifact_id: number
  fidelity_score: number
  generation_ms: number
  unsupported_count: number
}

// --------------------------------------------------------------------------- Metrics
//
// backend/routes/metrics.py eval/results.json'ı OLDUĞU GİBİ servis eder.
// Şema docs/FEATURE_SPEC.md §6.2'de tanımlı; M1-M4 (Faz 4.7) tamamlanana
// kadar dosya yok, /api/metrics 503 METRICS_NOT_GENERATED döner.

export interface MetricsQuestionResult {
  id: string
  // "meta"/"corpus"/"cross_lingual": rag/query_router.py yönlendirmesini
  // ölçen kategoriler (özetleme, korpus sorgusu, diller arası retrieval).
  // Additive -- eski üç kategori davranışı değişmedi.
  category:
    | "answerable"
    | "unanswerable"
    | "edge_case"
    | "meta"
    | "corpus"
    | "cross_lingual"
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
