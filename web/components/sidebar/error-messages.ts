import { ApiRequestError } from "@/lib/api"
import type { ResolvedNamespace } from "@/lib/i18n"
import type { common } from "@/lib/i18n/common"
import type { sidebar } from "@/lib/i18n/sidebar"
import type { ApiErrorBody } from "@/lib/types"

export type SidebarText = ResolvedNamespace<typeof sidebar>
export type CommonText = ResolvedNamespace<typeof common>

/**
 * backend/routes/documents.py::MAX_UPLOAD_BYTES ile aynı değer (50 MB).
 *
 * `/api/health` bu sınırı yayınlamıyor (FEATURE_SPEC §2.1 şemasında yok),
 * bu yüzden istemci ön kontrolü (§1.1 "Dosya tipi/boyut ön kontrolü") için
 * burada duruyor ve `DocumentUploader`'a prop olarak geçirilebilir. Eşik
 * (`min_score`) gibi bir MODEL parametresi değil, backend'e özgü bir
 * güvenlik marjıdır — "eşiği koda gömme" kuralı bunu kapsamaz. Backend
 * sınırı değişirse burası da değişmeli.
 */
export const DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

/**
 * Bir hatanın yerelleştirilebilir gösterimi.
 *
 * Backend'in `message` alanı TÜRKÇE üretilir (backend/errors.py); UI dili
 * İngilizce iken ham metni basmak DESIGN_SYSTEM.md §7'ye aykırı olurdu.
 * Bu yüzden hata durumda `code` olarak saklanır, metne yalnızca render
 * anında — aktif dille — çevrilir. Dil değişirse ekrandaki hata metni de
 * kendiliğinden değişir.
 */
export type Failure =
  | { kind: "api"; code: ApiErrorBody["code"] }
  | { kind: "network" }
  | { kind: "not-pdf" }
  | { kind: "too-large"; maxBytes: number }

/** SSE `event: error` çerçevesinden gelen `{code, message}` için. */
export function apiFailure(
  code: ApiErrorBody["code"],
  maxBytes: number = DEFAULT_MAX_UPLOAD_BYTES
): Failure {
  if (code === "FILE_TOO_LARGE") return { kind: "too-large", maxBytes }
  return { kind: "api", code }
}

/**
 * `lib/api.ts`'ten gelen bir istisnayı `Failure`'a çevirir.
 * `fetch` ağ hatasında `TypeError` atar — `ApiRequestError` olmayan her şey
 * "sunucuya ulaşılamadı" sayılır.
 */
export function toFailure(error: unknown, maxBytes?: number): Failure {
  if (error instanceof ApiRequestError) return apiFailure(error.code, maxBytes)
  return { kind: "network" }
}

function megabytes(bytes: number): number {
  return Math.round(bytes / (1024 * 1024))
}

/** FEATURE_SPEC.md §2.2 hata kodları → sidebar/common namespace metinleri. */
export function failureText(
  failure: Failure,
  t: SidebarText,
  tc: CommonText
): string {
  switch (failure.kind) {
    case "network":
      return tc.errorNetwork
    case "not-pdf":
      return t.errorNotPdf
    case "too-large":
      return t.errorFileTooLarge(megabytes(failure.maxBytes))
    case "api":
      switch (failure.code) {
        case "INVALID_PDF":
          return t.errorInvalidPdf
        case "NO_CONTENT":
          return t.errorNoContent
        case "MODEL_WARMING":
          return t.errorModelWarming
        case "DOCUMENT_NOT_FOUND":
          return t.errorNotFound
        case "NO_DOCUMENTS":
          return t.errorNoDocuments
        default:
          // EMPTY_QUERY / METRICS_NOT_GENERATED / INTERNAL sidebar akışında
          // beklenmez; jenerik metne düşer. Backend'in ham mesajı BASILMAZ.
          return tc.errorGeneric
      }
  }
}
