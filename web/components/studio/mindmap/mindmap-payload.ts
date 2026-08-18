import type { MindMapEdge, MindMapNode, MindMapPayload } from "@/lib/types"

/**
 * `payload_json` §11.5'te DONDURULDU. Bu dosya onu render'a hazırlayan SAF
 * yardımcıları taşır — bileşenler payload'ın şeklini TAHMİN ETMEZ.
 *
 * Yerleşim matematiği de burada: `d3-hierarchy` KURULMADI (gerekçe
 * `docs/FEATURE_SPEC.md §11.9`). Bu harita iki seviyelidir (kök → konular);
 * iki seviyeli radyal yerleşim tek satırlık trigonometridir ve d3-hierarchy'nin
 * asıl değeri (derin/düzensiz ağaçların düğüm ayrıştırması) burada hiç
 * kullanılmazdı.
 */

export function asMindMapPayload(
  payload: Record<string, unknown>
): MindMapPayload | null {
  return payload.kind === "mindmap" && Array.isArray(payload.nodes)
    ? (payload as unknown as MindMapPayload)
    : null
}

export interface PlacedNode {
  node: MindMapNode
  x: number
  y: number
  /** Etiketin düğümün soluna mı sağına mı yazılacağı (yarım daireye göre). */
  anchor: "start" | "end" | "middle"
}

export interface MindMapLayout {
  width: number
  height: number
  placed: PlacedNode[]
  byId: Map<string, PlacedNode>
}

/** Görüntü alanı: SVG kendi viewBox'ında ölçeklenir, piksel değil BİRİMDİR. */
const VIEW = { width: 760, height: 560 }
const RADIUS = 210

/**
 * Kök merkezde, konular çevresinde eşit açılı bir çember üzerinde.
 *
 * Sıra payload'ın KENDİ düğüm sırasıdır (kümeleme boyuta göre azalan üretir),
 * yani yerleşim de deterministiktir: aynı korpus her zaman aynı haritayı çizer.
 * Açı -90°'den (saat 12) başlar, böylece ilk (en büyük) konu tepede durur.
 */
export function layoutMindMap(payload: MindMapPayload): MindMapLayout {
  const root = payload.nodes.find((n) => n.kind === "root") ?? null
  const topics = payload.nodes.filter((n) => n.kind === "topic")
  const cx = VIEW.width / 2
  const cy = VIEW.height / 2

  const placed: PlacedNode[] = []
  if (root !== null) {
    placed.push({ node: root, x: cx, y: cy, anchor: "middle" })
  }

  topics.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(topics.length, 1) - Math.PI / 2
    const x = cx + RADIUS * Math.cos(angle)
    const y = cy + RADIUS * Math.sin(angle)
    // Sağ yarıda etiket düğümün sağına, sol yarıda soluna; tam tepede/altta
    // ortalanır ki çember dışına taşan metin kırpılmasın.
    const cos = Math.cos(angle)
    const anchor: PlacedNode["anchor"] =
      Math.abs(cos) < 0.25 ? "middle" : cos > 0 ? "start" : "end"
    placed.push({ node, x, y, anchor })
  })

  return {
    ...VIEW,
    placed,
    byId: new Map(placed.map((p) => [p.node.id, p])),
  }
}

/**
 * Kenar kalınlığı ağırlığa göre: 1–3 birim.
 *
 * DİKKAT — RENK KULLANILMAZ. `weight` ham cosine olsa da
 * `DESIGN_SYSTEM.md §1.2` güven bantları SORGU→CHUNK alaka düzeyi için
 * kalibre edildi; iki KONU MERKEZİ arasındaki benzerlik başka bir sorudur
 * (§11.6). Bantla renklendirmek Inspector'ın anlamını sessizce genişletirdi.
 */
export function edgeWidth(edge: MindMapEdge): number {
  return 1 + Math.max(0, Math.min(1, (edge.weight - 0.5) / 0.4)) * 2
}

/** Uzun etiketleri SVG'de kırpar (tooltip tam metni gösterir). */
export function truncateLabel(label: string, max = 26): string {
  return label.length <= max ? label : `${label.slice(0, max - 1)}…`
}
