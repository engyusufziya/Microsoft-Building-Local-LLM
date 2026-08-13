"use client"

import { FileTextIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { chatActions } from "@/components/chat/chat-store"
import { middleTruncate, parseCitation } from "@/components/chat/citation"

/**
 * Cevabın altındaki kaynak chip'leri — FEATURE_SPEC §1.3.
 *
 * Chip'e tıklamak Inspector'ı ilgili ChunkCard'a kaydırır ve kartı 1.5 sn
 * vurgular. Bağlantı `citation` stringi üzerinden kurulur: `done` olayının
 * `sources` dizisi ile `retrieval` olayının `hits[].citation` alanı AYNI
 * motor fonksiyonundan (`rag/retrieve.py::Hit.citation`) üretilir, bu yüzden
 * birebir eşleşir. Eşleşme bulunamazsa (teorik olarak mümkün) chip yalnızca
 * ilgili mesajı Inspector'da seçer, çökmez.
 *
 * Kaynak yalnızca `reason === null` dalında gösterilir; `below_threshold` ve
 * `llm_refused` dallarında bu bileşen hiç render edilmez (FEATURE_SPEC §3.2).
 */
export interface SourceChipsProps {
  /** Vurgulanacak chunk'ın hangi mesajın retrieval'ında aranacağı. */
  messageId: string
  /** `done` olayının `sources` dizisi: ["[Kaynak: dosya.pdf s.4]", …] */
  sources: string[]
  className?: string
}

export function SourceChips({ messageId, sources, className }: SourceChipsProps) {
  const t = useT(chat)
  if (sources.length === 0) return null

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-caption font-medium text-text-tertiary">
        {t.sourcesLabel}
      </span>
      <ul className="flex flex-wrap gap-1.5">
        {sources.map((citation) => {
          const { source, page } = parseCitation(citation)
          return (
            <li key={citation}>
              <Tooltip>
                <TooltipTrigger
                  render={
                    <button
                      type="button"
                      onClick={() => chatActions.focusSource(messageId, citation)}
                      className="inline-flex h-6 w-fit items-center gap-1.5 rounded-sm border border-border bg-card px-2 text-caption font-medium text-text-secondary transition-colors duration-(--duration-hover) ease-(--ease-standard) hover:border-border-strong hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                    />
                  }
                >
                  <FileTextIcon aria-hidden="true" className="size-3 shrink-0" />
                  <span className="font-mono">{middleTruncate(source, 28)}</span>
                  {page > 0 && (
                    <span className="text-text-tertiary">{t.pageLabel(page)}</span>
                  )}
                </TooltipTrigger>
                <TooltipContent>
                  <span className="flex flex-col gap-0.5">
                    <span className="font-mono">{source}</span>
                    <span className="opacity-80">{t.sourceChipHint}</span>
                  </span>
                </TooltipContent>
              </Tooltip>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
