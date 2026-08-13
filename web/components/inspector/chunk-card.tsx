"use client"

import * as React from "react"
import { ChevronDownIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import type { ChunkHit } from "@/lib/types"
import { getScoreBand } from "@/components/ui/score-badge"
import { ScoreBadge } from "@/components/ui/score-badge"
import { RelevanceBar } from "@/components/ui/relevance-bar"
import { OcrBadge } from "@/components/ui/ocr-badge"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { middleTruncate } from "@/components/chat/citation"

/**
 * Tek bir getirilen bölüm — FEATURE_SPEC §4.2 anatomisi.
 *
 * | Öğe          | Kaynak                  | Kural                          |
 * | Skor rozeti  | hit.score               | renk + sayı + ikon             |
 * | İlgi çubuğu  | hit.score               | genişlik = skor                |
 * | Kaynak       | hit.source              | uzunsa ORTADAN kısaltılır      |
 * | Sayfa        | hit.page                | page > 0 ise "s.4"             |
 * | OCR rozeti   | hit.via_ocr             | --ocr-badge rengi              |
 * | Önizleme     | hit.content             | 3 satır, tıklayınca tam metin  |
 * | Elendi       | !hit.passed_threshold   | %50 opaklık + "elendi" rozeti  |
 *
 * `threshold` PROP: skor bantlarının alt sınırı backend'den gelir
 * (`retrieval` olayının `threshold` alanı), buraya asla gömülmez.
 */

const BAND_LABEL_KEY = {
  strong: "scoreBandStrong",
  medium: "scoreBandMedium",
  weak: "scoreBandWeak",
  rejected: "scoreBandRejected",
} as const

export interface ChunkCardProps {
  hit: ChunkHit
  /** `retrieval` olayından gelen `MIN_SCORE`. */
  threshold: number
  /** SourceChip tıklandığında 1.5 sn boyunca true (FEATURE_SPEC §1.3, §4.1). */
  highlighted?: boolean
  className?: string
}

export function ChunkCard({
  hit,
  threshold,
  highlighted = false,
  className,
}: ChunkCardProps) {
  const t = useT(chat)
  const [expanded, setExpanded] = React.useState(false)

  const rejected = !hit.passed_threshold
  const band = getScoreBand(hit.score, threshold)
  const bandLabel = t[BAND_LABEL_KEY[band]]

  return (
    <article
      data-slot="chunk-card"
      data-rejected={rejected}
      data-highlighted={highlighted}
      className={cn(
        "flex flex-col gap-2 rounded-lg border bg-card p-3",
        "transition-[opacity,border-color,box-shadow] duration-(--duration-hover) ease-(--ease-standard)",
        // §4.2: elendi -> %50 opaklık. Bilgi gizlenmez, geri plana alınır.
        rejected ? "border-border opacity-50 hover:opacity-100" : "border-border",
        highlighted && "border-primary opacity-100 ring-3 ring-ring/50",
        className
      )}
    >
      <header className="flex flex-wrap items-center gap-1.5">
        <ScoreBadge
          score={hit.score}
          threshold={threshold}
          aria-label={t.scoreAria(bandLabel, hit.score)}
        />
        {hit.page > 0 && (
          <span
            className="font-mono text-mono font-medium text-text-tertiary tabular-nums"
            aria-label={t.pageAria(hit.page)}
          >
            {t.pageLabel(hit.page)}
          </span>
        )}
        <span className="flex-1" />
        {hit.via_ocr && (
          <Tooltip>
            <TooltipTrigger render={<span />}>
              <OcrBadge label={t.ocrBadge} />
            </TooltipTrigger>
            <TooltipContent>{t.ocrHint}</TooltipContent>
          </Tooltip>
        )}
        {rejected && (
          <Tooltip>
            <TooltipTrigger
              render={
                <span className="inline-flex h-5 w-fit shrink-0 items-center rounded-sm border border-border px-1.5 text-caption font-medium text-score-rejected" />
              }
            >
              {t.rejectedBadge}
            </TooltipTrigger>
            <TooltipContent>{t.rejectedHint}</TooltipContent>
          </Tooltip>
        )}
      </header>

      <Tooltip>
        <TooltipTrigger
          render={
            <p className="w-fit cursor-default font-mono text-mono text-text-secondary" />
          }
        >
          {middleTruncate(hit.source, 34)}
        </TooltipTrigger>
        <TooltipContent>{hit.source}</TooltipContent>
      </Tooltip>

      <RelevanceBar score={hit.score} threshold={threshold} />

      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((previous) => !previous)}
        className="flex flex-col items-start gap-1 rounded-sm text-left focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <span
          className={cn(
            "text-body-sm whitespace-pre-wrap text-text-secondary",
            !expanded && "line-clamp-3"
          )}
        >
          {hit.content}
        </span>
        <span className="inline-flex items-center gap-1 text-caption font-medium text-primary">
          <ChevronDownIcon
            aria-hidden="true"
            className={cn(
              "size-3 transition-transform duration-(--duration-hover) ease-(--ease-standard)",
              expanded && "rotate-180"
            )}
          />
          {expanded ? t.collapseChunk : t.expandChunk}
        </span>
      </button>
    </article>
  )
}
