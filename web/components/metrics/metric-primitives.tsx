"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

/**
 * Metrics sayfasının paylaşılan görsel parçaları.
 *
 * Buradaki hiçbir bileşen metin veya sayı ÜRETMEZ: etiketleri çağıran
 * taraf i18n'den, değerleri `MetricsResponse`'tan geçirir. Renkler yalnızca
 * dondurulmuş token köprüleri üzerinden (bg-success, text-warning, …)
 * kullanılır; sabit hex yoktur (DESIGN_SYSTEM.md §1).
 */

/** Grafiklerdeki iki soru grubunun kategorik renkleri.
 *
 * Seçim gerekçesi: indigo (`--primary`) ↔ amber (`--warning`) mavi/turuncu
 * karşıtlığıdır ve renk körlüğü altında ayrışması ölçüldü (protanopi ΔE 31.7
 * light / 33.7 dark, tritanopi 27.0 / 23.5 — eşik 8). Skor bandı renkleri
 * (yeşil/kehribar/kırmızı) burada BİLEREK kullanılmadı: bu grafikte renk
 * "skor ne kadar iyi"yi değil "soru hangi gruba ait"i taşıyor; ikisini aynı
 * paletle boyamak iki ayrı anlamı üst üste bindirirdi. Renk tek başına da
 * bilgi taşımıyor — her grubun adı, sayısı ve aralığı lejantta yazılı.
 */
export const SERIES_PAINT = {
  answerable: "var(--primary)",
  other: "var(--warning)",
} as const

export type SeriesKey = keyof typeof SERIES_PAINT

const SERIES_SWATCH_CLASS: Record<SeriesKey, string> = {
  answerable: "bg-primary",
  other: "bg-warning",
}

// --------------------------------------------------------------------------- bölüm kabuğu

export interface MetricsSectionProps {
  title: string
  description?: string
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}

export function MetricsSection({
  title,
  description,
  actions,
  children,
  className,
}: MetricsSectionProps) {
  return (
    <Card className={cn("[--card-spacing:--spacing(6)]", className)}>
      <CardHeader>
        <CardTitle className="text-h2 font-semibold">{title}</CardTitle>
        {description && (
          <CardDescription className="text-body-sm">{description}</CardDescription>
        )}
        {actions}
      </CardHeader>
      <CardContent className="flex flex-col gap-5">{children}</CardContent>
    </Card>
  )
}

// --------------------------------------------------------------------------- istatistik kutusu

export interface StatTileProps {
  label: string
  /** Kahraman sayı. Zaten biçimlendirilmiş metin olarak gelir. */
  value: string
  help?: string
  icon?: React.ReactNode
  /** Değerin altında ek bir görsel (oran çubuğu, rozet dizisi, …). */
  children?: React.ReactNode
  className?: string
}

export function StatTile({
  label,
  value,
  help,
  icon,
  children,
  className,
}: StatTileProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-lg bg-surface p-4 ring-1 ring-foreground/10",
        className
      )}
    >
      <div className="flex items-center gap-2 text-caption font-medium text-text-secondary">
        {icon}
        <span>{label}</span>
      </div>
      {/* Kahraman sayıda tabular-nums YOK: büyük puntoda eşit genişlikli
          rakamlar gevşek görünür (dikey hizalanan tablo hücrelerinde var). */}
      <span className="text-display leading-none font-semibold text-foreground">
        {value}
      </span>
      {children}
      {help && <p className="text-caption text-text-tertiary">{help}</p>}
    </div>
  )
}

// --------------------------------------------------------------------------- oran çubuğu

export interface RatioBarProps {
  passed: number
  total: number
  /** Ekran okuyucu için tam cümle; görsel olarak sayı ayrıca yazılır. */
  ariaLabel: string
  className?: string
}

/**
 * Geçen/toplam oranı. Renk burada DURUM taşır (geçti = `--success`), bu
 * yüzden kategorik seri renklerinden ayrı tutuldu; yanında her zaman
 * sayısal oran yazılır, bilgi renge bağlı değildir.
 */
export function RatioBar({ passed, total, ariaLabel, className }: RatioBarProps) {
  const ratio = total > 0 ? Math.max(0, Math.min(1, passed / total)) : 0
  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className={cn("h-1.5 w-full overflow-hidden rounded-sm bg-border", className)}
    >
      <div
        className="h-full rounded-sm bg-success"
        style={{ width: `${ratio * 100}%` }}
      />
    </div>
  )
}

// --------------------------------------------------------------------------- lejant

export interface LegendSwatchProps {
  kind: SeriesKey | "threshold" | "overlap"
  className?: string
}

export function LegendSwatch({ kind, className }: LegendSwatchProps) {
  if (kind === "threshold") {
    return (
      <span
        aria-hidden="true"
        className={cn("inline-block h-3.5 w-0.5 shrink-0 rounded-sm bg-foreground", className)}
      />
    )
  }
  if (kind === "overlap") {
    // Lejant işareti grafikteki işaretin BİRE BİR küçüğü olmalı: örtüşme
    // bandı taralı bir dikdörtgen, o yüzden swatch de taralı ve köşeli.
    // `currentColor` sınıftan gelen renkle boyanır, sabit değer yok.
    return (
      <span
        aria-hidden="true"
        className={cn(
          "inline-block h-3 w-4 shrink-0 rounded-sm text-text-secondary/60 ring-1 ring-text-secondary/40",
          className
        )}
        style={{
          backgroundImage:
            "repeating-linear-gradient(45deg, transparent 0 2px, currentColor 2px 3px)",
        }}
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-3 shrink-0 rounded-full ring-2 ring-card",
        SERIES_SWATCH_CLASS[kind],
        className
      )}
    />
  )
}

export interface LegendItemProps {
  kind: SeriesKey | "threshold" | "overlap"
  label: string
  detail?: string
}

export function LegendItem({ kind, label, detail }: LegendItemProps) {
  return (
    <span className="inline-flex items-center gap-2">
      <LegendSwatch kind={kind} />
      {/* Metin daima ink token'ı giyer, seri rengini değil. */}
      <span className="text-caption font-medium text-foreground">{label}</span>
      {detail && (
        <span className="font-mono text-mono text-text-secondary tabular-nums">
          {detail}
        </span>
      )}
    </span>
  )
}

// --------------------------------------------------------------------------- açıklama kutusu

export interface CalloutProps {
  tone: "insight" | "note"
  icon?: React.ReactNode
  title: string
  children: React.ReactNode
  className?: string
}

export function Callout({ tone, icon, title, children, className }: CalloutProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-lg p-4 ring-1",
        tone === "insight"
          ? "bg-primary/8 ring-primary/25"
          : "bg-surface-raised ring-foreground/10",
        className
      )}
    >
      <h3 className="flex items-center gap-2 text-h3 font-semibold text-foreground">
        {icon}
        {title}
      </h3>
      <div className="flex flex-col gap-2 text-body-sm text-text-secondary">
        {children}
      </div>
    </div>
  )
}
