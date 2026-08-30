"use client"

import * as React from "react"
import { ArrowLeftIcon, DownloadIcon, PrinterIcon, RefreshCwIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import { artifactExportUrl } from "@/lib/api"
import type { ArtifactDetail } from "@/lib/types"
import { Button } from "@/components/ui/button"

import { useArtifacts } from "./use-artifacts"

/**
 * Üç artefakt ekranının ORTAK tam-ekran kabuğu — FEATURE_SPEC §13.5 (Faz 4).
 *
 * Neden ortak: rapor, zihin haritası ve quiz görünümleri birbirinin KOPYASI
 * olan üç başlık taşıyordu (aynı `<header>`, aynı indir/yazdır/kapat üçlüsü).
 * Kopya, "Raporu kapat" etiketinin quiz ve harita kapatılırken de
 * görünmesine yol açmıştı — üç yerde ayrı ayrı düzeltilecek bir hata yerine
 * tek yerde duran bir kabuk.
 *
 * Yazdırma sözleşmesi (§10.12) KORUNUR: kök `data-print="root"`, üst çubuk
 * `data-print="hide"`. Kabuk `fixed inset-0` ile tüm kabuğun üstünü kaplar
 * (mockup'ın `position:absolute; inset:0`'ı), ama YAZDIRIRKEN `print:static`
 * ile normal akışa döner — `position: fixed` bir eleman yazdırıldığında tek
 * sayfaya kırpılırdı ve raporun çok sayfalı çıktısı bozulurdu.
 */
export interface ArtifactScreenProps {
  artifact: ArtifactDetail
  onClose: () => void
  /** Başlığın yanındaki mono künye — "12 soru · v2" gibi. */
  meta?: React.ReactNode
  /** Yalnızca rapor yazdırılır (§10.12); diğer ikisinde düğme gösterilmez. */
  showPrint?: boolean
  /** Kök elemanın `data-slot`'u — ui_proof bu seçicilere bağlı. */
  slot: string
  className?: string
  children: React.ReactNode
}

export function ArtifactScreen({
  artifact,
  onClose,
  meta,
  showPrint = false,
  slot,
  className,
  children,
}: ArtifactScreenProps) {
  const t = useT(studio)
  const { generatingKind, generate } = useArtifacts()

  return (
    <div
      data-print="root"
      data-slot={slot}
      className={cn(
        "fixed inset-0 z-40 flex flex-col overflow-hidden bg-background",
        "print:static print:overflow-visible",
        className
      )}
    >
      <header
        data-print="hide"
        className="flex h-13 shrink-0 items-center gap-3.5 border-b-2 border-border px-5"
      >
        <Button variant="ghost" size="sm" onClick={onClose}>
          <ArrowLeftIcon aria-hidden="true" />
          {t.closeArtifact}
        </Button>
        <span aria-hidden="true" className="h-4.5 w-px bg-border" />
        <h1 className="truncate text-body-sm font-semibold text-text-primary">
          {artifact.title}
        </h1>
        {meta !== undefined && (
          <span className="shrink-0 font-mono text-mono text-text-secondary tabular-nums">
            {meta}
          </span>
        )}
        <span className="flex-1" />

        {/* "Yeniden üret" ÜRETİM MANTIĞINI DEĞİŞTİRMEZ (§9–12 donduruldu):
            var olan `generate`'i artefaktın KENDİ kapsamıyla yeniden çağırır.
            Kapsamı yeniden seçtirmek yeni bir karar olurdu; burada amaç
            "bu artefaktı tazele". */}
        <Button
          variant="outline"
          size="sm"
          disabled={generatingKind !== null}
          onClick={() => {
            void generate(artifact.kind, artifact.document_id)
          }}
        >
          <RefreshCwIcon aria-hidden="true" />
          {t.regenerate}
        </Button>
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
        {showPrint && (
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <PrinterIcon aria-hidden="true" />
            {t.print}
          </Button>
        )}
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden print:overflow-visible">
        {children}
      </div>
    </div>
  )
}
