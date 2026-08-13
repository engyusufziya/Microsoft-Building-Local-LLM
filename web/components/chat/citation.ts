/**
 * Kaynak atıflarıyla (citation) ilgili saf yardımcılar.
 *
 * Motor `[Kaynak: dosya.pdf s.4]` biçiminde tek bir string üretir
 * (`rag/retrieve.py::Hit.citation`) ve `done` olayının `sources` dizisi bu
 * stringlerden oluşur (`rag/answer.py::Answer.sources`). SourceChip ->
 * ChunkCard bağlantısı bu string üzerinden kurulur, bu yüzden ayrıştırma
 * tek bir yerde durur.
 *
 * Etiket ("Kaynak") Türkçe sabittir çünkü backend'den öyle gelir — burada
 * ATILIR, UI kendi yerelleştirilmiş biçimini kurar (DESIGN_SYSTEM.md §7).
 */

export interface ParsedCitation {
  /** Dosya adı. Ayrıştırılamazsa ham string. */
  source: string
  /** 0 = sayfa bilgisi yok (markdown fixture). */
  page: number
}

const CITATION_PATTERN = /^\[[^:\]]*:\s*(.+?)(?:\s+s\.(\d+))?\]$/

export function parseCitation(citation: string): ParsedCitation {
  const match = CITATION_PATTERN.exec(citation.trim())
  if (!match) return { source: citation, page: 0 }
  return { source: match[1], page: match[2] ? Number(match[2]) : 0 }
}

/**
 * Uzun dosya adını ORTADAN kısaltır (FEATURE_SPEC §4.2): baş ve son
 * korunur, çünkü ayırt edici bilgi çoğu zaman uzantıda ve önekte.
 * Kısaltma gerekmiyorsa string aynen döner.
 */
export function middleTruncate(value: string, max = 32): string {
  if (value.length <= max) return value
  // Ellipsis tek karakter; kalan bütçeyi baş/son arasında bölüştür.
  const budget = max - 1
  const head = Math.ceil(budget / 2)
  const tail = budget - head
  return `${value.slice(0, head)}…${value.slice(value.length - tail)}`
}
