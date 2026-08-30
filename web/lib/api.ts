/**
 * Backend istemcisi -- docs/FEATURE_SPEC.md §2'deki tüm endpoint'leri sarar.
 *
 * Tek giriş noktası: frontend-kb, frontend-chat, metrics-ui bu dosyayı
 * import eder, kendi fetch mantıklarını yazmaz (docs/DESIGN_SYSTEM.md §6:
 * üç agent da bunu okuyacağı için paralel yazımda en yüksek çakışma riski
 * taşıyan dosya -- entegrasyona ayrıldı).
 *
 * Üretimde statik export FastAPI tarafından AYNI origin'den servis edilir,
 * bu yüzden varsayılan taban yol göreli (`/api`). Geliştirmede backend ayrı
 * porttan (uvicorn, varsayılan 8000) çalışırsa `.env.local` içinde
 * `NEXT_PUBLIC_API_BASE=http://localhost:8000/api` ile geçersiz kılınabilir.
 */

import { parseSSEStream } from "./sse"
import type {
  ApiErrorBody,
  ArtifactCompleteEvent,
  ArtifactCreateRequest,
  ArtifactDetail,
  ArtifactProgressEvent,
  ArtifactStageEvent,
  ArtifactSummary,
  AttemptResult,
  AttemptSummary,
  QuizAttemptRequest,
  ChatDoneEvent,
  ChatRetrievalEvent,
  ChatTokenEvent,
  DeleteResponse,
  DocumentInfo,
  HealthResponse,
  MetricsResponse,
  RetrieveResponse,
  UploadCompleteEvent,
  UploadProgressEvent,
} from "./types"

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "/api"

/** Backend'den gelen {code, message} hatasını taşıyan tip. */
export class ApiRequestError extends Error {
  code: ApiErrorBody["code"]
  status: number

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = "ApiRequestError"
    this.code = body.code
    this.status = status
  }
}

async function parseErrorBody(res: Response): Promise<ApiErrorBody> {
  try {
    const body = (await res.json()) as Partial<ApiErrorBody>
    if (body && typeof body.code === "string" && typeof body.message === "string") {
      return body as ApiErrorBody
    }
  } catch {
    // JSON değilse aşağıdaki jenerik hataya düş.
  }
  return { code: "INTERNAL", message: `HTTP ${res.status}` }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    throw new ApiRequestError(res.status, await parseErrorBody(res))
  }
  return (await res.json()) as T
}

// --------------------------------------------------------------------------- health / documents

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health")
}

export function listDocuments(): Promise<DocumentInfo[]> {
  return requestJson<DocumentInfo[]>("/documents")
}

/**
 * Sayfa görüntüsünün URL'i — FEATURE_SPEC §13.4.
 *
 * `fetch` DEĞİL, düz URL: görüntü `<img src>` ile yüklenir, böylece tarayıcı
 * kendi önbelleğini ve ilerlemeli çözümlemesini kullanır. Aynı origin
 * (`API_BASE` görece), yani §1.2 offline garantisi korunur.
 *
 * Dosya adı yol parçası olduğu için ENCODE EDİLİR: Türkçe karakter ve boşluk
 * içeren adlar (`Ders Notları 2026.pdf`) aksi halde kırılır.
 */
export function pageImageUrl(filename: string, page: number): string {
  return `${API_BASE}/documents/${encodeURIComponent(filename)}/pages/${page}/image`
}

