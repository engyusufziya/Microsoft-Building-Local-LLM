"use client"

import * as React from "react"
import {
  ChartNoAxesColumnIcon,
  FlaskConicalIcon,
  GaugeIcon,
  LayersIcon,
  TargetIcon,
  TimerIcon,
  TriangleAlertIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { ApiRequestError, getMetrics } from "@/lib/api"
import { useLocale, useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { metrics as metricsText } from "@/lib/i18n/metrics"
import type { MetricsResponse } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
  MetricsSection,
  RatioBar,
  StatTile,
} from "@/components/metrics/metric-primitives"
import { CATEGORY_ORDER, useCategoryLabels } from "@/components/metrics/categories"
import { ThresholdChart } from "@/components/metrics/threshold-chart"
import { ModelComparison } from "@/components/metrics/model-comparison"
import { EvalTable } from "@/components/metrics/eval-table"

/**
 * Metrics sayfası — FEATURE_SPEC §1.5, §6.
 *
 * Veri `/api/metrics`'ten gelir ve dosya henüz üretilmemişse backend
 * 503 + `METRICS_NOT_GENERATED` döner. Bu durum jenerik hatadan AYRI ele
 * alınır: kullanıcıya "değerlendirme henüz çalıştırılmadı" denir ve hiçbir
 * sayı gösterilmez. Örnek/varsayılan değer basmak, ölçülmüş bir sonuç gibi
 * okunurdu (§6.3).
 */

type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: MetricsResponse }
  | { status: "not-generated" }
  | { status: "error"; message: string }

export interface MetricsPageProps {
  /**
   * Veri kaynağı. Varsayılan `getMetrics`. Önizleme/test için enjekte
   * edilebilir — DİKKAT: referansı kararlı olmalı (modül düzeyinde tanımlı
   * bir fonksiyon), her render'da yeni bir kapanış geçilirse istek döngüye
   * girer.
   */
  load?: () => Promise<MetricsResponse>
  className?: string
}

export function MetricsPage({ load = getMetrics, className }: MetricsPageProps) {
  const t = useT(metricsText)
  const tc = useT(common)
  const [state, setState] = React.useState<LoadState>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    load().then(
      (data) => {
        if (!cancelled) setState({ status: "ready", data })
      },
      (error: unknown) => {
        if (cancelled) return
        if (error instanceof ApiRequestError && error.code === "METRICS_NOT_GENERATED") {
          setState({ status: "not-generated" })
          return
        }
        setState({
          status: "error",
          message: error instanceof Error ? error.message : tc.errorGeneric,
        })
      }
    )
    return () => {
      cancelled = true
    }
    // `tc.errorGeneric` yalnızca hata metni için okunuyor; dile göre yeniden
    // istek atmamak için bağımlılık listesinde bilinçli olarak yok.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, attempt])

  const retry = () => {
    setState({ status: "loading" })
    setAttempt((n) => n + 1)
  }

  return (
    <div
      className={cn(
        "mx-auto flex w-full max-w-[76rem] flex-col gap-8 px-6 py-8",
        className
      )}
    >
      <header className="flex flex-col gap-2">
        <h1 className="text-display font-semibold text-foreground">{t.pageTitle}</h1>
        <p className="max-w-prose text-body text-text-secondary">{t.pageSubtitle}</p>
        {state.status === "ready" && <GeneratedAt isoDate={state.data.generated_at} />}
      </header>

      {state.status === "loading" && <MetricsSkeleton label={t.loadingLabel} />}
      {state.status === "not-generated" && <NotGeneratedState />}
      {state.status === "error" && (
        <ErrorState message={state.message} onRetry={retry} retryLabel={tc.retry} />
      )}
      {state.status === "ready" && <MetricsContent data={state.data} />}
    </div>
  )
}

// --------------------------------------------------------------------------- içerik

export interface MetricsContentProps {
  data: MetricsResponse
}

/**
 * Yalnızca sunum. Ayrı export edilmesinin sebebi: veri getirmeden (önizleme,
 * test) tam sayfayı render edebilmek.
 */
