"use client"

import * as React from "react"
import { LayersIcon, LightbulbIcon, TriangleAlertIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { metrics as metricsText } from "@/lib/i18n/metrics"
import type { MetricsResponse } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import {
  Callout,
  LegendItem,
  MetricsSection,
  SERIES_PAINT,
} from "@/components/metrics/metric-primitives"
import {
  buildTicks,
  countWithin,
  extentOf,
  fullPassHeadroom,
  intersect,
  makeScale,
  swarm,
  type Extent,
} from "@/components/metrics/scale"

/**
 * Projenin en önemli teknik bulgusunu görselleştiren bileşen
 * (docs/FEATURE_SPEC.md §6.4).
 *
 * Anlatılan şey bir sayı değil, bir SINIR: cevabı belgelerde olan sorularla
 * olmayanların retrieval skorları AYNI aralığa düşüyor. Grafik bunu üç
 * işaretle söylüyor:
 *   1. İki şerit — her nokta bir sorunun en yüksek skoru; aralıklar üst üste.
 *   2. Taralı dikey bant — iki aralığın kesişimi, veriden hesaplanır.
 *   3. Dikey ink çizgi — aktif eşik; bandın İÇİNDEN ya da kenarından geçer.
 *
 * Hiçbir sayı burada sabit değil: eksen çentikleri `threshold_sweep.table`'ın
 * eşiklerinden, bant `answerable_scores` ∩ `other_scores`'tan, çizgi
 * `config.min_score`'tan gelir.
 *
 * Çizim tekniği: viewBox YOK. SVG uzunlukları yüzde kabul ettiği için yatay
 * eksen kapsayıcıyla esner, dikey eksen ve yazılar CSS pikselinde sabit
 * kalır. viewBox + uniform ölçeklemede dar ekranda 11px eksen yazısı 5px'e
 * inerdi. Boyalar `style` ile verilir (token var'ları), sınıfla değil —
 * presentation attribute'larda var() desteği tarayıcıdan tarayıcıya değişir.
 */

const GEOM = {
  height: 182,
  bandLabelY: 15,
  plotTop: 24,
  laneAnswerableY: 58,
  laneOtherY: 124,
  axisY: 158,
  tickLabelY: 174,
  dotRadius: 5,
  hitRadius: 13,
  rangeBarHeight: 4,
  swarmOffsets: [0, -12, 12, -24, 24],
  minGapPercent: 2.6,
} as const

type HoverState = {
  series: "answerable" | "other"
  value: number
  percent: number
  y: number
}

export interface ThresholdChartProps {
  sweep: MetricsResponse["threshold_sweep"]
  /** `config.min_score` — koda asla gömülmez, yanıttan gelir. */
  threshold: number
  className?: string
}

export function ThresholdChart({ sweep, threshold, className }: ThresholdChartProps) {
  const t = useT(metricsText)
  const patternId = React.useId()
  const [hover, setHover] = React.useState<HoverState | null>(null)

  const answerable = sweep.answerable_scores
  const other = sweep.other_scores

  const model = React.useMemo(() => {
    const answerableExtent = extentOf(answerable)
    const otherExtent = extentOf(other)
    const tableThresholds = sweep.table.map((row) => row.threshold)
    const scale = makeScale([...answerable, ...other, ...tableThresholds, threshold])
    return {
      answerableExtent,
      otherExtent,
      scale,
      ticks: buildTicks(tableThresholds, threshold, scale.domain),
      overlap: intersect(answerableExtent, otherExtent),
      answerablePoints: swarm(
        answerable,
        scale.percentOf,
        GEOM.minGapPercent,
        GEOM.swarmOffsets
      ),
      otherPoints: swarm(other, scale.percentOf, GEOM.minGapPercent, GEOM.swarmOffsets),
      headroom: fullPassHeadroom(sweep.table),
    }
  }, [answerable, other, sweep.table, threshold])

  const { scale, ticks, overlap, answerableExtent, otherExtent } = model
  const thresholdPercent = scale.percentOf(threshold)

  const hoverLabel = hover
    ? t.dotTooltip(
        hover.series === "answerable" ? t.groupAnswerable : t.groupOther,
        hover.value
      )
    : null

  return (
    <MetricsSection
      title={t.thresholdTitle}
      description={t.thresholdSubtitle}
      className={className}
    >
      {/* --- Lejant: renk asla tek başına bilgi taşımaz; her seri burada
              adı, soru sayısı ve aralığıyla yazılı (DESIGN_SYSTEM.md §1.2). --- */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <LegendItem
          kind="answerable"
          label={t.groupAnswerable}
          detail={
            answerableExtent
              ? t.groupSummary(answerable.length, answerableExtent[0], answerableExtent[1])
              : undefined
          }
        />
        <LegendItem
          kind="other"
          label={t.groupOther}
          detail={
            otherExtent
              ? t.groupSummary(other.length, otherExtent[0], otherExtent[1])
              : undefined
          }
        />
        <LegendItem
          kind="threshold"
          label={t.activeThresholdLabel}
          detail={t.score(threshold)}
        />
        {overlap && (
          <LegendItem
            kind="overlap"
            label={t.overlapLabel}
            detail={t.overlapRange(overlap[0], overlap[1])}
          />
        )}
      </div>

      {/* --- Çizim alanı ---
          Dar ekranda eksen etiketleri üst üste binmesin diye grafik kendi
          kabında yatay kayar; sayfa gövdesi asla yatay kaymaz. */}
      <div className="overflow-x-auto">
        <div className="relative min-w-[30rem] px-3">
          <svg
            width="100%"
            height={GEOM.height}
            role="img"
            aria-label={t.chartAria(answerable.length, other.length)}
            className="block overflow-visible"
          >
            <defs>
              {/* Örtüşme bandı taraması. Doku burada dekorasyon değil: bir
                  DEĞER ölçeğini değil bir BÖLGEYİ işaretliyor ve renk körlüğü
                  altında da okunur kalıyor. */}
              <pattern
                id={patternId}
                width="7"
                height="7"
                patternUnits="userSpaceOnUse"
                patternTransform="rotate(45)"
              >
                <line
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="7"
                  style={{ stroke: "var(--text-secondary)", strokeWidth: 1 }}
                  strokeOpacity={0.45}
                />
              </pattern>
            </defs>

            {/* Izgara: düz saç teli çizgiler, yüzeyin bir ton üstü. */}
            {ticks.map((tick) => (
              <line
                key={`grid-${tick}`}
                x1={`${scale.percentOf(tick)}%`}
                x2={`${scale.percentOf(tick)}%`}
                y1={GEOM.plotTop}
                y2={GEOM.axisY}
                style={{ stroke: "var(--border)", strokeWidth: 1 }}
              />
            ))}

            {/* --- ÖRTÜŞME BÖLGESİ --- */}
            {overlap && (
              <g>
                <rect
                  x={`${scale.percentOf(overlap[0])}%`}
                  width={`${scale.percentOf(overlap[1]) - scale.percentOf(overlap[0])}%`}
                  y={GEOM.plotTop}
                  height={GEOM.axisY - GEOM.plotTop}
                  style={{ fill: "var(--text-secondary)" }}
                  fillOpacity={0.07}
                />
                <rect
                  x={`${scale.percentOf(overlap[0])}%`}
                  width={`${scale.percentOf(overlap[1]) - scale.percentOf(overlap[0])}%`}
                  y={GEOM.plotTop}
                  height={GEOM.axisY - GEOM.plotTop}
                  fill={`url(#${patternId})`}
                />
                {[overlap[0], overlap[1]].map((edge) => (
                  <line
                    key={`overlap-edge-${edge}`}
                    x1={`${scale.percentOf(edge)}%`}
                    x2={`${scale.percentOf(edge)}%`}
                    y1={GEOM.plotTop}
                    y2={GEOM.axisY}
                    style={{ stroke: "var(--text-secondary)", strokeWidth: 1 }}
                    strokeOpacity={0.55}
                  />
                ))}
                <text
                  x={`${(scale.percentOf(overlap[0]) + scale.percentOf(overlap[1])) / 2}%`}
                  y={GEOM.bandLabelY}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={500}
                  style={{ fill: "var(--text-secondary)" }}
                >
                  {t.overlapLabel}
                </text>
              </g>
            )}

            {/* --- Aktif eşik: ink rengi, seri rengi DEĞİL (bir veri serisi değil). --- */}
            <line
              x1={`${thresholdPercent}%`}
              x2={`${thresholdPercent}%`}
              y1={GEOM.plotTop - 4}
              y2={GEOM.axisY}
              style={{ stroke: "var(--text-primary)", strokeWidth: 2 }}
            />
            <circle
              cx={`${thresholdPercent}%`}
              cy={GEOM.plotTop - 4}
              r={3}
              style={{ fill: "var(--text-primary)" }}
            />

            {/* --- Şerit 1: cevaplanabilir --- */}
            <LaneMarks
              points={model.answerablePoints}
              extent={answerableExtent}
              laneY={GEOM.laneAnswerableY}
              paint={SERIES_PAINT.answerable}
              scale={scale}
              onHover={setHover}
              series="answerable"
            />

            {/* --- Şerit 2: cevaplanamaz + kenar durum --- */}
            <LaneMarks
              points={model.otherPoints}
              extent={otherExtent}
              laneY={GEOM.laneOtherY}
              paint={SERIES_PAINT.other}
              scale={scale}
              onHover={setHover}
              series="other"
            />

            {/* --- Eksen --- */}
            <line
              x1="0%"
              x2="100%"
              y1={GEOM.axisY}
              y2={GEOM.axisY}
              style={{ stroke: "var(--border-strong)", strokeWidth: 1 }}
            />
            {ticks.map((tick) => {
              const isThreshold = Math.abs(tick - threshold) < 0.005
              return (
                <text
                  key={`tick-${tick}`}
                  x={`${scale.percentOf(tick)}%`}
                  y={GEOM.tickLabelY}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={isThreshold ? 600 : 400}
                  className="font-mono tabular-nums"
                  style={{
                    fill: isThreshold ? "var(--text-primary)" : "var(--text-secondary)",
                  }}
                >
                  {t.score(tick)}
                </text>
              )
            })}
          </svg>

          {/* İpucu katmanı: değeri OKUMANIN tek yolu değil — aynı sayılar
              aşağıdaki tarama tablosunda ve lejanttaki aralıklarda var. */}
          {hover && hoverLabel && (
            <div
              aria-hidden="true"
              className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md bg-foreground px-2 py-1 font-mono text-mono whitespace-nowrap text-background"
              style={{ left: `calc(0.75rem + (100% - 1.5rem) * ${hover.percent / 100})`, top: hover.y - 12 }}
            >
              {hoverLabel}
            </div>
          )}
        </div>
      </div>

      <p className="text-caption text-text-tertiary">{t.axisLabel}</p>

      {/* --- §6.4: anlatılması gereken içgörü --- */}
      <Callout
        tone="insight"
        icon={<LightbulbIcon className="size-4 shrink-0 text-primary" />}
        title={t.insightTitle}
      >
        <p>{t.insightBody}</p>
        {overlap ? (
          <p className="font-medium text-foreground">
            {t.overlapCounts(
              countWithin(answerable, overlap),
              countWithin(other, overlap)
            )}
          </p>
        ) : (
          <p>{t.noOverlapNote}</p>
        )}
      </Callout>

      <div className="flex flex-col gap-3">
        <h3 className="flex items-center gap-2 text-h3 font-semibold text-foreground">
          <LayersIcon className="size-4 shrink-0 text-text-secondary" />
          {t.defenseTitle}
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <DefenseLayer tag={t.defenseLayerOneTag} body={t.defenseLayerOne} />
          <DefenseLayer tag={t.defenseLayerTwoTag} body={t.defenseLayerTwo} />
        </div>
      </div>

      {/* --- Kalibrasyon hikâyesi (aşırı uydurma) --- */}
      <Callout
        tone="note"
        icon={<TriangleAlertIcon className="size-4 shrink-0 text-warning" />}
        title={t.calibrationTitle}
      >
        <p>{t.calibrationBody}</p>
        {model.headroom !== null && (
          <p className="text-foreground">
            {t.calibrationEvidence(model.headroom, threshold)}
          </p>
        )}
        <p>{t.calibrationTradeoff}</p>
      </Callout>

      <SweepTable sweep={sweep} threshold={threshold} />
    </MetricsSection>
  )
}

// --------------------------------------------------------------------------- şerit

interface LaneMarksProps {
  points: { value: number; percent: number; offset: number }[]
  extent: Extent | null
  laneY: number
  paint: string
  scale: { percentOf: (value: number) => number }
  series: "answerable" | "other"
  onHover: (state: HoverState | null) => void
}

function LaneMarks({
  points,
  extent,
  laneY,
  paint,
  scale,
  series,
  onHover,
}: LaneMarksProps) {
  return (
    <g>
      {/* Aralık şeridi: grubun min–max genişliği. İki şeridi yan yana
          görünce "aralıklar örtüşüyor" iddiası tek bakışta okunuyor. */}
      {extent && (
        <rect
          x={`${scale.percentOf(extent[0])}%`}
          width={`${scale.percentOf(extent[1]) - scale.percentOf(extent[0])}%`}
          y={laneY - GEOM.rangeBarHeight / 2}
          height={GEOM.rangeBarHeight}
          rx={GEOM.rangeBarHeight / 2}
          style={{ fill: paint }}
          fillOpacity={0.22}
        />
      )}
      {points.map((point, index) => (
        <g key={`${series}-${index}-${point.value}`}>
          {/* Görünmez, büyük vuruş alanı: 5px'lik bir noktayı tam ortasından
              yakalamak zorunda kalmamak için (~26px hedef). */}
          <circle
            cx={`${point.percent}%`}
            cy={laneY + point.offset}
            r={GEOM.hitRadius}
            fill="transparent"
            pointerEvents="all"
            onPointerEnter={() =>
              onHover({
                series,
                value: point.value,
                percent: point.percent,
                y: laneY + point.offset,
              })
            }
            onPointerLeave={() => onHover(null)}
          />
          {/* 2px yüzey halkası: üst üste binen noktalar birbirinden ayrılır
              (kenarlık çizmeden). */}
          <circle
            cx={`${point.percent}%`}
            cy={laneY + point.offset}
            r={GEOM.dotRadius}
            style={{ fill: paint, stroke: "var(--surface)", strokeWidth: 2 }}
            pointerEvents="none"
          />
        </g>
      ))}
    </g>
  )
}

// --------------------------------------------------------------------------- savunma katmanı kutusu

function DefenseLayer({ tag, body }: { tag: string; body: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg bg-surface-raised p-4 ring-1 ring-foreground/10">
      <Badge variant="outline" className="font-mono text-mono">
        {tag}
      </Badge>
      <p className="text-body-sm text-text-secondary">{body}</p>
    </div>
  )
}

// --------------------------------------------------------------------------- tarama tablosu

interface SweepTableProps {
  sweep: MetricsResponse["threshold_sweep"]
  threshold: number
}

/**
 * Dağılım grafiğinin tablo ikizi: aynı iki dizinin her eşikteki kümülatif
 * sayımı. Grafiğe erişemeyen (ekran okuyucu, yazdırma, renk körlüğü) her
 * kullanıcı aynı bilgiye buradan ulaşır.
 */
function SweepTable({ sweep, threshold }: SweepTableProps) {
  const t = useT(metricsText)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h3 className="text-h3 font-semibold text-foreground">{t.sweepTitle}</h3>
        <p className="text-caption text-text-tertiary">{t.sweepSubtitle}</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[26rem] border-collapse text-body-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="py-2 pr-4 text-left text-caption font-medium text-text-secondary">
                {t.sweepColThreshold}
              </th>
              <th className="py-2 pr-4 text-left text-caption font-medium text-text-secondary">
                {t.sweepColAnswerable}
              </th>
              <th className="py-2 text-left text-caption font-medium text-text-secondary">
                {t.sweepColOther}
              </th>
            </tr>
          </thead>
          <tbody>
            {sweep.table.map((row) => {
              const isActive = Math.abs(row.threshold - threshold) < 0.005
              return (
                <tr
                  key={row.threshold}
                  className={cn(
                    "border-b border-border last:border-b-0",
                    isActive && "bg-primary/8"
                  )}
                >
                  <td className="py-2 pr-4">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className={cn(
                          "font-mono text-mono tabular-nums",
                          isActive
                            ? "font-semibold text-foreground"
                            : "text-text-secondary"
                        )}
                      >
                        {t.score(row.threshold)}
                      </span>
                      {isActive && (
                        <Badge variant="outline" className="text-caption">
                          {t.sweepActiveRow}
                        </Badge>
                      )}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <SweepCell
                      passed={row.answerable_passed}
                      total={row.answerable_total}
                      paint={SERIES_PAINT.answerable}
                      label={t.ratio(row.answerable_passed, row.answerable_total)}
                    />
                  </td>
                  <td className="py-2">
                    <SweepCell
                      passed={row.other_passed}
                      total={row.other_total}
                      paint={SERIES_PAINT.other}
                      label={t.ratio(row.other_passed, row.other_total)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="text-caption text-text-tertiary">{t.sweepNote}</p>
    </div>
  )
}

function SweepCell({
  passed,
  total,
  paint,
  label,
}: {
  passed: number
  total: number
  paint: string
  label: string
}) {
  const ratio = total > 0 ? passed / total : 0
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-mono text-mono tabular-nums text-foreground">{label}</span>
      <span
        aria-hidden="true"
        className="inline-block h-1.5 w-16 overflow-hidden rounded-sm bg-border align-middle"
      >
        <span
          className="block h-full rounded-sm"
          style={{ width: `${ratio * 100}%`, backgroundColor: paint }}
        />
      </span>
    </span>
  )
}
