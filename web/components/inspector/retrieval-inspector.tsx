"use client"

import * as React from "react"
import { SearchIcon, TelescopeIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import type { ChunkHit } from "@/lib/types"
import { Skeleton } from "@/components/ui/skeleton"
import { selectedAssistant, useChatState } from "@/components/chat/chat-store"
import { ChunkCard } from "@/components/inspector/chunk-card"

/**
 * Retrieval Inspector — bu ürünün açıklanabilirlik paneli.
 *
 * Durum makinesi (FEATURE_SPEC §4.1):
 *   Boş -> Aranıyor -> Dolu -> (Vurgulu -> Dolu) -> Aranıyor …
 * Kök elemandaki `data-state` bu makineyi DOM'da da görünür kılar.
 *
 * KRİTİK ZAMANLAMA (§1.2): panel `retrieval` olayıyla dolar (~0.3 sn),
 * `done` BEKLENMEZ. Kullanıcı ilk kelimeden (TTFT 0.74 sn) önce hangi
 * bölümlerin bulunduğunu görür — sistemin ne yaptığı cevaptan önce belli olur.
 *
 * EŞİK ALTINDAKİLER DE GÖSTERİLİR: `/api/chat`'in `retrieval` olayı
 * `min_score=None` ile çekilmiş TÜM chunk'ları taşır (FEATURE_SPEC §0.1,
 * §2.1). "Neyin neden elendiği" görünmezse panel açıklayıcı olmaz.
 */

/** İlk elenen chunk'ın indeksi; -1 ise eleme yok, 0 ise hepsi elendi. */
function firstRejectedIndex(hits: ChunkHit[]): number {
  return hits.findIndex((hit) => !hit.passed_threshold)
}

function ThresholdDivider({ label }: { label: string }) {
  return (
    <li
      role="separator"
      aria-label={label}
      className="flex items-center gap-2 py-1"
    >
      <span aria-hidden="true" className="h-px flex-1 bg-border-strong" />
      <span className="font-mono text-mono font-medium text-score-rejected">
        {label}
      </span>
      <span aria-hidden="true" className="h-px flex-1 bg-border-strong" />
    </li>
  )
}

function InspectorPlaceholder({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode
  title: string
  body?: string
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-text-secondary">
        {icon}
      </span>
      <div className="flex flex-col gap-1">
        <p className="text-h3 font-semibold text-foreground">{title}</p>
        {body && <p className="text-body-sm text-text-secondary">{body}</p>}
      </div>
    </div>
  )
}

export interface RetrievalInspectorProps {
  className?: string
}

export function RetrievalInspector({ className }: RetrievalInspectorProps) {
  const t = useT(chat)
  const state = useChatState()
  const message = selectedAssistant(state)
  const retrieval = message?.retrieval ?? null

  const highlightIndex =
    state.highlight && message && state.highlight.messageId === message.id
      ? state.highlight.chunkIndex
      : -1
  const highlightNonce = state.highlight?.nonce ?? 0

  const cardRefs = React.useRef<Array<HTMLLIElement | null>>([])

  React.useEffect(() => {
    if (highlightIndex < 0) return
    const element = cardRefs.current[highlightIndex]
    if (!element) return
    // §5 hareket kuralı: reduced-motion altında yumuşak kaydırma da kapanır.
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    element.scrollIntoView({
      block: "nearest",
      behavior: reduced ? "auto" : "smooth",
    })
  }, [highlightIndex, highlightNonce])

  const machineState = retrieval
    ? highlightIndex >= 0
      ? "highlighted"
      : "filled"
    : state.phase === "searching"
      ? "searching"
      : "empty"

  const hits = retrieval?.hits ?? []
  const dividerIndex = firstRejectedIndex(hits)
  const nonePassed = retrieval !== null && retrieval.passed_count === 0

  return (
    <aside
      data-slot="retrieval-inspector"
      data-state={machineState}
      aria-label={t.inspectorTitle}
      className={cn("flex h-full min-h-0 flex-col bg-surface", className)}
    >
      <header className="flex flex-col gap-1 border-b border-border px-4 py-3">
        <h2 className="text-h2 font-semibold text-foreground">
          {t.inspectorTitle}
        </h2>
        {retrieval ? (
          <p className="flex flex-wrap items-baseline gap-x-2 text-caption text-text-secondary">
            <span>
              {t.inspectorSummary(retrieval.passed_count, retrieval.hits.length)}
            </span>
            <span className="font-mono text-mono text-text-tertiary tabular-nums">
              {t.inspectorElapsed(retrieval.elapsed_ms)}
            </span>
          </p>
        ) : (
          <p className="text-caption text-text-secondary">
            {t.inspectorSubtitle}
          </p>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {machineState === "empty" && (
          <InspectorPlaceholder
            icon={<TelescopeIcon aria-hidden="true" className="size-4.5" />}
            title={t.inspectorEmptyTitle}
            body={t.inspectorEmptyBody}
          />
        )}

        {machineState === "searching" && (
          <div className="flex flex-col gap-3" aria-live="polite">
            <p className="flex items-center gap-2 text-body-sm text-text-secondary">
              <SearchIcon
                aria-hidden="true"
                className="size-3.5 animate-pulse motion-reduce:animate-none"
              />
              {t.inspectorSearchingTitle}
            </p>
            {/* Skeleton'ın varsayılan `bg-muted`'ı `--surface`, kart zemini de
                aynı token — bu yüzden çubuklar `--border` ile çizilir, aksi
                halde iskelet görünmez olurdu (iki temada da ölçüldü). */}
            {[0, 1, 2].map((index) => (
              <div
                key={index}
                className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3"
              >
                <Skeleton className="h-5 w-24 bg-border" />
                <Skeleton className="h-3 w-40 bg-border" />
                <Skeleton className="h-1.5 w-full bg-border" />
                <Skeleton className="h-12 w-full bg-border" />
              </div>
            ))}
          </div>
        )}

        {retrieval && (
          <>
            {/* §4.3: hepsi elendiyse panel başında açıklama. */}
            {nonePassed && (
              <div className="mb-3 flex flex-col gap-1 rounded-md border border-warning/30 bg-warning/5 p-3">
                <p className="text-body-sm font-medium text-warning">
                  {t.nonePassedTitle}
                </p>
                <p className="text-caption text-text-secondary">
                  {t.nonePassedBody}
                </p>
              </div>
            )}

            <ul className="flex flex-col gap-3">
              {hits.map((hit, index) => (
                <React.Fragment key={`${hit.citation}-${index}`}>
                  {/* Eşik çizgisi tam geçiş noktasına düşer; hiç eleme
                      yoksa hiç çizilmez (dividerIndex === -1). */}
                  {index === dividerIndex && (
                    <ThresholdDivider
                      label={t.thresholdLine(retrieval.threshold)}
                    />
                  )}
                  <li
                    ref={(element) => {
                      cardRefs.current[index] = element
                    }}
                  >
                    <ChunkCard
                      hit={hit}
                      threshold={retrieval.threshold}
                      highlighted={index === highlightIndex}
                    />
                  </li>
                </React.Fragment>
              ))}
            </ul>

            {dividerIndex === -1 && hits.length > 0 && (
              <p className="mt-3 text-caption text-text-tertiary">
                {t.allPassedNote}
              </p>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
