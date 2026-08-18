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
  /** HAM COSINE -- Hit.score ile aynı ölçek, dokunulmaz (CLAUDE.md §1.1). */
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
  /**
   * TÜRETİLİR: payload.dropped uzunluğu (§10.11). `unsupported_count` ile
   * BİRLEŞTİRİLMEZ: biri bağlanabilirliği, öbürü rapordan ÇIKARILAN iddiayı
   * sayar; tuzak iddia ikisinde de görünür (§10.6).
   */
  dropped_count: number
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
  /** ADDITIVE (§10.11): rapordan çıkarılan iddia sayısı. */
  dropped_count: number
}

// --------------------------------------------------------------------------- Rapor payload'ı (Faz 2)
//
// `payload_json` §10.5'te DONDURULDU; render'ın TEK girdisi budur, frontend
// hiçbir alanı tahmin etmez. `ArtifactDetail.payload` jenerik bir
// Record<string, unknown> olarak kalır (kind başına farklı şema) --
// `isReportPayload()` ile daraltılır.

export interface ReportParagraph {
  /** Her cümle ayrı bir <span>: tıklanıp kaynağına gidilebilsin (§10.5). */
  sentences: string[]
}

export interface ReportSection {
  id: string
  kind: "executive_summary" | "key_findings" | "detailed_analysis"
  title: string
  /** Yalnızca `detailed_analysis` için dolu. */
  topic_id: number | null
  /** Şeffaflık + ikinci katman kaydı; `exec` için birleşim kümesi (§10.4). */
  context_chunk_ids: number[]
  paragraphs: ReportParagraph[]
}

export interface ReportTable {
  id: string
  title: string
  columns: string[]
  /** Hücreler ya belge adı (string) ya da chunk sayısı (number). */
  rows: (string | number)[][]
}

export interface ReportCitation {
  chunk_id: number
  source: string
  /** 0 = markdown fixture (sayfa eki taşımaz). */
  page: number
  citation: string
}

/** Rapordan ÇIKARILAN iddia. Gövdede gösterilmez; ayrı panelde listelenir. */
export interface DroppedClaim {
  section_id: string
  text: string
  reason: "unsupported" | "weak" | "unverified_terms"
  /** HAM COSINE; bağlanamayan iddiada null. */
  score: number | null
  /** Yalnızca `unverified_terms` sebebinde dolu. */
  terms: string[]
}

export interface ReportPayload {
  kind: "report"
  outline: string[]
  sections: ReportSection[]
  tables: ReportTable[]
  citations: ReportCitation[]
  dropped: DroppedClaim[]
}

// --------------------------------------------------------------------------- Mind map payload'ı (Faz 3)
//
// §11.5'te dondurulmuş şema. Yapı KORPUSTAN gelir (kümeleme); LLM yalnızca
// `label` yazar -- render hiçbir düğüm/kenar hesaplamaz.

export interface MindMapCitation {
  chunk_id: number
  source: string
  /** 0 = markdown fixture (sayfa eki taşımaz). */
  page: number
  citation: string
}

export interface MindMapNode {
  id: string
  label: string
  kind: "root" | "topic"
  /** Kök için null. */
  parent: string | null
  /** Yalnızca `topic` için dolu. */
  topic_id: number | null
  chunk_ids: number[]
  size: number
  /**
   * DÜRÜSTLÜK ALANI (§11.5): etiketi model mi önerdi ("model"), sadakat
   * kapısından geçemediği için korpustan mı türetildi ("fallback"), yoksa
   * kökün korpus metadatası mı ("corpus")? Arayüz "fallback"i GÖSTERMEK
   * ZORUNDA -- yoksa deterministik bir ad model çıktısı gibi görünür.
   */
  label_source: "model" | "fallback" | "corpus"
  citations: MindMapCitation[]
}

export interface MindMapEdge {
  from: string
  to: string
  relation: "related"
  /** HAM COSINE (küme merkezleri arası) -- yeniden ölçeklenmez. */
  weight: number
}

