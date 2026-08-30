"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"

import { failureText } from "./error-messages"
import { SystemStatus } from "./system-status"
import { useKnowledge } from "./use-knowledge"

/**
 * Ayarlar çekmecesinin içeriği — FEATURE_SPEC §13.5 (Faz 5).
 *
 * SALT-OKUNUR. Her sayı `/api/health`'ten gelir; UI hiçbir eşiği literal
 * yazmaz (§13.6 canlı eşik/topK kaydırağını kapsam dışı bıraktı).
 *
 * `SystemStatus` buraya TAŞINDI, kopyalanmadı: aynı sayılar hem sidebar
 * altbilgisinde hem çekmecede yaşasaydı ikisi ayrışabilirdi. Isınma uyarısı
 * ve "yeniden dene" düğmesi o bileşenin içinde, yani kayıpsız geldi.
 *
 * Mockup'ın "Cihaz" bölümü (tok/s · RAM · GPU) KURULMADI: §13.6'da cihaz
 * telemetrisi kapsam dışı bırakılmıştı ve backend böyle bir ölçüm
 * üretmiyor. Olmayan bir sayıyı göstermektense bölümü hiç açmamak doğru.
 */
export interface SettingsPanelProps {
  className?: string
}

export function SettingsPanel({ className }: SettingsPanelProps) {
  const t = useT(sidebarText)
  const tc = useT(common)
  const { health, healthFailure, refreshAll } = useKnowledge()

  const healthErrorText = healthFailure
    ? failureText(healthFailure, t, tc)
    : undefined

  return (
    <div
      data-slot="settings-panel"
      className={cn("flex min-h-0 flex-1 flex-col overflow-y-auto", className)}
    >
      <div className="border-b border-border p-4">
        <SystemStatus
          health={health}
          errorText={healthErrorText}
          onRetry={() => {
            void refreshAll()
          }}
        />
      </div>

      {/* Eşik çubuğu. YALNIZCA `min_score` için: cosine 0–1 aralığında
          gerçek bir ölçek. `top_k` için çubuk çizmek var olmayan bir tavan
          uydurmak olurdu (mockup 4'ü %32 dolu gösteriyordu — o yüzde nereden
          geliyorsa, orası bizde yok). */}
      {health !== null && (
        <div className="p-4">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-body-sm font-medium text-text-primary">
              {t.minScoreLabel}
            </span>
            <span className="font-mono text-mono text-primary tabular-nums">
              {health.min_score.toFixed(2)}
            </span>
          </div>
          <p className="mt-1 text-caption text-text-secondary">{t.minScoreHint}</p>
          <div
            role="img"
            aria-label={t.minScoreScale(health.min_score)}
            className="mt-2.5 h-1 w-full bg-border-strong"
          >
            <div
              className="h-full bg-primary"
              style={{ width: `${health.min_score * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
