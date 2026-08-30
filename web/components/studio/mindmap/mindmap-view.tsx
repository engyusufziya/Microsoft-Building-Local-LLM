"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { ArtifactScreen } from "../artifact-screen"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import type { ArtifactDetail, MindMapDroppedLabel, MindMapNode } from "@/lib/types"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import {
  asMindMapPayload,
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
  const nodeRefs = React.useRef(new Map<string, HTMLDivElement | null>())

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

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
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

  // Yatay ağaç için kök ve dallar ayrılır. `layout.placed` İÇİNDEKİ İNDEKS
  // korunur: klavye gezinmesi (`jump`) o diziye göre çalışıyor ve
  // yeniden numaralandırmak Home/End/ok davranışını sessizce bozardı.
  const rootIndex = layout.placed.findIndex((p) => p.node.kind === "root")
  const rootPlaced = rootIndex >= 0 ? layout.placed[rootIndex] : undefined
  const topicPlaced = layout.placed
    .map((placed, index) => ({ placed, index }))
    .filter(({ placed }) => placed.node.kind === "topic")

  return (
    <ArtifactScreen
      artifact={artifact}
      onClose={onClose}
      slot="mindmap-view"
      meta={t.mindMapBranchCount(topicCount)}
      className={className}
    >
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {/* Künye satırı. Üst çubuğa SIĞMADIĞI için buraya alındı — ama
            KALDIRILMADI: sadakat oranı ve düşürülen etiket sayısı §11.9'un
            görünür olmasını istediği sayılar, tam-ekran düzene geçerken
            sessizce kaybolamazdı. */}
        <dl className="flex shrink-0 flex-wrap items-center gap-x-6 gap-y-1 border-b border-border px-6 py-3">
          <Metric label={t.mindMapNodeCount(topicCount)} />
          <Metric label={t.mindMapEdgeCount(payload.edges.length)} hint={t.mindMapEdgeHint} />
          <div className="flex items-baseline gap-1.5">
            <Tooltip>
              <TooltipTrigger
                render={<dt className="cursor-default text-caption text-text-tertiary" />}
              >
                {t.fidelityLabel}
              </TooltipTrigger>
              <TooltipContent>{t.fidelityHint}</TooltipContent>
            </Tooltip>
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
          <p className="w-full text-caption text-text-tertiary">{t.mindMapHint}</p>
        </dl>

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-auto px-6 py-7 xl:flex-row">
        <div className="min-w-0 flex-1">
          {/* Modernist yatay ağaç. SVG dairelerin YERİNE geçti: köşesiz
              kutular, 2px kenarlık, dik bağlantı çizgileri.

              ERİŞİLEBİLİRLİK SÖZLEŞMESİ AYNEN KORUNDU (§11.9): kap
              `role="tree"`, her düğüm `role="treeitem"` + `aria-level`
              (kök 1, konular 2) + roving tabindex, ve ok/Home/End
              gezinmesi ESKİ `handleKeyDown`'a bağlı. Değişen yalnızca
              çizim; klavye ve ekran okuyucu davranışı bir satır bile
              değişmedi.

              Alıntılar (yapraklar) treeitem DEĞİL: payload'ın düğümleri
              kök + konulardan ibaret, yaprakları da düğüm saymak ağacın
              yapısını (ve ölçülen düğüm sayısını) değiştirirdi. */}
          <div
            role="tree"
            aria-label={t.mindMapAria}
            tabIndex={-1}
            onKeyDown={handleKeyDown}
            className="flex min-w-[52rem] items-stretch outline-none"
          >
            {rootPlaced !== undefined && (
              <>
                <div className="flex w-65 shrink-0 flex-col justify-center">
                  <div
                    ref={(element) => {
                      nodeRefs.current.set(rootPlaced.node.id, element)
                    }}
                    role="treeitem"
                    aria-level={1}
                    aria-selected={rootPlaced.node.id === activeId}
                    aria-label={`${rootPlaced.node.label} — ${rootPlaced.node.size}`}
                    tabIndex={rootPlaced.node.id === activeId ? 0 : -1}
                    data-node-id={rootPlaced.node.id}
                    data-label-source={rootPlaced.node.label_source}
                    onFocus={() => setSelectedId(rootPlaced.node.id)}
                    onClick={() => jump(rootIndex)}
                    className={cn(
                      "cursor-pointer border-2 bg-primary p-4.5 text-primary-foreground outline-none",
                      rootPlaced.node.id === activeId
                        ? "border-primary"
                        : "border-text-primary"
                    )}
                  >
                    <p className="text-caption font-medium tracking-[0.1em] uppercase opacity-85">
                      {t.mindMapRootKicker}
                    </p>
                    <p className="mt-2 text-h2 font-semibold">{rootPlaced.node.label}</p>
                  </div>
                </div>

                {/* Kökten dallara giden dik omurga. */}
                <div className="relative w-11 shrink-0" aria-hidden="true">
                  <span className="absolute top-1/2 right-1/2 left-0 h-0.5 bg-text-primary" />
                  <span className="absolute top-[12%] bottom-[12%] left-1/2 w-0.5 bg-text-primary" />
                </div>
              </>
            )}

            <div className="flex flex-1 flex-col gap-3.5">
              {topicPlaced.map(({ placed, index }, branchNo) => {
                const isActive = placed.node.id === activeId
                return (
                  <div key={placed.node.id} className="flex items-stretch">
                    <div className="relative w-5.5 shrink-0" aria-hidden="true">
                      <span className="absolute top-1/2 right-0 left-0 h-0.5 bg-text-primary" />
                    </div>
                    <div
                      ref={(element) => {
                        nodeRefs.current.set(placed.node.id, element)
                      }}
                      role="treeitem"
                      aria-level={2}
                      aria-selected={isActive}
                      aria-label={`${placed.node.label} — ${placed.node.size}`}
                      tabIndex={isActive ? 0 : -1}
                      data-node-id={placed.node.id}
                      data-label-source={placed.node.label_source}
                      onFocus={() => setSelectedId(placed.node.id)}
                      onClick={() => jump(index)}
                      className={cn(
                        "w-62 shrink-0 cursor-pointer border-2 bg-background p-3.5 outline-none",
                        isActive ? "border-primary" : "border-text-primary"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-mono text-primary tabular-nums">
                          {String(branchNo + 1).padStart(2, "0")}
                        </span>
                        <span className="text-body-sm font-semibold text-text-primary">
                          {truncateLabel(placed.node.label)}
                        </span>
                      </div>
                      {placed.node.label_source === "fallback" && (
                        <p className="mt-1.5 text-caption text-warning">
                          {t.labelSourceFallback}
                        </p>
                      )}
                    </div>

                    <div className="relative w-8.5 shrink-0" aria-hidden="true">
                      <span className="absolute top-1/2 right-0 left-0 h-0.5 bg-border-strong" />
                    </div>

                    {/* Yapraklar: konunun alıntıları, geldikleri sayfayla
                        etiketli. Mockup'ın "s.N" rozeti. */}
                    <ul className="flex flex-1 flex-col justify-center gap-1.5 border-l-2 border-border-strong pl-3.5">
                      {placed.node.citations.map((citation) => (
                        <li
                          key={citation.chunk_id}
                          className="flex items-center gap-2.5 border border-border bg-surface px-2.5 py-1.5"
                        >
                          <span className="min-w-0 flex-1 truncate text-body-sm text-text-secondary">
                            {citation.source}
                          </span>
                          {citation.page > 0 && (
                            <span className="shrink-0 border border-border px-1 font-mono text-mono text-text-tertiary tabular-nums">
                              {t.pageShort(citation.page)}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          </div>
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
        <div className="px-6 pb-6">
          <DroppedLabels dropped={payload.dropped} />
        </div>
      )}
      </div>
    </ArtifactScreen>
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
