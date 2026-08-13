"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { HealthResponse } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

export interface SystemStatusProps {
  /** `/api/health` yanıtı; henüz gelmediyse `null`. */
  health: HealthResponse | null
  /** Yerelleştirilmiş health hatası metni. */
  errorText?: string
  onRetry?: () => void
  className?: string
}

type Tone = "ready" | "warming" | "error"

// Tailwind sınıfları build-time taranıyor: dinamik string birleştirme yok.
const DOT_CLASS: Record<Tone, string> = {
  ready: "bg-success",
  warming: "bg-warning animate-pulse",
  error: "bg-danger",
}

const TEXT_CLASS: Record<Tone, string> = {
  ready: "text-success",
  warming: "text-warning",
  error: "text-danger",
}

function StatusRow({
  label,
  value,
  hint,
  mono = false,
}: {
  label: string
  value: React.ReactNode
  hint?: string
  mono?: boolean
}) {
  const labelNode = hint ? (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            className="cursor-help underline decoration-dotted underline-offset-2"
          />
        }
      >
        {label}
      </TooltipTrigger>
      <TooltipContent>{hint}</TooltipContent>
    </Tooltip>
  ) : (
    <span>{label}</span>
  )

  return (
    <div className="flex items-baseline justify-between gap-2 text-caption">
      <span className="shrink-0 text-text-secondary">{labelNode}</span>
      <span
        title={typeof value === "string" ? value : undefined}
        className={cn(
          "min-w-0 truncate text-right text-text-primary",
          mono && "font-mono text-mono tabular-nums"
        )}
      >
        {value}
      </span>
    </div>
  )
}

/**
 * Model durumu + aktif yapılandırma (FEATURE_SPEC §2.1 `HealthResponse`).
 *
 * `min_score` ve `top_k` BURADAN gösterilir çünkü ikisi de backend'in
 * yapılandırmasıdır; UI hiçbir yerde bu sayıları literal yazmaz
 * (DESIGN_SYSTEM.md §1.2 [!danger]). Sayıları görünür kılmak aynı zamanda
 * ürünün açıklanabilirlik iddiasının parçası: kullanıcı hangi eşikle
 * elendiğini görebilmeli.
 */
function SystemStatus({ health, errorText, onRetry, className }: SystemStatusProps) {
  const t = useT(sidebarText)
  const tc = useT(common)

  // Sunucuya ulaşılamıyorsa (errorText) durum her zaman "error"; son bilinen
  // yapılandırma satırları yine de gösterilir — kullanıcı neyin yürürlükte
  // olduğunu kaybetmez.
  const tone: Tone | null =
    errorText !== undefined
      ? "error"
      : health === null
        ? null
        : health.status === "ready"
          ? "ready"
          : health.status === "warming"
            ? "warming"
            : "error"

  const label =
    tone === null
      ? t.statusUnknown
      : tone === "ready"
        ? t.statusReady
        : tone === "warming"
          ? t.statusWarming
          : t.statusError

  return (
    <section
      aria-label={t.systemTitle}
      className={cn("flex flex-col gap-1.5", className)}
    >
      <div className="flex items-center gap-2">
        <h2 className="text-caption font-medium tracking-wide text-text-secondary uppercase">
          {t.systemTitle}
        </h2>
      </div>

      <p
        className={cn(
          "inline-flex items-center gap-2 text-body-sm font-medium",
          tone === null ? "text-text-secondary" : TEXT_CLASS[tone]
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "size-2 shrink-0 rounded-full",
            tone === null ? "bg-border-strong" : DOT_CLASS[tone]
          )}
        />
        {label}
      </p>

      {tone === "warming" && (
        <p className="text-caption text-text-secondary">{t.warmingHint}</p>
      )}

      {tone === "error" && (
        <div className="flex flex-col items-start gap-1.5">
          <p className="text-caption text-text-secondary">
            {errorText ?? t.healthFailed}
          </p>
          {onRetry && (
            <Button type="button" variant="outline" size="xs" onClick={onRetry}>
              {tc.retry}
            </Button>
          )}
        </div>
      )}

      {tone === null && (
        <div className="flex flex-col gap-1.5" aria-hidden="true">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-3 w-3/5" />
        </div>
      )}

      {health !== null && (
        <div className="flex flex-col gap-1">
          <StatusRow
            label={t.chatModelLabel}
            value={health.chat_model}
            mono
          />
          <StatusRow
            label={t.embeddingModelLabel}
            value={health.embedding_model}
            mono
          />
          <StatusRow
            label={t.topKLabel}
            value={health.top_k}
            hint={t.topKHint}
            mono
          />
          <StatusRow
            label={t.minScoreLabel}
            value={health.min_score.toFixed(2)}
            hint={t.minScoreHint}
            mono
          />
          <StatusRow
            label={t.ocrLabel}
            value={health.ocr_available ? t.ocrAvailable : t.ocrUnavailable}
          />
        </div>
      )}
    </section>
  )
}

export { SystemStatus }
