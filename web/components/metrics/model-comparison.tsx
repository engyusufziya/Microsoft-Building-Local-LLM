"use client"

import * as React from "react"
import { InfoIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { metrics as metricsText } from "@/lib/i18n/metrics"
import type { MetricsModelResult } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { MetricsSection, RatioBar } from "@/components/metrics/metric-primitives"
import { CATEGORY_ORDER, useCategoryLabels } from "@/components/metrics/categories"

/**
 * `models[]` girdilerini yan yana kıyaslar.
 *
 * Kıyas yalnızca DOSYADA kayıtlı olan modeller üzerinden yapılır. Tek model
 * varsa ikinci bir kart uydurulmaz; bunun yerine kıyasın neden yapılamadığı
 * yazılır (FEATURE_SPEC §6.1: kaydedilmemiş bir ölçüm koda gömülmüş bir
 * iddiadır).
 */

export interface ModelComparisonProps {
  models: MetricsModelResult[]
  className?: string
}

export function ModelComparison({ models, className }: ModelComparisonProps) {
  const t = useT(metricsText)

  return (
    <MetricsSection
      title={t.modelsTitle}
      description={t.modelsSubtitle}
      className={className}
    >
      <div
        className={cn(
          "grid gap-4",
          models.length > 1 && "md:grid-cols-2",
          models.length > 2 && "xl:grid-cols-3"
        )}
      >
        {models.map((model) => (
          <ModelCard key={`${model.alias}-${model.model_id}`} model={model} />
        ))}
      </div>

      {models.length < 2 && (
        <p className="flex items-start gap-2 text-caption text-text-tertiary">
          <InfoIcon className="mt-px size-3.5 shrink-0" />
          <span>{t.modelSingleNote}</span>
        </p>
      )}

      <p className="text-caption text-text-tertiary">{t.modelRetrievalShared}</p>
    </MetricsSection>
  )
}

// --------------------------------------------------------------------------- tek model kartı

function ModelCard({ model }: { model: MetricsModelResult }) {
  const t = useT(metricsText)
  const categoryLabels = useCategoryLabels()
  const { summary } = model
  const [retrievalHits, retrievalTotal] = summary.retrieval_hits

  const orderedCategories = CATEGORY_ORDER.filter(
    (category) => summary.by_category[category] !== undefined
  )
  const extraCategories = Object.keys(summary.by_category).filter(
    (key) => !CATEGORY_ORDER.includes(key as (typeof CATEGORY_ORDER)[number])
  )

  return (
    <div
      className={cn(
        "flex flex-col gap-4 rounded-lg p-4 ring-1",
        model.is_active
          ? "bg-primary/8 ring-primary/30"
          : "bg-surface-raised ring-foreground/10"
      )}
    >
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-mono text-h3 font-semibold text-foreground">
            {model.alias}
          </h3>
          {model.is_active && (
            <Badge variant="default" className="text-caption">
              {t.modelActiveBadge}
            </Badge>
          )}
        </div>
        <p
          className="truncate font-mono text-mono text-text-tertiary"
          title={model.model_id}
        >
          {model.model_id}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-caption font-medium text-text-secondary">
            {t.modelPassedLabel}
          </span>
          <span className="text-h1 leading-none font-semibold text-foreground">
            {t.ratio(summary.passed, summary.total)}
          </span>
        </div>
        <RatioBar
          passed={summary.passed}
          total={summary.total}
          ariaLabel={`${t.modelPassedLabel}: ${t.ratio(summary.passed, summary.total)}`}
        />
      </div>

      <Separator />

      <dl className="flex flex-col gap-2">
        {orderedCategories.map((category) => {
          const [passed, total] = summary.by_category[category]
          return (
            <MetricRow
              key={category}
              label={categoryLabels[category]}
              value={t.ratio(passed, total)}
            >
              <RatioBar
                passed={passed}
                total={total}
                ariaLabel={`${categoryLabels[category]}: ${t.ratio(passed, total)}`}
                className="w-16"
              />
            </MetricRow>
          )
        })}
        {extraCategories.map((category) => {
          const [passed, total] = summary.by_category[category]
          return (
            <MetricRow
              key={category}
              label={category}
              value={t.ratio(passed, total)}
            >
              <RatioBar
                passed={passed}
                total={total}
                ariaLabel={`${category}: ${t.ratio(passed, total)}`}
                className="w-16"
              />
            </MetricRow>
          )
        })}
      </dl>

      <Separator />

      <dl className="flex flex-col gap-2">
        <MetricRow
          label={t.modelRetrievalLabel}
          value={t.ratio(retrievalHits, retrievalTotal)}
        >
          <RatioBar
            passed={retrievalHits}
            total={retrievalTotal}
            ariaLabel={`${t.modelRetrievalLabel}: ${t.ratio(retrievalHits, retrievalTotal)}`}
            className="w-16"
          />
        </MetricRow>
        {/* Gecikme bilerek ÇUBUKSUZ: bu kartta her çubuk "uzun = iyi"
            okunuyor (geçen oranı, retrieval isabeti). Süre tersine çalışır;
            aynı sütunda iki yönlü çubuk karıştırmak yerine sayı bırakıldı. */}
        <MetricRow
          label={t.modelAvgLabel}
          value={t.seconds(summary.avg_seconds)}
        />
      </dl>
    </div>
  )
}

function MetricRow({
  label,
  value,
  children,
}: {
  label: string
  value: string
  children?: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-body-sm text-text-secondary">{label}</dt>
      <dd className="flex items-center gap-2">
        <span className="font-mono text-mono tabular-nums text-foreground">
          {value}
        </span>
        {children}
      </dd>
    </div>
  )
}