export function deleteDocument(filename: string): Promise<DeleteResponse> {
  return requestJson<DeleteResponse>(`/documents/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  })
}

export interface UploadCallbacks {
  onProgress?: (event: UploadProgressEvent) => void
  onComplete?: (event: UploadCompleteEvent) => void
  onError?: (error: ApiErrorBody) => void
}

/**
 * PDF yükler, SSE ilerlemesini callback'lere dağıtır.
 *
 * Hata iki şekilde gelebilir (backend/routes/documents.py):
 *  - istek gövdesi HTTP hatası (413 dosya çok büyük, 503 model hazır değil)
 *    -> Promise reject eder (ApiRequestError)
 *  - akış SIRASINDA hata (400 INVALID_PDF, 422 NO_CONTENT) -> `event: error`
 *    çerçevesi olarak gelir, `onError` callback'i çağrılır, Promise resolve olur
 */
export async function uploadDocument(
  file: File,
  callbacks: UploadCallbacks = {}
): Promise<void> {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetch(`${API_BASE}/documents`, { method: "POST", body: formData })
  if (!res.ok) {
    throw new ApiRequestError(res.status, await parseErrorBody(res))
  }

  for await (const frame of parseSSEStream(res)) {
    switch (frame.event) {
      case "progress":
        callbacks.onProgress?.(JSON.parse(frame.data) as UploadProgressEvent)
        break
      case "complete":
        callbacks.onComplete?.(JSON.parse(frame.data) as UploadCompleteEvent)
        break
      case "error":
        callbacks.onError?.(JSON.parse(frame.data) as ApiErrorBody)
        break
    }
  }
}

// --------------------------------------------------------------------------- retrieve (LLM'siz)

/**
 * `/api/retrieve` -- min_score=None ile çağrılır (backend tarafında,
 * bkz. FEATURE_SPEC §0.1), yani eşik altındaki chunk'lar da döner.
 * `passed_threshold` alanına göre görsel olarak ele.
 */
export function retrieve(question: string, k?: number): Promise<RetrieveResponse> {
  return requestJson<RetrieveResponse>("/retrieve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, k }),
  })
}

// --------------------------------------------------------------------------- chat

export interface ChatCallbacks {
  onRetrieval?: (event: ChatRetrievalEvent) => void
  onToken?: (event: ChatTokenEvent) => void
  onDone?: (event: ChatDoneEvent) => void
  onError?: (error: ApiErrorBody) => void
}

/**
 * Soru sorar, SSE olaylarını callback'lere dağıtır
 * (retrieval -> token* -> done, bkz. FEATURE_SPEC §3.1).
 *
 * `reason: "llm_refused"` durumunda `onToken` modelin GERÇEK (Türkçe) ret
 * metnini de akıtır -- FEATURE_SPEC §3.2 gereği backend bunu değiştirmez.
 * UI dili İngilizce ise `onDone`'da `reason === "llm_refused"` görüldüğünde
 * akan metni frontend'in kendi yerelleştirilmiş metniyle (`chat.noAnswer`)
 * DEĞİŞTİRMESİ gerekir -- bu tüketicinin sorumluluğu, burada yapılmaz.
 */
export async function streamChat(
  question: string,
  callbacks: ChatCallbacks = {},
  k?: number
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, k }),
  })
  if (!res.ok) {
    throw new ApiRequestError(res.status, await parseErrorBody(res))
  }

  for await (const frame of parseSSEStream(res)) {
    switch (frame.event) {
      case "retrieval":
        callbacks.onRetrieval?.(JSON.parse(frame.data) as ChatRetrievalEvent)
        break
      case "token":
        callbacks.onToken?.(JSON.parse(frame.data) as ChatTokenEvent)
        break
      case "done":
        callbacks.onDone?.(JSON.parse(frame.data) as ChatDoneEvent)
        break
      case "error":
        callbacks.onError?.(JSON.parse(frame.data) as ApiErrorBody)
        break
    }
  }
}

// --------------------------------------------------------------------------- artifacts (Studio)

export function listArtifacts(kind?: string): Promise<ArtifactSummary[]> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : ""
  return requestJson<ArtifactSummary[]>(`/artifacts${query}`)
}

export function getArtifact(artifactId: number): Promise<ArtifactDetail> {
  return requestJson<ArtifactDetail>(`/artifacts/${artifactId}`)
}

export function deleteArtifact(artifactId: number): Promise<DeleteResponse> {
  return requestJson<DeleteResponse>(`/artifacts/${artifactId}`, { method: "DELETE" })
}

/**
 * Markdown dışa aktarım BAĞLANTISI (FEATURE_SPEC §10.11).
 *
 * `fetch` ile indirilmez: tarayıcının kendi indirme yolu `Content-Disposition`
 * başlığını zaten okuyor; Blob + ObjectURL kurmak aynı işi ikinci kez yapmak
 * olurdu. Bağlantı AYNI origin'dedir — offline garantisi korunur.
 */
export function artifactExportUrl(artifactId: number): string {
  return `${API_BASE}/artifacts/${artifactId}/export?format=md`
}

export interface ArtifactCallbacks {
  onStage?: (event: ArtifactStageEvent) => void
  onProgress?: (event: ArtifactProgressEvent) => void
  onComplete?: (event: ArtifactCompleteEvent) => void
  onError?: (error: ApiErrorBody) => void
}

/**
 * Artefakt üretir, SSE olaylarını callback'lere dağıtır
 * (stage* -> progress* -> complete | error, bkz. FEATURE_SPEC §9.8/§10.11).
 *
 * DİKKAT: `progress.pct` burada 0-100 TAM SAYI; `uploadDocument`'ınki 0.0-1.0
 * kesirli (§9.5 [!warning]). İki akış için paylaşılan bir ilerleme yardımcısı
 * YAZILMAZ — her akış kendi ölçeğini kendi okur.
 *
 * Akış açılmadan önceki hatalar (503 MODEL_WARMING, 404 DOCUMENT_NOT_FOUND,
 * 422 INSUFFICIENT_CORPUS) Promise'i reject eder; üretim SIRASINDAKİ hata
 * (GENERATION_FAILED) `event: error` olarak gelir ve `onError`'a düşer.
 */
export async function createArtifact(
  body: ArtifactCreateRequest,
  callbacks: ArtifactCallbacks = {}
): Promise<void> {
  const res = await fetch(`${API_BASE}/artifacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new ApiRequestError(res.status, await parseErrorBody(res))
  }

  for await (const frame of parseSSEStream(res)) {
    switch (frame.event) {
      case "stage":
        callbacks.onStage?.(JSON.parse(frame.data) as ArtifactStageEvent)
        break
      case "progress":
        callbacks.onProgress?.(JSON.parse(frame.data) as ArtifactProgressEvent)
        break
      case "complete":
        callbacks.onComplete?.(JSON.parse(frame.data) as ArtifactCompleteEvent)
        break
      case "error":
        callbacks.onError?.(JSON.parse(frame.data) as ApiErrorBody)
        break
    }
  }
}

