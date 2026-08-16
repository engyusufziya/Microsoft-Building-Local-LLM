"use client"

import { FileTextIcon, LoaderIcon, SparklesIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import type { ApiErrorBody, ArtifactSummary } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { useArtifacts } from "./use-artifacts"

/**
 * Studio sekmesinin içeriği — docs/FEATURE_SPEC.md §9.9.4 + §10.11.
 *
 * Faz 2'de "Üret" düğmesi GELDİ: Faz 1'de kasıtlı olarak yoktu, çünkü
 * arkasında çalışan bir üretici yoktu (basılamayan düğme, "sahte sayı
 * göstermeme" ilkesinin aynı ihlali). Artık `POST /api/artifacts` gerçek bir
 * rapor üretiyor.
 *
 * İlerleme `progress.pct` alanından gelir ve 0–100 TAM SAYIDIR; yükleme
 * akışının 0.0–1.0 ölçeğiyle paylaşılan bir yardımcı YAZILMAZ (§9.5).
 */
export interface StudioPanelProps {
  className?: string
}

export function StudioPanel({ className }: StudioPanelProps) {
  const t = useT(studio)
  const {
    artifacts,
    generating,
    pct,
    progressDetail,
    generateError,
    open,
    generate,
    openArtifact,
  } = useArtifacts()

  const errorText = (code: ApiErrorBody["code"] | null): string | null => {
    switch (code) {
      case null:
        return null
      case "INSUFFICIENT_CORPUS":
        return t.errorInsufficientCorpus
      case "MODEL_WARMING":
        return t.errorModelWarming
      case "GENERATION_FAILED":
        return t.errorGenerationFailed
      default:
        return t.errorGeneric
    }
  }

  const generateFailure = errorText(generateError)

  return (
    <div
      data-slot="studio-panel"
      className={cn("flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-4", className)}
    >
      <Button
        type="button"
        onClick={() => void generate()}
        disabled={generating}
        className="w-full"
      >
        {generating ? (
          <LoaderIcon aria-hidden="true" className="animate-spin" />
        ) : (
          <SparklesIcon aria-hidden="true" />
        )}
        {generating ? t.generating : t.generateReport}
      </Button>

      {generating ? (
        <Progress value={pct} aria-label={t.progressAria}>
          <ProgressLabel className="text-caption text-text-secondary">
            {progressDetail ?? t.generating}
          </ProgressLabel>
          <ProgressValue className="text-caption tabular-nums" />
        </Progress>
      ) : (
        <p className="text-caption text-text-tertiary">{t.generateHint}</p>
      )}

      {generateFailure !== null && (
        <p role="alert" className="text-body-sm text-danger">
          {generateFailure}
        </p>
      )}

      {artifacts !== null && artifacts.length === 0 && !generating && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-2 text-center">
          <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-text-secondary">
            <SparklesIcon aria-hidden="true" className="size-4.5" />
          </span>
          <div className="flex flex-col gap-1">
            <p className="text-h3 font-semibold text-foreground">{t.emptyTitle}</p>
            <p className="max-w-70 text-body-sm text-text-secondary">{t.emptyBody}</p>
          </div>
          <p className="text-caption text-text-tertiary">{t.emptyNote}</p>
        </div>
      )}

      {artifacts !== null && artifacts.length > 0 && (
        <ul aria-label={t.artifactListLabel} className="flex flex-col gap-2">
          {artifacts.map((artifact) => (
            <ArtifactRow
              key={artifact.id}
              artifact={artifact}
              active={open?.id === artifact.id}
              onOpen={() => void openArtifact(artifact.id)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function ArtifactRow({
  artifact,
  active,
  onOpen,
}: {
  artifact: ArtifactSummary
  active: boolean
  onOpen: () => void
}) {
  const t = useT(studio)
  return (
    <li
      className={cn(
        "flex flex-col gap-1.5 rounded-lg border bg-card p-3",
        active ? "border-primary" : "border-border"
      )}
    >
      <div className="flex items-start gap-2">
        <FileTextIcon aria-hidden="true" className="mt-0.5 size-4 text-text-tertiary" />
        <p className="flex-1 text-body-sm font-medium text-text-primary">
          {artifact.title}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {/* Oran; güven bandı rengi YOK (§9.1). */}
        <span className="font-mono text-mono text-text-tertiary tabular-nums">
          {t.fidelityLabel} {artifact.fidelity_score?.toFixed(2) ?? "—"}
        </span>
        {artifact.is_stale && (
          <Tooltip>
            <TooltipTrigger
              render={
                <span className="inline-flex h-5 w-fit shrink-0 items-center rounded-sm border border-border px-1.5 text-caption font-medium text-warning" />
              }
            >
              {t.staleBadge}
            </TooltipTrigger>
            <TooltipContent>{t.staleHint}</TooltipContent>
          </Tooltip>
        )}
        <span className="flex-1" />
        <Button type="button" variant="secondary" size="xs" onClick={onOpen}>
          {t.openArtifact}
        </Button>
      </div>
    </li>
  )
}
