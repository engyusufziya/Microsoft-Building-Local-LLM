"use client"

import * as React from "react"
import { PrinterIcon, XIcon, DownloadIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import { artifactExportUrl } from "@/lib/api"
import type { ArtifactDetail, MindMapDroppedLabel, MindMapNode } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import {
  asMindMapPayload,
  edgeWidth,
  layoutMindMap,
  truncateLabel,
} from "./mindmap-payload"

/**
 * Zihin haritası görüntüleyici — docs/FEATURE_SPEC.md §11.9.
 *
 * Render'ın TEK girdisi `payload_json`'dır (§11.5); burada hiçbir düğüm ya da
 * kenar hesaplanmaz, yalnızca YERLEŞTİRİLİR. Üç kural bu bileşende görünür:
 *
 *  1. Her düğüm bir chunk kümesidir: seçili düğümün kaynakları yanda,
 *     `citation` biçimiyle listelenir (§11.5).
 *  2. `label_source === "fallback"` GÖSTERİLİR — modelin etiketi kapıdan
 *     geçemediğinde düğüm silinmez, adı korpustan türer ve bu saklanmaz.
 *  3. Kenar ağırlığı ham cosine'dır ama RENKLE değil KALINLIKLA gösterilir:
 *     DESIGN_SYSTEM §1.2 bantları sorgu→chunk için kalibre edildi (§11.6).
 *
 * Erişilebilirlik (§11.9, WCAG AA): SVG `role="tree"`, düğümler
 * `role="treeitem"`, roving tabindex + ok tuşları/Home/End ile gezinme.
 * `d3-hierarchy` KURULMADI — gerekçe mindmap-payload.ts.
 */

export interface MindMapViewProps {
  artifact: ArtifactDetail
  onClose: () => void
  className?: string
}

export function MindMapView({ artifact, onClose, className }: MindMapViewProps) {
  const t = useT(studio)
  const payload = asMindMapPayload(artifact.payload)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const nodeRefs = React.useRef(new Map<string, SVGGElement | null>())

  const layout = React.useMemo(
    () => (payload === null ? null : layoutMindMap(payload)),
    [payload]
  )

  if (payload === null || layout === null) return null

  const focusable = layout.placed
  const activeId = selectedId ?? focusable[0]?.node.id ?? null
  const selected = focusable.find((p) => p.node.id === activeId)?.node ?? null

  const move = (delta: number) => {
    const index = focusable.findIndex((p) => p.node.id === activeId)
    const next = focusable[(index + delta + focusable.length) % focusable.length]
    setSelectedId(next.node.id)
    nodeRefs.current.get(next.node.id)?.focus()
  }

  const jump = (index: number) => {
    const target = focusable[index]
    setSelectedId(target.node.id)
    nodeRefs.current.get(target.node.id)?.focus()
  }

  const handleKeyDown = (event: React.KeyboardEvent<SVGSVGElement>) => {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault()
        move(1)
        break
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault()
        move(-1)
        break
      case "Home":
        event.preventDefault()
        jump(0)
        break
      case "End":
        event.preventDefault()
        jump(focusable.length - 1)
        break
      default:
        break
    }
  }

  const topicCount = payload.nodes.filter((n) => n.kind === "topic").length

  return (
    <div
      data-print="root"
      data-slot="mindmap-view"
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
        <dl className="flex flex-wrap items-center gap-x-6 gap-y-1">
          <Metric label={t.mindMapNodeCount(topicCount)} />
          <Metric
            label={t.mindMapEdgeCount(payload.edges.length)}
            hint={t.mindMapEdgeHint}
          />
          <div className="flex items-baseline gap-1.5">
            <Tooltip>
              <TooltipTrigger
                render={<dt className="cursor-default text-caption text-text-tertiary" />}
              >
                {t.fidelityLabel}
              </TooltipTrigger>
              <TooltipContent>{t.fidelityHint}</TooltipContent>
            </Tooltip>
            {/* Renk YOK: bu bir oran, retrieval güven bandı değil (§9.1). */}
            <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
              {artifact.fidelity_score === null ? "—" : artifact.fidelity_score.toFixed(2)}
            </dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-caption text-text-tertiary">{t.droppedCountLabel}</dt>
            <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
              {artifact.dropped_count}
            </dd>
          </div>
        </dl>
        <p data-print="hide" className="text-caption text-text-tertiary">
          {t.mindMapHint}
        </p>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 px-5 py-5 xl:flex-row">
        <div className="min-w-0 flex-1">
          <svg
            role="tree"
            aria-label={t.mindMapAria}
            tabIndex={-1}
            onKeyDown={handleKeyDown}
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            className="h-auto w-full max-w-full"
          >
            {payload.edges.map((edge) => {
              const from = layout.byId.get(edge.from)
              const to = layout.byId.get(edge.to)
              if (from === undefined || to === undefined) return null
              return (
                <line
                  key={`${edge.from}-${edge.to}`}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke="var(--border-strong)"
                  strokeWidth={edgeWidth(edge)}
                  strokeDasharray="4 4"
                />
              )
            })}
            {layout.placed
              .filter((p) => p.node.kind === "topic")
              .map((p) => {
                const root = layout.byId.get("root")
                if (root === undefined) return null
                return (
                  <line
                    key={`root-${p.node.id}`}
                    x1={root.x}
                    y1={root.y}
                    x2={p.x}
                    y2={p.y}
                    stroke="var(--border)"
                    strokeWidth={1.5}
                  />
                )
              })}

            {layout.placed.map((p, index) => {
              const isRoot = p.node.kind === "root"
              const isActive = p.node.id === activeId
              const radius = isRoot ? 34 : 12 + Math.min(p.node.size, 12)
              return (
                <g
                  key={p.node.id}
                  ref={(element) => {
                    nodeRefs.current.set(p.node.id, element)
                  }}
                  role="treeitem"
                  aria-level={isRoot ? 1 : 2}
                  aria-selected={isActive}
                  aria-label={`${p.node.label} — ${p.node.size}`}
                  tabIndex={isActive ? 0 : -1}
                  data-node-id={p.node.id}
                  data-label-source={p.node.label_source}
                  onFocus={() => setSelectedId(p.node.id)}
                  onClick={() => jump(index)}
                  className="cursor-pointer outline-none"
                >
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={radius}
                    fill={isRoot ? "var(--primary)" : "var(--surface)"}
                    stroke={isActive ? "var(--primary)" : "var(--border-strong)"}
                    strokeWidth={isActive ? 3 : 1.5}
                  />
                  {!isRoot && (
                    <text
                      x={p.x}
                      y={p.y + 4}
                      textAnchor="middle"
                      className="fill-[var(--text-secondary)] font-mono text-[11px]"
                    >
                      {p.node.size}
                    </text>
                  )}
                  <text
                    x={p.anchor === "middle" ? p.x : p.x + (p.anchor === "start" ? radius + 8 : -(radius + 8))}
                    y={p.anchor === "middle" ? p.y + radius + 18 : p.y + 4}
                    textAnchor={p.anchor}
                    className={cn(
                      "text-[13px]",
                      isRoot
                        ? "fill-[var(--text-primary)] font-semibold"
                        : "fill-[var(--text-primary)]"
                    )}
                  >
                    {truncateLabel(p.node.label)}
                  </text>
                  {p.node.label_source === "fallback" && (
                    <text
                      x={p.anchor === "middle" ? p.x : p.x + (p.anchor === "start" ? radius + 8 : -(radius + 8))}
                      y={p.anchor === "middle" ? p.y + radius + 32 : p.y + 18}
                      textAnchor={p.anchor}
                      className="fill-[var(--warning)] text-[11px]"
                    >
                      {t.labelSourceFallback}
                    </text>
                  )}
                </g>
              )
            })}
          </svg>
          {payload.edges.length === 0 && (
            <p className="mt-2 text-caption text-text-tertiary">{t.mindMapNoEdges}</p>
          )}
        </div>

        <aside className="flex w-full shrink-0 flex-col gap-2 xl:w-80">
          <h2 className="text-h3 font-semibold text-text-primary">{t.nodeSourcesHeading}</h2>
          {selected === null ? (
            <p className="text-body-sm text-text-secondary">{t.nodeSelectHint}</p>
          ) : (
            <NodeSources node={selected} />
          )}
        </aside>
      </div>

      {payload.dropped.length > 0 && (
        <div className="px-5 pb-5">
          <DroppedLabels dropped={payload.dropped} />
        </div>
      )}
    </div>
  )
}

