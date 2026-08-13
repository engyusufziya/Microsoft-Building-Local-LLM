"use client"

import { useT } from "@/lib/i18n"
import { metrics as metricsText } from "@/lib/i18n/metrics"
import type { MetricsQuestionResult } from "@/lib/types"

/**
 * Değerlendirme kategorileri tek yerde.
 *
 * Sıralama `eval/eval_set.json`'ın anlatım sırasıdır (kolaydan zora:
 * cevaplanabilir → cevaplanamaz → kenar durum) ve hem özet kırılımında
 * hem tablo filtresinde aynı kalır.
 */
export const CATEGORY_ORDER = [
  "answerable",
  "unanswerable",
  "edge_case",
] as const satisfies readonly MetricsQuestionResult["category"][]

export type Category = (typeof CATEGORY_ORDER)[number]

/** Kategori adlarının aktif dildeki karşılıkları. */
export function useCategoryLabels(): Record<Category, string> {
  const t = useT(metricsText)
  return {
    answerable: t.categoryAnswerable,
    unanswerable: t.categoryUnanswerable,
    edge_case: t.categoryEdgeCase,
  }
}