// --------------------------------------------------------------------------- quiz (Faz 4)

/**
 * Quiz denemesini gönderir ve puanlanmış sonucu alır (FEATURE_SPEC §12.10).
 *
 * Puanlama SUNUCUDA yapılır -- cevap anahtarı zaten `payload` içinde geliyor
 * olsa da, istemcide puanlamak short_answer benzerliği için embedding'i
 * tarayıcıya taşımayı gerektirirdi (imkânsız) ve iki ayrı puanlama yolu
 * oluştururdu.
 */
export function submitQuizAttempt(
  artifactId: number,
  body: QuizAttemptRequest
): Promise<AttemptResult> {
  return requestJson<AttemptResult>(`/quiz/${artifactId}/attempt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export function listQuizAttempts(artifactId: number): Promise<AttemptSummary[]> {
  return requestJson<AttemptSummary[]>(`/quiz/${artifactId}/attempts`)
}

// --------------------------------------------------------------------------- metrics

/**
 * `/api/metrics`. Dosya henüz üretilmediyse (Faz 4.7 M1-M4) backend 503
 * METRICS_NOT_GENERATED döner -- bu fonksiyon ApiRequestError fırlatır,
 * çağıran taraf `error.code === "METRICS_NOT_GENERATED"` ile "henüz
 * çalıştırılmadı" durumunu ayırt edebilir.
 */
export function getMetrics(): Promise<MetricsResponse> {
  return requestJson<MetricsResponse>("/metrics")
}