function Metric({ label, hint }: { label: string; hint?: string }) {
  if (hint === undefined) {
    return <dd className="text-caption text-text-secondary">{label}</dd>
  }
  return (
    <Tooltip>
      <TooltipTrigger render={<dd className="cursor-default text-caption text-text-secondary" />}>
        {label}
      </TooltipTrigger>
      <TooltipContent>{hint}</TooltipContent>
    </Tooltip>
  )
}

function NodeSources({ node }: { node: MindMapNode }) {
  const t = useT(studio)
  return (
    <div className="flex flex-col gap-2">
      <p className="text-body-sm font-medium text-text-primary">{node.label}</p>
      {node.label_source === "fallback" && (
        <p className="text-caption text-warning">{t.labelSourceFallbackHint}</p>
      )}
      <ol className="flex flex-col gap-1">
        {node.citations.map((citation) => (
          <li
            key={citation.chunk_id}
            className="font-mono text-mono text-text-secondary"
          >
            {citation.citation}
          </li>
        ))}
      </ol>
    </div>
  )
}

/**
 * §11.5: kapıdan geçemeyen etiket ÖNERİLERİ. Haritada gösterilmezler ama
 * varlıkları gizlenmez — raporun "çıkarılan iddialar" panelinin aynı kuralı.
 */
function DroppedLabels({ dropped }: { dropped: MindMapDroppedLabel[] }) {
  const t = useT(studio)
  const reasonLabel = (reason: MindMapDroppedLabel["reason"]): string => {
    switch (reason) {
      case "unsupported":
        return t.droppedReasonUnsupported
      case "weak":
        return t.droppedReasonWeak
      case "unverified_terms":
        return t.droppedReasonUnverifiedTerms
      default:
        return t.droppedReasonLabelInvalid
    }
  }
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-h2 font-semibold text-text-primary">{t.droppedLabelsHeading}</h2>
      <p className="text-body-sm text-text-secondary">{t.droppedIntro}</p>
      <ul className="flex flex-col gap-2">
        {dropped.map((item, index) => (
          <li
            key={index}
            className="flex flex-col gap-1 rounded-lg border border-border bg-card p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-caption font-medium text-warning">
                {reasonLabel(item.reason)}
              </span>
              {item.score !== null && (
                <span className="font-mono text-mono text-text-tertiary tabular-nums">
                  {item.score.toFixed(4)}
                </span>
              )}
            </div>
            {item.text !== "" && (
              <p className="text-body-sm text-text-secondary">{item.text}</p>
            )}
            {item.terms.length > 0 && (
              <p className="font-mono text-mono text-text-tertiary">
                {t.droppedTerms(item.terms)}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
