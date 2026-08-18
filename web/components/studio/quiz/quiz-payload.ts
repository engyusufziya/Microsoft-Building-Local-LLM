import type { QuizPayload, QuizQuestionType } from "@/lib/types"

/**
 * `payload_json` §12.2'de DONDURULDU. Bu dosya onu render'a hazırlayan SAF
 * yardımcıları taşır — bileşenler payload'ın şeklini TAHMİN ETMEZ.
 */

export function asQuizPayload(
  payload: Record<string, unknown>
): QuizPayload | null {
  return payload.kind === "quiz" && Array.isArray(payload.questions)
    ? (payload as unknown as QuizPayload)
    : null
}

/**
 * `true_false` şıkları payload'da KANONİK ("true"/"false") tutulur; arayüz
 * dili neyse onu gösterir. Payload'a Türkçe etiket yazmak, artefaktı üretildiği
 * dile kilitlerdi (aynı artefakt İngilizce arayüzde de açılıyor).
 */
export function choiceLabel(
  choice: string,
  labels: { yes: string; no: string }
): string {
  if (choice === "true") return labels.yes
  if (choice === "false") return labels.no
  return choice
}

export function typeLabel(
  type: QuizQuestionType,
  labels: {
    multipleChoice: string
    trueFalse: string
    fillBlank: string
    shortAnswer: string
  }
): string {
  switch (type) {
    case "multiple_choice":
      return labels.multipleChoice
    case "true_false":
      return labels.trueFalse
    case "fill_blank":
      return labels.fillBlank
    default:
      return labels.shortAnswer
  }
}
