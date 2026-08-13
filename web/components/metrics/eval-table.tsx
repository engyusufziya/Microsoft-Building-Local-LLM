"use client"

import * as React from "react"
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  InfoIcon,
  XIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { metrics as metricsText } from "@/lib/i18n/metrics"
import type { MetricsModelResult, MetricsQuestionResult } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MetricsSection } from "@/components/metrics/metric-primitives"
import {
  CATEGORY_ORDER,
  useCategoryLabels,
  type Category,
} from "@/components/metrics/categories"

/**
 * Soru bazında sonuç tablosu.
 *
 * Filtreler tablonun ÜSTÜNDE tek bir satırda durur (kart içinde, sütun
 * başlıklarına gömülü değil) ve tabloyu bütün olarak daraltır.
 *
 * `keywords_matched` hakkında: bu metrik kasıtlı olarak gevşek raporlar
 * (bkz. `eval/run_eval.py::keyword_hit` — küçük/büyük harf duyarsız kök
 * araması). Cevap tamamen doğruyken bile eksik görünebilir. Bu yüzden
 * sütunun altında dipnot var ve hücre "başarısız" gibi renklenmiyor:
 * bağlayıcı olan "Sonuç" sütunudur.
 */

type CategoryFilter = Category | "all"

const FILTERS: readonly CategoryFilter[] = ["all", ...CATEGORY_ORDER]

export interface EvalTableProps {
  models: MetricsModelResult[]
  className?: string
}

