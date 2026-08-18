"use client"

import {
  FileTextIcon,
  ListChecksIcon,
  LoaderIcon,
  NetworkIcon,
  SparklesIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import type { ApiErrorBody, ArtifactSummary } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { useArtifacts, type ArtifactKind } from "./use-artifacts"

/**
 * Studio sekmesinin içeriği — docs/FEATURE_SPEC.md §9.9.4 · §10.11 · §11.9.
 *
 * Düğmeler üreticiler GERÇEKTEN çalıştıkça geldi: Faz 1'de hiç yoktu (basılamayan
 * düğme, "sahte sayı göstermeme" ilkesinin aynı ihlali), Faz 2'de rapor,
 * Faz 3'te zihin haritası. Quiz Faz 4'te gelecek.
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
    generatingKind,
    pct,
    progressDetail,
    generateError,
    open,
    generate,
    openArtifact,
  } = useArtifacts()

  const generating = generatingKind !== null

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
      <div className="flex flex-col gap-1.5">
        <GenerateButton
          kind="report"
          label={t.generateReport}
          icon={<FileTextIcon aria-hidden="true" />}
          generatingKind={generatingKind}
          onGenerate={generate}
        />
        <GenerateButton
          kind="mindmap"
          label={t.generateMindMap}
          icon={<NetworkIcon aria-hidden="true" />}
          generatingKind={generatingKind}
          onGenerate={generate}
        />
      </div>

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
            <p className="max-w-70 text-body-sm text-text-secondary">{t.emptyBodyAll}</p>
          </div>
          <p className="text-caption text-text-tertiary">{t.emptyNoteAll}</p>
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

function GenerateButton({
  kind,
  label,
  icon,
  generatingKind,
  onGenerate,
}: {
  kind: ArtifactKind
  label: string
  icon: React.ReactNode
  generatingKind: ArtifactKind | null
  onGenerate: (kind: ArtifactKind) => Promise<void>
}) {
  const t = useT(studio)
  const isThis = generatingKind === kind
  return (
    <Button
      type="button"
      variant={kind === "report" ? "default" : "secondary"}
      onClick={() => void onGenerate(kind)}
      // Üretim sürerken ÜÇÜ de kapalı: backend model kilidini üretim boyunca
      // tutuyor, ikinci istek kilidin arkasında donmuş gibi görünürdü (§9.8).
      disabled={generatingKind !== null}
      data-kind={kind}
      className="w-full"
    >
      {isThis ? <LoaderIcon aria-hidden="true" className="animate-spin" /> : icon}
      {isThis ? t.generating : label}
    </Button>
  )
}

const KIND_ICON: Record<ArtifactSummary["kind"], React.ReactNode> = {
  report: <FileTextIcon aria-hidden="true" className="mt-0.5 size-4 text-text-tertiary" />,
  mindmap: <NetworkIcon aria-hidden="true" className="mt-0.5 size-4 text-text-tertiary" />,
  quiz: <ListChecksIcon aria-hidden="true" className="mt-0.5 size-4 text-text-tertiary" />,
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
  const kindLabel = { report: t.kindReport, mindmap: t.kindMindMap, quiz: t.kindQuiz }[
    artifact.kind
  ]
  return (
    <li
      data-kind={artifact.kind}
      className={cn(
        "flex flex-col gap-1.5 rounded-lg border bg-card p-3",
        active ? "border-primary" : "border-border"
      )}
    >
      <div className="flex items-start gap-2">
        {KIND_ICON[artifact.kind]}
        <p className="flex-1 text-body-sm font-medium text-text-primary">
          {artifact.title}
        </p>
        <span className="shrink-0 rounded-sm border border-border px-1.5 text-caption text-text-secondary">
          {kindLabel}
        </span>
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
