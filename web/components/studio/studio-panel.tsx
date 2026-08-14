"use client"

import { SparklesIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"

/**
 * Studio sekmesinin içeriği — docs/FEATURE_SPEC.md §9.9.4.
 *
 * Faz 1'de gösterdiği TEK şey boş durumdur ve API'ye istek atmaz: üretim
 * yolu (`POST /api/artifacts`) Faz 2'de açılıyor, o zamana kadar
 * `GET /api/artifacts` her zaman boş liste döner -- boş bir listeyi almak
 * için bir ağ turu yapmak anlamsız.
 *
 * Kasıtlı olarak burada bir "Üret" düğmesi YOK: basılamayan ya da hata
 * döndüren bir düğme, bu ürünün "sahte sayı göstermez" çizgisinin aynı
 * ihlalidir. Düğme, arkasındaki üretici gerçekten çalıştığında (Faz 2)
 * gelir.
 */
export interface StudioPanelProps {
  className?: string
}

export function StudioPanel({ className }: StudioPanelProps) {
  const t = useT(studio)

  return (
    <div
      data-slot="studio-panel"
      className={cn(
        "flex h-full min-h-0 flex-col items-center justify-center gap-3 overflow-y-auto px-4 py-10 text-center",
        className
      )}
    >
      <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-text-secondary">
        <SparklesIcon aria-hidden="true" className="size-4.5" />
      </span>
      <div className="flex flex-col gap-1">
        <p className="text-h3 font-semibold text-foreground">{t.emptyTitle}</p>
        <p className="max-w-70 text-body-sm text-text-secondary">
          {t.emptyBody}
        </p>
      </div>
      <p className="text-caption text-text-tertiary">{t.emptyNote}</p>
    </div>
  )
}