export function EvalTable({ models, className }: EvalTableProps) {
  const t = useT(metricsText)
  const categoryLabels = useCategoryLabels()

  const defaultModelKey =
    (models.find((model) => model.is_active) ?? models[0])?.alias ?? ""
  const [modelKey, setModelKey] = React.useState(defaultModelKey)
  const [filter, setFilter] = React.useState<CategoryFilter>("all")
  const [expanded, setExpanded] = React.useState<ReadonlySet<string>>(
    () => new Set<string>()
  )

  const selectedModel =
    models.find((model) => model.alias === modelKey) ?? models[0]
  const questions = selectedModel?.questions ?? []
  const rows =
    filter === "all"
      ? questions
      : questions.filter((question) => question.category === filter)

  const filterLabel = (value: CategoryFilter) =>
    value === "all" ? t.categoryAll : categoryLabels[value]

  const toggleExpanded = (id: string) => {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <MetricsSection
      title={t.evalTitle}
      description={t.evalSubtitle}
      className={className}
    >
      {/* --- Filtre satırı: kapsadığı her şeyin üstünde, tek satır. --- */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        {models.length > 1 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-caption font-medium text-text-secondary">
              {t.modelFilterLabel}
            </span>
            {models.map((model) => (
              <Button
                key={model.alias}
                size="xs"
                variant={model.alias === selectedModel?.alias ? "default" : "outline"}
                onClick={() => setModelKey(model.alias)}
                className="font-mono"
              >
                {model.alias}
              </Button>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-caption font-medium text-text-secondary">
            {t.filterLabel}
          </span>
          {FILTERS.map((value) => {
            const count =
              value === "all"
                ? questions.length
                : questions.filter((question) => question.category === value).length
            return (
              <Button
                key={value}
                size="xs"
                variant={value === filter ? "default" : "outline"}
                onClick={() => setFilter(value)}
                aria-pressed={value === filter}
              >
                {filterLabel(value)}
                <span className="font-mono tabular-nums opacity-70">{count}</span>
              </Button>
            )
          })}
        </div>

        <span className="ml-auto font-mono text-mono text-text-tertiary tabular-nums">
          {t.rowCount(rows.length, questions.length)}
        </span>
      </div>

      {rows.length === 0 ? (
        <p className="text-body-sm text-text-secondary">{t.filterEmpty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] border-collapse text-body-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="w-12 py-2 pr-3 text-left text-caption font-medium text-text-secondary">
                  {t.colId}
                </th>
                <th className="py-2 pr-3 text-left text-caption font-medium text-text-secondary">
                  {t.colCategory}
                </th>
                <th className="py-2 pr-3 text-left text-caption font-medium text-text-secondary">
                  {t.colStatus}
                </th>
                <th className="py-2 pr-3 text-right text-caption font-medium text-text-secondary">
                  {t.colSeconds}
                </th>
                <th className="py-2 pr-3 text-left text-caption font-medium text-text-secondary">
                  {t.colSource}
                </th>
                <th className="py-2 pr-3 text-left text-caption font-medium text-text-secondary">
                  {t.colKeywords}
                </th>
                <th className="py-2 text-left text-caption font-medium text-text-secondary">
                  {t.colAnswer}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((question) => (
                <EvalRow
                  key={question.id}
                  question={question}
                  categoryLabel={categoryLabels[question.category]}
                  isExpanded={expanded.has(question.id)}
                  onToggle={toggleExpanded}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="flex items-start gap-2 text-caption text-text-tertiary">
        <InfoIcon className="mt-px size-3.5 shrink-0" />
        <span>{t.keywordsFootnote}</span>
      </p>
    </MetricsSection>
  )
}

// --------------------------------------------------------------------------- satır

interface EvalRowProps {
  question: MetricsQuestionResult
  categoryLabel: string
  isExpanded: boolean
  onToggle: (id: string) => void
}

function EvalRow({ question, categoryLabel, isExpanded, onToggle }: EvalRowProps) {
  const t = useT(metricsText)
  const answer = question.answer.trim()
  const isLong = answer.length > 140

  return (
    <tr className="border-b border-border align-top last:border-b-0">
      <td className="py-3 pr-3">
        <span className="font-mono text-mono tabular-nums text-text-secondary">
          {question.id}
        </span>
      </td>
      <td className="py-3 pr-3">
        <Badge variant="outline" className="text-caption">
          {categoryLabel}
        </Badge>
      </td>
      <td className="py-3 pr-3">
        {/* Renk + ikon + metin birlikte: durum renge bağlı değil. */}
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-caption font-medium",
            question.passed ? "text-success" : "text-danger"
          )}
        >
          {question.passed ? (
            <CheckIcon className="size-3.5" aria-hidden="true" />
          ) : (
            <XIcon className="size-3.5" aria-hidden="true" />
          )}
          {question.passed ? t.statusPassed : t.statusFailed}
        </span>
      </td>
      <td className="py-3 pr-3 text-right">
        <span className="font-mono text-mono tabular-nums text-text-secondary">
          {t.secondsShort(question.seconds)}
        </span>
      </td>
      <td className="max-w-[14rem] py-3 pr-3">
        {question.expected_source ? (
          <span className="flex flex-col gap-0.5">
            <span
              className="truncate font-mono text-mono text-text-secondary"
              title={question.expected_source}
            >
              {question.expected_source}
            </span>
            <span
              className={cn(
                "text-caption",
                question.source_found ? "text-success" : "text-danger"
              )}
            >
              {question.source_found ? t.sourceFound : t.sourceMissing}
            </span>
          </span>
        ) : (
          <span className="text-caption text-text-tertiary" title={t.notApplicableAria}>
            {t.notApplicable}
          </span>
        )}
      </td>
      <td className="py-3 pr-3">
        {question.keywords_total !== null && question.keywords_total > 0 ? (
          <span className="font-mono text-mono tabular-nums text-text-secondary">
            {t.keywordsValue(question.keywords_matched ?? 0, question.keywords_total)}
          </span>
        ) : (
          <span className="text-caption text-text-tertiary" title={t.notApplicableAria}>
            {t.notApplicable}
          </span>
        )}
      </td>
      <td className="py-3">
        {answer.length === 0 ? (
          <span className="text-caption text-text-tertiary">{t.emptyAnswer}</span>
        ) : (
          <div className="flex flex-col items-start gap-1">
            <p
              className={cn(
                "max-w-prose text-body-sm text-text-secondary",
                !isExpanded && "line-clamp-2"
              )}
            >
              {answer}
            </p>
            {isLong && (
              <Button
                size="xs"
                variant="ghost"
                onClick={() => onToggle(question.id)}
                aria-expanded={isExpanded}
              >
                {isExpanded ? t.collapseAnswer : t.expandAnswer}
                {isExpanded ? (
                  <ChevronUpIcon className="size-3" />
                ) : (
                  <ChevronDownIcon className="size-3" />
                )}
              </Button>
            )}
          </div>
        )}
      </td>
    </tr>
  )
}
