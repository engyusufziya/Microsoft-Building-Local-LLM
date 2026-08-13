import type { SidebarText } from "./error-messages"

/**
 * `/api/documents` SSE'sinin `progress.stage` alanını yerelleştirir.
 *
 * Neden eşleme gerekiyor: `stage` metni motorda üretiliyor
 * (rag/ingest.py::_embed_and_store — "32/41 chunk embed edildi") ve
 * TÜRKÇE. FEATURE_SPEC §3.4 "progress_cb doğrudan bu olaya eşlenir,
 * motorda değişiklik yok" diyor; motor bu fazda dokunulmaz. UI dili
 * İngilizceyken ham Türkçe metin basmak DESIGN_SYSTEM.md §7'ye aykırı
 * olurdu, bu yüzden bilinen dört aşama desen eşleşmesiyle tanınır ve
 * kendi i18n anahtarımıza çevrilir.
 *
 * Tanınmayan bir aşama gelirse (motor metni değişirse) nötr bir
 * "İşleniyor…" metnine düşülür — ham metin ASLA basılmaz. Yüzde göstergesi
 * zaten `pct`'ten geldiği için ilerleme bilgisi kaybolmaz.
 */
const EMBEDDING_PROGRESS = /^(\d+)\s*\/\s*(\d+)\s+chunk embed edildi/i
const EMBEDDING_START = /^(\d+)\s+chunk embed ediliyor/i
const SAVED = /^veritabanına yazıldı/i
const READING = /^(.+?)\s+okunuyor/i

export function localizeUploadStage(
  stage: string | null | undefined,
  t: SidebarText
): string {
  if (!stage) return t.stageWorking

  const progress = EMBEDDING_PROGRESS.exec(stage)
  if (progress) {
    return t.stageEmbedding(Number(progress[1]), Number(progress[2]))
  }

  const start = EMBEDDING_START.exec(stage)
  if (start) return t.stageEmbeddingStart(Number(start[1]))

  if (SAVED.test(stage)) return t.stageSaving

  const reading = READING.exec(stage)
  if (reading) return t.stageReading(reading[1])

  return t.stageWorking
}
