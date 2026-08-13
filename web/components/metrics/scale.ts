/**
 * Grafikler için saf ölçek/yerleşim matematiği.
 *
 * Neden kütüphane yok: gösterilecek veri iki küçük skor dizisi ve yedi
 * satırlık bir tablo. Bir grafik kütüphanesi bundle'ı şişirir ve "hiçbir
 * dış istek yok" iddiasına risk ekler (docs/DESIGN_SYSTEM.md §2.1'deki
 * CDN kararının aynı gerekçesi). Bu dosyadaki her şey saf fonksiyon —
 * rastgelelik veya zaman kullanmaz, böylece render sırasında güvenle
 * çağrılabilir (react-hooks/purity).
 *
 * Ölçek çıktısı YÜZDE'dir: SVG uzunlukları yüzde birimini kabul eder
 * (`cx="63.2%"`), böylece grafik viewBox'sız çizilebilir. viewBox +
 * uniform ölçekleme kullanılsaydı dar ekranda yazılar ve nokta yarıçapı
 * da küçülürdü; yüzde koordinatla yatay eksen esner, işaretler ve metin
 * gerçek piksel boyutunda kalır.
 */

/** Kapalı aralık; `null` = dizi boş. */
export type Extent = readonly [number, number]

export function extentOf(values: readonly number[]): Extent | null {
  if (values.length === 0) return null
  let lo = values[0]
  let hi = values[0]
  for (const v of values) {
    if (v < lo) lo = v
    if (v > hi) hi = v
  }
  return [lo, hi]
}

/** İki aralığın kesişimi — grafikte "örtüşme bölgesi" budur. */
export function intersect(a: Extent | null, b: Extent | null): Extent | null {
  if (!a || !b) return null
  const lo = Math.max(a[0], b[0])
  const hi = Math.min(a[1], b[1])
  return hi > lo ? [lo, hi] : null
}

export function countWithin(values: readonly number[], range: Extent): number {
  return values.filter((v) => v >= range[0] && v <= range[1]).length
}

export interface LinearScale {
  domain: Extent
  /** Değeri 0–100 arası yüzdeye çevirir (SVG `%` birimi için hazır). */
  percentOf: (value: number) => number
}

/**
 * Verilen tüm değerleri kapsayan, iki yanı paylı doğrusal ölçek.
 * Alan adı gereği 0–1 dışına taşmaz (skorlar kosinüs benzerliği).
 */
export function makeScale(values: readonly number[], padRatio = 0.06): LinearScale {
  const span = extentOf(values)
  if (!span || span[0] === span[1]) {
    const center = span ? span[0] : 0.5
    const lo = Math.max(0, center - 0.05)
    const hi = Math.min(1, center + 0.05)
    return buildScale([lo, hi === lo ? lo + 0.1 : hi])
  }
  const pad = Math.max(0.01, (span[1] - span[0]) * padRatio)
  return buildScale([Math.max(0, span[0] - pad), Math.min(1, span[1] + pad)])
}

function buildScale(domain: Extent): LinearScale {
  const [lo, hi] = domain
  const width = hi - lo || 1
  return {
    domain,
    percentOf: (value: number) => ((value - lo) / width) * 100,
  }
}

export interface SwarmPoint {
  value: number
  /** Yatay konum, 0–100 yüzde. */
  percent: number
  /** Şeridin merkezine göre dikey kayma, piksel. */
  offset: number
}

/**
 * Üst üste binen noktaları dikeyde katmanlara ayırır (mini "beeswarm").
 * Rastgele jitter YOK: aynı veri her render'da aynı yerleşimi üretir.
 */
export function swarm(
  values: readonly number[],
  percentOf: (value: number) => number,
  minGapPercent: number,
  offsets: readonly number[]
): SwarmPoint[] {
  const placed: SwarmPoint[] = []
  const sorted = [...values].sort((a, b) => a - b)
  for (const value of sorted) {
    const percent = percentOf(value)
    let level = 0
    while (level < offsets.length - 1) {
      const collides = placed.some(
        (p) =>
          p.offset === offsets[level] &&
          Math.abs(p.percent - percent) < minGapPercent
      )
      if (!collides) break
      level += 1
    }
    placed.push({ value, percent, offset: offsets[level] })
  }
  return placed
}

/**
 * Eksen çentikleri. Tarama tablosundaki eşikler doğal çentiklerdir —
 * grafik ile alttaki tablo tam olarak aynı sayıları gösterir. Tablo alan
 * adının tamamını kapsamadığı için (tarama 0.70'te biter, skorlar daha
 * yukarı çıkar) aynı adımla iki yöne uzatılır; eşik listede yoksa eklenir.
 */
export function buildTicks(
  candidates: readonly number[],
  threshold: number,
  domain: Extent
): number[] {
  const sorted = [...new Set(candidates)].sort((a, b) => a - b)
  const step = inferStep(sorted)
  const base = sorted.length > 0 ? extend(sorted, step, domain) : fallbackTicks(domain)
  const within = base.filter((v) => v >= domain[0] && v <= domain[1])
  const hasThreshold = within.some((v) => Math.abs(v - threshold) < 0.005)
  const all = hasThreshold ? within : [...within, threshold]
  return [...new Set(all.map((v) => round(v)))].sort((a, b) => a - b)
}

/** Kayan nokta birikmesini temizler; 0.6500000000000001 gibi etiketleri önler. */
function round(value: number): number {
  return Math.round(value * 1e6) / 1e6
}

function inferStep(sorted: readonly number[]): number {
  if (sorted.length < 2) return 0.05
  const gaps = sorted.slice(1).map((v, i) => v - sorted[i])
  return Math.min(...gaps)
}

function extend(sorted: readonly number[], step: number, domain: Extent): number[] {
  if (step <= 0) return [...sorted]
  const ticks = [...sorted]
  for (let v = sorted[0] - step; v >= domain[0]; v -= step) ticks.unshift(v)
  const last = sorted[sorted.length - 1]
  for (let v = last + step; v <= domain[1]; v += step) ticks.push(v)
  return ticks
}

function fallbackTicks(domain: Extent): number[] {
  const [lo, hi] = domain
  const steps = 5
  return Array.from({ length: steps + 1 }, (_, i) => lo + ((hi - lo) * i) / steps)
}

/**
 * Bir eşikte cevaplanabilir soruların TAMAMININ hâlâ geçtiği en yüksek
 * değer. Kalibrasyon hikâyesinin kanıtı bu: değerlendirme setine bakarak
 * eşiği buraya kadar yükseltmek "bedelsiz" görünür, oysa set dışı sorular
 * çoktan elenmeye başlamıştır. `null` = hiçbir satırda tam geçiş yok.
 */
export function fullPassHeadroom(
  rows: readonly { threshold: number; answerable_passed: number; answerable_total: number }[]
): number | null {
  const fullPass = rows.filter(
    (r) => r.answerable_total > 0 && r.answerable_passed === r.answerable_total
  )
  if (fullPass.length === 0) return null
  return fullPass.reduce((max, r) => (r.threshold > max ? r.threshold : max), fullPass[0].threshold)
}
