"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { chatActions } from "@/components/chat/chat-store"

/**
 * Cümlenin içindeki numaralı atıf üst simgesi — FEATURE_SPEC §13.4.
 *
 * Basınca iki şey olur: `focusSource` çekmecenin odağını bu chunk'a alır
 * (ve §4'ün 1.5 sn'lik vurgusunu tetikler), sonra çekmece açılır. Yani
 * DAVRANIŞ §1.3'teki SourceChip -> ChunkCard etkileşiminin aynısı; değişen
 * yalnızca tetikleyicinin cümlenin içinde durması.
 *
 * `<button>`, `<span>` değil: klavyeyle erişilebilir olmalı ve ekran
 * okuyucuya "kaynağı aç" diye tanıtılmalı.
 */
export interface CitationMarkerProps {
  number: number
  /** Ham işaretçi — `focusSource` eşleşmeyi bu string üzerinden kurar. */
  citation: string
  messageId: string
  /** Görünür etiket ("3. kaynağı aç" gibi); i18n'den gelir. */
  label: string
  onOpenDrawer?: () => void
  className?: string
}

export function CitationMarker({
  number,
  citation,
  messageId,
  label,
  onOpenDrawer,
  className,
}: CitationMarkerProps) {
  return (
    // `text-mono` (yazı boyutu) BURADA duruyor, düğmede değil: düğmede
    // `text-primary-foreground` ile aynı `text-*` ailesinde çakışıyor ve
    // tailwind-merge boyutu düşürüyordu (ölçüldü: render edilen class
    // listesinde `text-mono` yoktu).
    <sup className="ml-0.5 align-super text-mono">
      <button
        type="button"
        data-slot="citation-marker"
        data-citation-number={number}
        aria-label={label}
        onClick={() => {
          chatActions.focusSource(messageId, citation)
          onOpenDrawer?.()
        }}
        className={cn(
          // `inline-block` + açık `leading`: `inline-flex` ÖLÇÜLDÜ ve
          // yüksekliği 0 veriyordu (box=16x0), yani üst simge tıklanamıyordu.
          "inline-block min-w-4 cursor-pointer px-1 text-center leading-4",
          "font-semibold text-primary-foreground tabular-nums",
          "bg-primary hover:bg-primary-hover",
          "transition-colors duration-(--duration-hover) ease-(--ease-standard)",
          "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
          className
        )}
      >
        {number}
      </button>
    </sup>
  )
}