/** Kapıdan geçemeyen etiket ÖNERİSİ. Haritada gösterilmez; ayrı panelde durur. */
export interface MindMapDroppedLabel {
  topic_id: number
  text: string
  /** `label_invalid`: model biçimi tutturamadı (boş ya da 5 kelimeden uzun). */
  reason: "unsupported" | "weak" | "unverified_terms" | "label_invalid"
  /** HAM COSINE; biçimi bozuk etiket kapıya hiç girmediği için null. */
  score: number | null
  terms: string[]
}

export interface MindMapPayload {
  kind: "mindmap"
  nodes: MindMapNode[]
  edges: MindMapEdge[]
  dropped: MindMapDroppedLabel[]
}

// --------------------------------------------------------------------------- Quiz payload'ı (Faz 4)
//
// §12.2'de dondurulmuş şema. Dört tipin üçü korpustan deterministik kurulur;
// yalnızca `short_answer` bir LLM çağrısıdır.

export type QuizQuestionType =
  | "multiple_choice"
  | "true_false"
  | "fill_blank"
  | "short_answer"

export interface QuizQuestion {
  id: string
  type: QuizQuestionType
  topic_id: number
  /** Kullanıcıya gösterilen soru metni (boşluklu cümle ya da iddia). */
  prompt: string
  /** multiple_choice: şıklar · true_false: ["true","false"] · diğerleri: []. */
  choices: string[]
  /**
   * Cevap anahtarı. true_false'ta KANONİK "true"/"false" -- arayüz
   * yerelleştirir, payload dile bağlanmaz.
   */
  answer: string
  chunk_id: number
  source: string
  citation: string
  /** Cevabın korpustaki dayanağı; sonuç ekranında gösterilir. */
  evidence: string
}

/** Cevap anahtarı kapıdan geçemediği için quiz'e ALINMAYAN soru. */
export interface QuizDroppedQuestion {
  topic_id: number
  /**
   * DOĞRULANAMAYAN metnin kendisi: short_answer'da modelin referans cevabı,
   * diğer tiplerde dayanak cümlesi (§12.7). Soru gövdesi `prompt`'tadır.
   */
  text: string
  prompt: string
  reason: "unsupported" | "weak" | "unverified_terms"
  score: number | null
  terms: string[]
}

export interface QuizPayload {
  kind: "quiz"
  questions: QuizQuestion[]
  dropped: QuizDroppedQuestion[]
}

export interface QuizAnswerResult {
  question_id: string
  type: QuizQuestionType
  given: string | null
  expected: string
  /** short_answer'da HER ZAMAN null: o tip eşikle doğru/yanlış'a indirgenmez. */
  correct: boolean | null
  /**
   * YALNIZCA short_answer'da dolu. HAM COSINE ama `ChunkHit.score` DEĞİL: iki
   * CEVAP arasındaki simetrik benzerlik (§12.8). DESIGN_SYSTEM §1.2 güven
   * bantlarıyla RENKLENDİRİLEMEZ -- o bantlar sorgu→chunk için kalibre edildi.
   */
  similarity: number | null
  chunk_id: number | null
  citation: string | null
  evidence: string
}

export interface AttemptResult {
  attempt_id: number
  artifact_id: number
  /** YALNIZCA deterministik sorulardan; hiç yoksa null (0.0 "hepsi yanlış" olurdu). */
  score: number | null
  correct_count: number
  deterministic_total: number
  similarity_total: number
  completed_at: string
  results: QuizAnswerResult[]
}

export interface AttemptSummary {
  id: number
  artifact_id: number
  started_at: string
  completed_at: string | null
  score: number | null
}

export interface QuizAttemptRequest {
  answers: Record<string, string>
  /** Quiz'in AÇILDIĞI an; yalnızca istemci bilir. */
  started_at?: string
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