export function MetricsContent({ data }: MetricsContentProps) {
  const t = useT(metricsText)
  const categoryLabels = useCategoryLabels()

  const activeModel = data.models.find((model) => model.is_active) ?? data.models[0]

  return (
    <div className="flex flex-col gap-8">
      <ConfigStrip data={data} />

      {activeModel ? (
        <section className="flex flex-col gap-4">
          <h2 className="text-h2 font-semibold text-foreground">{t.summaryHeading}</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              label={t.passedLabel}
              value={t.ratio(activeModel.summary.passed, activeModel.summary.total)}
              help={t.passedHelp}
              icon={<ChartNoAxesColumnIcon className="size-3.5" aria-hidden="true" />}
            >
              <RatioBar
                passed={activeModel.summary.passed}
                total={activeModel.summary.total}
                ariaLabel={`${t.passedLabel}: ${t.ratio(
                  activeModel.summary.passed,
                  activeModel.summary.total
                )}`}
              />
            </StatTile>

            <CategoryTile
              label={t.categoryLabel}
              help={t.categoryHelp}
              byCategory={activeModel.summary.by_category}
              categoryLabels={categoryLabels}
            />

            <StatTile
              label={t.retrievalLabel}
              value={t.ratio(
                activeModel.summary.retrieval_hits[0],
                activeModel.summary.retrieval_hits[1]
              )}
              help={t.retrievalHelp}
              icon={<TargetIcon className="size-3.5" aria-hidden="true" />}
            >
              <RatioBar
                passed={activeModel.summary.retrieval_hits[0]}
                total={activeModel.summary.retrieval_hits[1]}
                ariaLabel={`${t.retrievalLabel}: ${t.ratio(
                  activeModel.summary.retrieval_hits[0],
                  activeModel.summary.retrieval_hits[1]
                )}`}
              />
            </StatTile>

            <StatTile
              label={t.avgSecondsLabel}
              value={t.seconds(activeModel.summary.avg_seconds)}
              help={t.avgSecondsHelp}
              icon={<TimerIcon className="size-3.5" aria-hidden="true" />}
            />
          </div>
        </section>
      ) : (
        <MetricsSection title={t.emptyModelsTitle}>
          <p className="text-body-sm text-text-secondary">{t.emptyModelsBody}</p>
        </MetricsSection>
      )}

      <ThresholdChart sweep={data.threshold_sweep} threshold={data.config.min_score} />

      {data.models.length > 0 && <ModelComparison models={data.models} />}
      {data.models.length > 0 && <EvalTable models={data.models} />}

      <p className="text-caption text-text-tertiary">{t.sourceNote}</p>
    </div>
  )
}

// --------------------------------------------------------------------------- kategori kutusu

function CategoryTile({
  label,
  help,
  byCategory,
  categoryLabels,
}: {
  label: string
  help: string
  byCategory: Record<string, [number, number]>
  categoryLabels: Record<(typeof CATEGORY_ORDER)[number], string>
}) {
  const t = useT(metricsText)
  const known = CATEGORY_ORDER.filter((category) => byCategory[category] !== undefined)
  const extra = Object.keys(byCategory).filter(
    (key) => !CATEGORY_ORDER.includes(key as (typeof CATEGORY_ORDER)[number])
  )
  const entries = [
    ...known.map((category) => ({ key: category, label: categoryLabels[category] })),
    ...extra.map((category) => ({ key: category, label: category })),
  ]

  return (
    <div className="flex flex-col gap-3 rounded-lg bg-surface p-4 ring-1 ring-foreground/10">
      <div className="flex items-center gap-2 text-caption font-medium text-text-secondary">
        <LayersIcon className="size-3.5" aria-hidden="true" />
        <span>{label}</span>
      </div>
      <dl className="flex flex-col gap-2">
        {entries.map((entry) => {
          const [passed, total] = byCategory[entry.key]
          return (
            <div key={entry.key} className="flex items-center justify-between gap-3">
              <dt className="text-body-sm text-text-secondary">{entry.label}</dt>
              <dd className="flex items-center gap-2">
                <span className="font-mono text-mono tabular-nums text-foreground">
                  {t.ratio(passed, total)}
                </span>
                <RatioBar
                  passed={passed}
                  total={total}
                  ariaLabel={`${entry.label}: ${t.ratio(passed, total)}`}
                  className="w-12"
                />
              </dd>
            </div>
          )
        })}
      </dl>
      <p className="text-caption text-text-tertiary">{help}</p>
    </div>
  )
}

