"use client"

import { AlertTriangleIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { MarkdownContent } from "@/components/chat/markdown-content"

/**
 * Token token akan cevap metni.
 *
 * DESIGN_SYSTEM.md §5: token akışında ANİMASYON YOK. Metin zaten hareket
 * ediyor; üzerine geçiş/fade eklemek okunabilirliği bozar. Tek hareketli öğe
 * yanıp sönen imleç, o da `prefers-reduced-motion` altında durur
 * (`motion-reduce:animate-none`).
 *
 * İmleç ayrı bir eleman değil, markdown gövdesinin SON blok elemanına takılan
 * bir `::after` — böylece cümlenin bittiği yerde, satır sonunda görünür.
 * Ayrı bir <span> olsaydı son paragrafın altına düşerdi.
 *
 * FEATURE_SPEC §5 [!tip]: akış ortasında kopan bir yanıtta kısmi metin
 * SİLİNMEZ; altına gri bir "yanıt tamamlanamadı" satırı eklenir.
 */

const CURSOR_CLASS = cn(
  "[&>:last-child]:after:ml-0.5 [&>:last-child]:after:inline-block",
  "[&>:last-child]:after:h-[0.9em] [&>:last-child]:after:w-[2px]",
  "[&>:last-child]:after:translate-y-[0.1em] [&>:last-child]:after:bg-accent",
  "[&>:last-child]:after:align-baseline [&>:last-child]:after:content-['']",
  "[&>:last-child]:after:animate-caret-blink",
  "motion-reduce:[&>:last-child]:after:animate-none"
)

export interface StreamingTextProps {
  /** O ana kadar biriken metin. */
  text: string
  /** Akış sürüyor mu — yanıp sönen imleci yalnızca bu true iken göster. */
  streaming?: boolean
  /** Akış tamamlanmadan koptu mu (kısmi metin korunur). */
  incomplete?: boolean
  /** "Yanıt tamamlanamadı." — i18n'den geçirilir, sabit yazılmaz. */
  incompleteLabel?: string
  /** Kopma sebebi (backend'den gelen mesaj); varsa ikinci satırda gösterilir. */
  incompleteDetail?: string
  className?: string
}

export function StreamingText({
  text,
  streaming = false,
  incomplete = false,
  incompleteLabel,
  incompleteDetail,
  className,
}: StreamingTextProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <MarkdownContent
        // Vurgulama yalnızca akış bittiğinde: her token'da yeniden
        // renklendirmek hem boşuna hem de titreme yaratır.
        highlightCode={!streaming}
        className={streaming ? CURSOR_CLASS : undefined}
      >
        {text}
      </MarkdownContent>

      {incomplete && incompleteLabel && (
        <p
          className="flex items-start gap-1.5 text-body-sm text-text-tertiary"
          role="status"
        >
          <AlertTriangleIcon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            {incompleteLabel}
            {incompleteDetail ? ` ${incompleteDetail}` : null}
          </span>
        </p>
      )}
    </div>
  )
}
