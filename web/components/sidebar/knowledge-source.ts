import {
  deleteDocument,
  getHealth,
  listDocuments,
  uploadDocument,
  type UploadCallbacks,
} from "@/lib/api"
import type { DeleteResponse, DocumentInfo, HealthResponse } from "@/lib/types"

/**
 * Sidebar'ın backend'e bakan yüzü — `lib/api.ts`'in İNCE bir arayüzü.
 *
 * Neden ayrı bir tip: `lib/api.ts` entegrasyonun dosyası ve doğrudan
 * `fetch` yapıyor. Bileşenleri backend olmadan (Foundry Local modellerini
 * yüklemeden) doğrulayabilmek için tek bir enjeksiyon noktası gerekiyordu;
 * `app/dev-kb/page.tsx` sahte bir kaynak geçirerek aynı bileşen ağacını
 * gerçek verilerle aynı kod yollarından render eder.
 *
 * Üretimde varsayılan kaynak kullanılır; `lib/api.ts` sarılmaz, kopyalanmaz.
 */
export interface KnowledgeSource {
  listDocuments: () => Promise<DocumentInfo[]>
  deleteDocument: (filename: string) => Promise<DeleteResponse>
  uploadDocument: (file: File, callbacks: UploadCallbacks) => Promise<void>
  getHealth: () => Promise<HealthResponse>
}

export const defaultKnowledgeSource: KnowledgeSource = {
  listDocuments,
  deleteDocument,
  uploadDocument,
  getHealth,
}
