"use client"

import * as React from "react"
import { DownloadIcon, PrinterIcon, XIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import { artifactExportUrl } from "@/lib/api"
import type { ArtifactDetail, DroppedClaim, ReportTable } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import {
  asReportPayload,
  citationIndexByChunk,
  claimByNodePath,
  sentenceCount,
  sentenceNodePath,
} from "./report-payload"

/**
 * Rapor görüntüleyici — docs/FEATURE_SPEC.md §10.12.
 *
 * Render'ın TEK girdisi `payload_json`'dır (§10.5); hiçbir sayı burada
 * hesaplanmaz, hiçbir alan tahmin edilmez. Üç kural bu bileşende görünür
 * hâle gelir:
 *
 *  1. Rapora giren her cümle bir chunk'a bağlıdır: her cümlenin üst simgesi
 *     "Kaynaklar" listesindeki sırasıdır, `artifact_claims`'ten gelir.
 *  2. Düşürülen iddia gövdede GÖSTERİLMEZ; ayrı, açıkça etiketlenmiş bir
 *     panelde sebebiyle ve HAM COSINE skoruyla durur.
 *  3. `fidelity_score` bir ORANDIR — DESIGN_SYSTEM §1.2'nin güven bantlarıyla
 *     RENKLENDİRİLMEZ (o bantlar ham cosine için kalibre edildi, §9.1).
 *
 * Yazdırma sözleşmesi: kök `data-print="root"`, yazdırılmayacak denetimler
 * `data-print="hide"` (globals.css'teki `@media print` yalnızca bu iki
 * seçiciye dayanır — bileşen iç yapısına bağlanmaz).
 */

export interface ReportViewProps {
  artifact: ArtifactDetail
  onClose: () => void
  className?: string
}

export function ReportView({ artifact, onClose, className }: ReportViewProps) {
  const t = useT(studio)
  const payload = asReportPayload(artifact.payload)

  if (payload === null) return null

  const citationIndex = citationIndexByChunk(payload)
  const claims = claimByNodePath(artifact.claims)

  return (
    <div
      data-print="root"
      data-slot="report-view"
      className={cn("flex h-full min-h-0 flex-col overflow-y-auto", className)}
    >
      <header className="flex flex-col gap-3 border-b border-border px-5 py-4">
        <div className="flex items-start gap-2">
          <h1 className="flex-1 text-h1 font-semibold text-text-primary">
            {artifact.title}
          </h1>
          <div data-print="hide" className="flex shrink-0 items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              render={
                <a href={artifactExportUrl(artifact.id)} download aria-label={t.exportMarkdown} />
              }
            >
              <DownloadIcon aria-hidden="true" />
              {t.exportMarkdown}
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <PrinterIcon aria-hidden="true" />
              {t.print}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t.closeArtifact}
              onClick={onClose}
            >
              <XIcon aria-hidden="true" />
            </Button>
          </div>
        </div>
        <ReportMeta artifact={artifact} sentences={sentenceCount(payload)} />
      </header>

      <div className="flex flex-col gap-6 px-5 py-5">
        {payload.sections.map((section, sectionIndex) => (
          <section key={section.id} className="flex flex-col gap-2">
            <h2 className="text-h2 font-semibold text-text-primary">{section.title}</h2>
            <p className="text-caption text-text-tertiary">
              {t.sourceCountLabel(section.context_chunk_ids.length)}
            </p>
            {section.paragraphs.map((paragraph, paragraphIndex) => (
              <p key={paragraphIndex} className="text-body text-text-secondary">
                {paragraph.sentences.map((sentence, sentenceIndex) => {
                  const nodePath = sentenceNodePath(
                    sectionIndex,
                    paragraphIndex,
                    sentenceIndex
                  )
                  const claim = claims.get(nodePath)
                  const marker =
                    claim?.chunk_id == null
                      ? null
                      : citationIndex.get(claim.chunk_id) ?? null
                  return (
                    <React.Fragment key={nodePath}>
                      <span data-node-path={nodePath}>{sentence}</span>
                      {marker !== null && claim?.citation != null && (
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <sup className="ml-0.5 cursor-default font-mono text-mono text-primary" />
                            }
                          >
                            {marker}
                          </TooltipTrigger>
                          <TooltipContent>{claim.citation}</TooltipContent>
                        </Tooltip>
                      )}{" "}
                    </React.Fragment>
                  )
                })}
              </p>
            ))}
          </section>
        ))}

        {payload.tables.map((table) => (
          <CoverageTable key={table.id} table={table} heading={t.tablesHeading} />
        ))}

        {payload.citations.length > 0 && (
          <section className="flex flex-col gap-2">
            <h2 className="text-h2 font-semibold text-text-primary">
              {t.citationsHeading}
            </h2>
            <ol className="flex flex-col gap-1">
              {payload.citations.map((citation, index) => (
                <li
                  key={citation.chunk_id}
                  className="font-mono text-mono text-text-secondary"
                >
                  <span className="text-primary">{index + 1}.</span> {citation.citation}
                </li>
              ))}
            </ol>
          </section>
        )}

        {payload.dropped.length > 0 && <DroppedPanel dropped={payload.dropped} />}
      </div>
    </div>
  )
}

