import type { MindMapNode, MindMapPayload } from "@/lib/types"

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

/**
 * Düğümleri gezinme sırasına dizer: kök önce, sonra konular.
 *
 * Sıra payload'ın KENDİ düğüm sırasıdır (kümeleme boyuta göre azalan
 * üretir), yani deterministiktir: aynı korpus her zaman aynı haritayı verir.
 * Klavye gezinmesi (ok/Home/End) bu diziyi izler.
 *
 * FAZ 4 NOTU — burada eskiden bir RADYAL YERLEŞİM vardı: kök merkezde,
 * konular çember üzerinde, her düğüm için x/y/anchor hesaplanıyordu. Çizim
 * SVG'den Modernist kutu ağacına geçince o koordinatların HİÇBİRİ okunmaz
 * oldu; ölü matematiği taşımak yerine fonksiyon yaptığı işe indirildi.
 */
export function orderedNodes(payload: MindMapPayload): MindMapNode[] {
  const root = payload.nodes.find((n) => n.kind === "root")
  const topics = payload.nodes.filter((n) => n.kind === "topic")
  return root === undefined ? topics : [root, ...topics]
}

/** Uzun etiketleri SVG'de kırpar (tooltip tam metni gösterir). */
export function truncateLabel(label: string, max = 26): string {
  return label.length <= max ? label : `${label.slice(0, max - 1)}…`
}
