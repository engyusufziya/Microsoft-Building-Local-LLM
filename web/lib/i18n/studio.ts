import type { Namespace } from "./index"

/**
 * Studio katmanı metinleri — docs/FEATURE_SPEC.md §9.9.
 *
 * `components/studio/**` içindeki hiçbir bileşen sabit string yazmaz,
 * hepsi buradan gelir (DESIGN_SYSTEM.md §7 kuralı). Faz 1'de yalnızca sağ
 * panelin sekme anahtarı ve Studio sekmesinin boş durumu var; üretim akışı
 * (SSE, artefakt listesi/detayı) metinleri Faz 2'de bu dosyaya eklenir.
 */
export const studio = {
  // --- Sağ panel sekme anahtarı (§9.9.3) ---
  tabListLabel: { tr: "Sağ panel sekmeleri", en: "Right panel tabs" },
  sourcesTab: { tr: "Kaynaklar", en: "Sources" },
  studioTab: { tr: "Studio", en: "Studio" },
  /**
   * Mobil/tablet drawer başlığı (`AppShell`'in `inspectorTitle` prop'u).
   * Artık yalnızca "Kaynaklar" olamaz -- panel iki sekmeyi birden taşıyor.
   */
  panelDrawerTitle: { tr: "Kaynaklar ve Studio", en: "Sources and Studio" },

  // --- Studio sekmesi: Faz 1 boş durumu (§9.9.4) ---
  emptyTitle: { tr: "Henüz artefakt yok", en: "No artifacts yet" },
  emptyBody: {
    tr: "Studio, yüklediğiniz belgelerden zihin haritası, rapor ve quiz gibi artefaktlar üretecek.",
    en: "Studio will generate artifacts like mind maps, reports, and quizzes from your uploaded documents.",
  },
  emptyNote: { tr: "Bu özellik yakında geliyor.", en: "This feature is coming soon." },
} as const satisfies Namespace
