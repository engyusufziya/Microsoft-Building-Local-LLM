import type { ArtifactClaim, ReportPayload } from "@/lib/types"

/**
 * `payload_json` §10.5'te DONDURULDU. Bu dosya onu render'a hazırlayan saf
 * yardımcıları taşır — bileşenler payload'ın şeklini TAHMİN ETMEZ.
 */

/** Jenerik `payload` alanını ReportPayload'a daraltır. */
export function asReportPayload(
  payload: Record<string, unknown>
): ReportPayload | null {
  return payload.kind === "report" && Array.isArray(payload.sections)
    ? (payload as unknown as ReportPayload)
    : null
}

/**
 * `chunk_id -> kaynak sırası` haritası: raporda her cümlenin üst simgesi,
 * "Kaynaklar" listesindeki sıra numarasıdır.
 *
 * Numara payload'ın KENDİ `citations` sırasından (kaynak adı, sonra sayfa)
 * türer — yeni bir sıralama icat edilmez (§10.8).
 */
export function citationIndexByChunk(payload: ReportPayload): Map<number, number> {
  return new Map(payload.citations.map((c, i) => [c.chunk_id, i + 1]))
}

/** node_path -> claim: cümleyi bağlandığı chunk'a bağlayan tek yol. */
export function claimByNodePath(claims: ArtifactClaim[]): Map<string, ArtifactClaim> {
  return new Map(claims.map((claim) => [claim.node_path, claim]))
}

export function sentenceNodePath(
  sectionIndex: number,
  paragraphIndex: number,
  sentenceIndex: number
): string {
  return `/sections/${sectionIndex}/paragraphs/${paragraphIndex}/sentences/${sentenceIndex}`
}

/** Rapora giren cümle sayısı (düşürülenler DAHİL DEĞİL). */
export function sentenceCount(payload: ReportPayload): number {
  return payload.sections.reduce(
    (total, section) =>
      total +
      section.paragraphs.reduce((n, paragraph) => n + paragraph.sentences.length, 0),
    0
  )
}
