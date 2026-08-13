"use client"

import { Progress as ProgressPrimitive } from "@base-ui/react/progress"

import { cn } from "@/lib/utils"
import { ProgressTrack, ProgressIndicator } from "@/components/ui/progress"
import { getScoreBand, type ScoreBand } from "@/components/ui/score-badge"

// Tailwind'in build-time sınıf taramasını bozmamak için literal sınıf adları.
const BAND_BG_CLASS: Record<ScoreBand, string> = {
  strong: "bg-score-strong",
  medium: "bg-score-medium",
  weak: "bg-score-weak",
  rejected: "bg-score-rejected",
}

export interface RelevanceBarProps
  extends Omit<ProgressPrimitive.Root.Props, "value" | "children"> {
  /** 0–1 aralığında retrieval güven skoru. */
  score: number
  /** Backend'in `MIN_SCORE`'u — "elendi" bandı sınırı, sabit yazma. */
  threshold: number
}

/**
 * Chunk/kaynak listelerinde kompakt bir güven göstergesi.
 * DESIGN_SYSTEM.md §1.2'deki dört bant rengini kullanır (bkz. score-badge.tsx
 * içindeki `getScoreBand`), böylece ScoreBadge ile aynı eşiklerde tutarlı
 * kalır. shadcn'in Progress primitive'i üzerine kurulur (ARIA progressbar
 * semantiği bedava gelir).
 */
function RelevanceBar({
  score,
  threshold,
  className,
  ...props
}: RelevanceBarProps) {
  const clamped = Math.max(0, Math.min(1, score))
  const percent = Math.round(clamped * 100)
  const band = getScoreBand(score, threshold)

  return (
    <ProgressPrimitive.Root
      value={percent}
      data-slot="relevance-bar"
      data-band={band}
      className={cn("flex w-full items-center", className)}
      {...props}
    >
      <ProgressTrack className="h-1.5 rounded-sm">
        <ProgressIndicator
          className={cn(
            "rounded-sm transition-[width] duration-(--duration-panel) ease-(--ease-panel)",
            BAND_BG_CLASS[band]
          )}
        />
      </ProgressTrack>
    </ProgressPrimitive.Root>
  )
}

export { RelevanceBar }
