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

/**
 * Cevap metnindeki atıf işaretçilerini TARAR — `[Kaynak: dosya.pdf s.4]`.
 *
 * `CITATION_PATTERN` tek bir stringin TAMAMINI eşler (chip'ler için);
 * bu ise metnin içindeki işaretçileri bulur. Motor bu işaretçileri cevabın
 * içine gömüyor (`rag/answer.py` SYSTEM_PROMPT), yani numaralandırma için
 * ayrı bir veri yoluna gerek yok.
 */
const CITATION_SCAN_PATTERN = /\[[^:\]\n]*:[^\]\n]+\]/g

export function scanCitations(text: string): string[] {
  return text.match(CITATION_SCAN_PATTERN) ?? []
}

/**
 * Atıf işaretçisi -> üst simge numarası eşlemesi (FEATURE_SPEC §13.4).
 *
 * Numara METİNDE İLK GÖRÜLME sırasından gelir, `hits` dizisinin skor
 * sırasından DEĞİL: okur numarayı cümlede gördüğü sırayla bekler. Aynı
 * kaynak ikinci kez geçtiğinde AYNI numarayı alır — numara kaynağı
 * gösterir, geçişi değil.
 */
export function numberCitations(text: string): Map<string, number> {
  const numbers = new Map<string, number>()
  for (const marker of scanCitations(text)) {
    if (!numbers.has(marker)) numbers.set(marker, numbers.size + 1)
  }
  return numbers
}

/** `numberCitations` haritasını ters çevirir: numara -> işaretçi. */
export function citationByNumber(numbers: Map<string, number>): Map<number, string> {
  return new Map([...numbers].map(([citation, n]) => [n, citation]))
}
