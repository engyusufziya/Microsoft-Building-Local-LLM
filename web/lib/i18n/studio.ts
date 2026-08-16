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

  // --- Studio sekmesi: boş durum (§9.9.4) ---
  emptyTitle: { tr: "Henüz artefakt yok", en: "No artifacts yet" },
  emptyBody: {
    tr: "Korpusunuzdan kaynakları doğrulanmış bir rapor üretin.",
    en: "Generate a report from your corpus with every sentence traced to a source.",
  },
  emptyNote: {
    tr: "Zihin haritası ve quiz sonraki fazlarda geliyor.",
    en: "Mind map and quiz are coming in later phases.",
  },

  // --- Üretim akışı (Faz 2, §10.11) ---
  generateReport: { tr: "Rapor üret", en: "Generate report" },
  generating: { tr: "Üretiliyor…", en: "Generating…" },
  generateHint: {
    tr: "Rapor korpusun tamamından üretilir ve birkaç dakika sürer.",
    en: "The report is generated from the whole corpus and takes a few minutes.",
  },
  progressAria: { tr: "Rapor üretim ilerlemesi", en: "Report generation progress" },
  artifactListLabel: { tr: "Üretilen artefaktlar", en: "Generated artifacts" },
  openArtifact: { tr: "Aç", en: "Open" },
  closeArtifact: { tr: "Raporu kapat", en: "Close report" },
  staleBadge: { tr: "korpus değişti", en: "corpus changed" },
  staleHint: {
    tr: "Bu artefakt üretildiğinden beri korpus değişti; yeniden üretmediğiniz sürece eski korpusu anlatır.",
    en: "The corpus changed after this artifact was generated; it still describes the old corpus until you regenerate it.",
  },
  retry: { tr: "Tekrar dene", en: "Retry" },

  // Hata metinleri backend'in {code} alanından seçilir; ham (Türkçe) mesaj
  // arayüz diline sızmasın diye burada yerelleştirilir.
  errorInsufficientCorpus: {
    tr: "Korpus rapor üretmek için yeterli değil — daha fazla belge yükleyin.",
    en: "The corpus is too small to generate a report — upload more documents.",
  },
  errorModelWarming: {
    tr: "Modeller henüz yüklenmedi; hazır olduğunda tekrar deneyin.",
    en: "Models are still loading; try again once they are ready.",
  },
  errorGenerationFailed: {
    tr: "Üretim tamamlanamadı.",
    en: "Generation could not be completed.",
  },
  errorGeneric: { tr: "İstek başarısız oldu.", en: "The request failed." },

  // --- Rapor görünümü (§10.12) ---
  reportLoading: { tr: "Rapor yükleniyor…", en: "Loading report…" },
  tablesHeading: { tr: "Tablolar", en: "Tables" },
  citationsHeading: { tr: "Kaynaklar", en: "Sources" },
  droppedHeading: { tr: "Rapordan çıkarılan iddialar", en: "Claims removed from the report" },
  droppedIntro: {
    tr: "Bu cümleler kaynağa yeterince bağlanamadığı için rapor gövdesine alınmadı. Ürün sınırını gizlemiyoruz.",
    en: "These sentences were not published in the report body because they could not be tied to a source. We do not hide this limit.",
  },
  droppedReasonUnsupported: { tr: "kaynağa bağlanamadı", en: "not tied to a source" },
  droppedReasonWeak: { tr: "bağ zayıf", en: "weak binding" },
  droppedReasonUnverifiedTerms: {
    tr: "terimler bağlamda doğrulanamadı",
    en: "terms not verified in context",
  },
  droppedTerms: {
    tr: (terms: string[]) => `Doğrulanamayan terimler: ${terms.join(", ")}`,
    en: (terms: string[]) => `Unverified terms: ${terms.join(", ")}`,
  },
  fidelityLabel: { tr: "Sadakat oranı", en: "Fidelity ratio" },
  fidelityHint: {
    tr: "Bağlanabilen iddia / toplam iddia. Benzerlik skoru DEĞİLDİR; retrieval güven bantlarıyla renklendirilmez.",
    en: "Bound claims / total claims. This is NOT a similarity score; it is not colored with the retrieval confidence bands.",
  },
  droppedCountLabel: { tr: "Çıkarılan iddia", en: "Removed claims" },
  claimCountLabel: { tr: "Rapordaki cümle", en: "Sentences in report" },
  exportMarkdown: { tr: "Markdown indir", en: "Download Markdown" },
  print: { tr: "Yazdır / PDF", en: "Print / PDF" },
  sourceCountLabel: {
    tr: (n: number) => `${n} kaynak bölüm`,
    en: (n: number) => `${n} source chunks`,
  },
} as const satisfies Namespace