// --------------------------------------------------------------------------- yapılandırma şeridi

function ConfigStrip({ data }: { data: MetricsResponse }) {
  const t = useT(metricsText)
  const items = [
    { label: t.configThreshold, value: t.score(data.config.min_score) },
    { label: t.configTopK, value: String(data.config.top_k) },
    { label: t.configChunkWords, value: t.words(data.config.chunk_words) },
    { label: t.configOverlap, value: t.words(data.config.chunk_overlap_words) },
    { label: t.corpusDocuments, value: String(data.corpus.document_count) },
    { label: t.corpusChunks, value: String(data.corpus.chunk_count) },
  ]

  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 text-caption font-medium text-text-secondary">
        <GaugeIcon className="size-3.5" aria-hidden="true" />
        {t.configHeading}
      </h2>
      <dl className="flex flex-wrap items-center gap-x-6 gap-y-3">
        {items.map((item, index) => (
          <React.Fragment key={item.label}>
            {index > 0 && (
              <Separator orientation="vertical" className="hidden h-6 sm:block" />
            )}
            <div className="flex items-baseline gap-2">
              <dt className="text-caption text-text-tertiary">{item.label}</dt>
              <dd className="font-mono text-mono tabular-nums text-foreground">
                {item.value}
              </dd>
            </div>
          </React.Fragment>
        ))}
      </dl>
    </section>
  )
}

// --------------------------------------------------------------------------- ölçüm zamanı

function GeneratedAt({ isoDate }: { isoDate: string }) {
  const t = useT(metricsText)
  const { locale } = useLocale()
  const parsed = new Date(isoDate)
  const formatted = Number.isNaN(parsed.getTime())
    ? isoDate
    : new Intl.DateTimeFormat(locale === "tr" ? "tr-TR" : "en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(parsed)

  return (
    <p className="font-mono text-mono text-text-tertiary">{t.generatedAt(formatted)}</p>
  )
}

// --------------------------------------------------------------------------- durumlar

function MetricsSkeleton({ label }: { label: string }) {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label={label}
    >
      <div className="flex flex-wrap gap-4">
        {[0, 1, 2, 3, 4, 5].map((key) => (
          <Skeleton key={key} className="h-4 w-28" />
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((key) => (
          <Skeleton key={key} className="h-32 rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-[26rem] rounded-lg" />
      <Skeleton className="h-64 rounded-lg" />
      <Skeleton className="h-80 rounded-lg" />
    </div>
  )
}

function NotGeneratedState() {
  const t = useT(metricsText)
  const commands = [t.commandRunEval, t.commandSweep, t.commandCompare]

  return (
    <div className="flex flex-col items-start gap-4 rounded-lg bg-surface p-6 ring-1 ring-foreground/10">
      <span className="flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary">
        <FlaskConicalIcon className="size-5" aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-2">
        <h2 className="text-h2 font-semibold text-foreground">{t.notGeneratedTitle}</h2>
        <p className="max-w-prose text-body-sm text-text-secondary">
          {t.notGeneratedBody}
        </p>
      </div>
      <div className="flex w-full flex-col gap-2">
        <p className="text-caption font-medium text-text-secondary">
          {t.notGeneratedHowTo}
        </p>
        <ul className="flex flex-col gap-1.5">
          {commands.map((command) => (
            <li key={command}>
              <code className="inline-block rounded-sm bg-surface-raised px-2 py-1 font-mono text-mono text-text-primary ring-1 ring-foreground/10">
                {command}
              </code>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function ErrorState({
  message,
  onRetry,
  retryLabel,
}: {
  message: string
  onRetry: () => void
  retryLabel: string
}) {
  const t = useT(metricsText)
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg bg-surface p-6 ring-1 ring-danger/30">
      <span className="flex items-center gap-2 text-h3 font-semibold text-foreground">
        <TriangleAlertIcon className="size-4 text-danger" aria-hidden="true" />
        {t.errorTitle}
      </span>
      <p className="max-w-prose text-body-sm text-text-secondary">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {retryLabel}
      </Button>
    </div>
  )
}