/**
 * Üst düzey sayılar. `fidelity_score` ve `dropped_count` YAN YANA ve AYRI
 * gösterilir — tek bir "kalite skoru"na katlanmazlar (§10.6).
 */
function ReportMeta({
  artifact,
  sentences,
}: {
  artifact: ArtifactDetail
  sentences: number
}) {
  const t = useT(studio)
  return (
    <dl className="flex flex-wrap items-center gap-x-6 gap-y-1">
      <div className="flex items-baseline gap-1.5">
        <Tooltip>
          <TooltipTrigger render={<dt className="cursor-default text-caption text-text-tertiary" />}>
            {t.fidelityLabel}
          </TooltipTrigger>
          <TooltipContent>{t.fidelityHint}</TooltipContent>
        </Tooltip>
        {/* Renk YOK: bu bir oran, retrieval güven bandı değil (§9.1). */}
        <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
          {artifact.fidelity_score === null
            ? "—"
            : artifact.fidelity_score.toFixed(2)}
        </dd>
      </div>
      <div className="flex items-baseline gap-1.5">
        <dt className="text-caption text-text-tertiary">{t.claimCountLabel}</dt>
        <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
          {sentences}
        </dd>
      </div>
      <div className="flex items-baseline gap-1.5">
        <dt className="text-caption text-text-tertiary">{t.droppedCountLabel}</dt>
        <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
          {artifact.dropped_count}
        </dd>
      </div>
    </dl>
  )
}

function CoverageTable({ table, heading }: { table: ReportTable; heading: string }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-h2 font-semibold text-text-primary">{heading}</h2>
      <Card>
        <CardHeader>
          <CardTitle className="text-h3">{table.title}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Geniş matris kendi içinde kayar; sayfa yatay kaymaz. */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-body-sm">
              <thead>
                <tr>
                  {table.columns.map((column) => (
                    <th
                      key={column}
                      scope="col"
                      className="border-b border-border px-2 py-1.5 text-left font-medium text-text-secondary"
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row) => (
                  <tr key={String(row[0])}>
                    {row.map((cell, index) => (
                      <td
                        key={index}
                        className={cn(
                          "border-b border-border px-2 py-1.5 text-text-secondary",
                          index > 0 && "font-mono text-mono tabular-nums"
                        )}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}

/**
 * §10.12: düşürülen iddialar rapor gövdesinde gösterilmez; burada sebebiyle
 * ve HAM COSINE skoruyla durur. Ürün sınırını gizlemez ama doğrulanamamış
 * cümleyi rapor içeriği gibi de sunmaz.
 */
function DroppedPanel({ dropped }: { dropped: DroppedClaim[] }) {
  const t = useT(studio)
  const reasonLabel = (reason: DroppedClaim["reason"]): string =>
    reason === "unsupported"
      ? t.droppedReasonUnsupported
      : reason === "weak"
        ? t.droppedReasonWeak
        : t.droppedReasonUnverifiedTerms
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-h2 font-semibold text-text-primary">{t.droppedHeading}</h2>
      <p className="text-body-sm text-text-secondary">{t.droppedIntro}</p>
      <ul className="flex flex-col gap-2">
        {dropped.map((claim, index) => (
          <li
            key={index}
            className="flex flex-col gap-1 rounded-lg border border-border bg-card p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-caption font-medium text-warning">
                {reasonLabel(claim.reason)}
              </span>
              {claim.score !== null && (
                <span className="font-mono text-mono text-text-tertiary tabular-nums">
                  {claim.score.toFixed(4)}
                </span>
              )}
            </div>
            <p className="text-body-sm text-text-secondary">{claim.text}</p>
            {claim.terms.length > 0 && (
              <p className="font-mono text-mono text-text-tertiary">
                {t.droppedTerms(claim.terms)}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
