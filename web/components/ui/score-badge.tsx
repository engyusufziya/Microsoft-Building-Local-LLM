import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * DESIGN_SYSTEM.md §1.2 — retrieval güven skoru bantları.
 *
 * Üst iki sınır (0.55 / 0.70) dokümanda sabit tablo değeri olarak
 * dondurulmuştur. Alt sınır ("elendi") `rag/config.py::MIN_SCORE`'a
 * bağlıdır ve backend'den gelir — bu yüzden `threshold` prop olarak
 * dışarıdan alınır, buraya asla gömülmez.
 */
export type ScoreBand = "strong" | "medium" | "weak" | "rejected"

const STRONG_MIN = 0.7
const MEDIUM_MIN = 0.55

export function getScoreBand(score: number, threshold: number): ScoreBand {
  if (score < threshold) return "rejected"
  if (score >= STRONG_MIN) return "strong"
  if (score >= MEDIUM_MIN) return "medium"
  return "weak"
}

// Renk körlüğü için: renk kaldırılsa bile bilgi ikon (dolu/boş nokta) ve
// sayısal değerle tam okunur kalmalı (DESIGN_SYSTEM.md §1.2, [!tip]).
const BAND_DOTS: Record<ScoreBand, string> = {
  strong: "●●●", // ●●●
  medium: "●●○", // ●●○
  weak: "●○○", // ●○○
  rejected: "○○○", // ○○○
}

// Tailwind'in build-time sınıf taramasını bozmamak için sınıf adları
// dinamik string birleştirme yerine tam literal olarak burada duruyor.
const BAND_TEXT_CLASS: Record<ScoreBand, string> = {
  strong: "text-score-strong",
  medium: "text-score-medium",
  weak: "text-score-weak",
  rejected: "text-score-rejected",
}

const BAND_FALLBACK_NAME: Record<ScoreBand, string> = {
  strong: "strong",
  medium: "medium",
  weak: "weak",
  rejected: "rejected",
}

export interface ScoreBadgeProps
  extends Omit<React.ComponentProps<"span">, "children"> {
  /** 0–1 aralığında retrieval güven skoru. */
  score: number
  /**
   * "Elendi" bandının alt sınırı — backend'in `MIN_SCORE`'u
   * (örn. `/api/health` yanıtından). Sabit yazma.
   */
  threshold: number
  /** Bant adı; i18n'den geçirilir (örn. t.chat.scoreBandStrong). Opsiyonel. */
  label?: string
  /** Sayısal skoru göster. Varsayılan: true. */
  showValue?: boolean
}

function ScoreBadge({
  score,
  threshold,
  label,
  showValue = true,
  className,
  ...props
}: ScoreBadgeProps) {
  const band = getScoreBand(score, threshold)
  const clamped = Math.max(0, Math.min(1, score))

  return (
    <span
      data-slot="score-badge"
      data-band={band}
      className={cn(
        "inline-flex h-5 w-fit shrink-0 items-center gap-1.5 rounded-sm border border-border bg-card px-2 py-0.5",
        className
      )}
      aria-label={`${label ?? BAND_FALLBACK_NAME[band]} — ${clamped.toFixed(2)}`}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          "font-mono text-mono leading-none tracking-[0.08em]",
          BAND_TEXT_CLASS[band]
        )}
      >
        {BAND_DOTS[band]}
      </span>
      {showValue && (
        <span
          aria-hidden="true"
          className={cn(
            "font-mono text-mono leading-none font-medium tabular-nums",
            BAND_TEXT_CLASS[band]
          )}
        >
          {clamped.toFixed(2)}
        </span>
      )}
      {label && (
        <span
          aria-hidden="true"
          className="font-sans text-caption leading-none font-medium text-muted-foreground"
        >
          {label}
        </span>
      )}
    </span>
  )
}

export { ScoreBadge }
