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

  // --- Üretim akışı (Faz 2, §10.11) ---
  generateReport: { tr: "Rapor üret", en: "Generate report" },
  generating: { tr: "Üretiliyor…", en: "Generating…" },
  generateHint: {
    tr: "Rapor korpusun tamamından üretilir ve birkaç dakika sürer.",
    en: "The report is generated from the whole corpus and takes a few minutes.",
  },
  progressAria: { tr: "Rapor üretim ilerlemesi", en: "Report generation progress" },
  artifactListLabel: { tr: "Üretilen artefaktlar", en: "Generated artifacts" },

  // --- Kapsam seçimi (§9.7: scope="corpus" | "document") ---
  scopeLabel: { tr: "Kapsam", en: "Scope" },
  scopeCorpus: { tr: "Tüm belgeler", en: "All documents" },
  scopeHintDocument: {
    tr: "Artefakt yalnızca seçili belgeden üretilir.",
    en: "The artifact is generated from the selected document only.",
  },
  errorDocumentNotFound: {
    tr: "Seçili belge artık yüklü değil; kapsamı yeniden seçin.",
    en: "The selected document is no longer loaded; pick the scope again.",
  },
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

  // --- Artefakt tipleri (Faz 3-4) ---
  generateMindMap: { tr: "Zihin haritası üret", en: "Generate mind map" },
  generateQuiz: { tr: "Quiz üret", en: "Generate quiz" },
  kindReport: { tr: "Rapor", en: "Report" },
  kindMindMap: { tr: "Zihin haritası", en: "Mind map" },
  kindQuiz: { tr: "Quiz", en: "Quiz" },
  emptyBodyAll: {
    tr: "Korpusunuzdan kaynakları doğrulanmış bir rapor, zihin haritası veya quiz üretin.",
    en: "Generate a source-verified report, mind map, or quiz from your corpus.",
  },
  emptyNoteAll: {
    tr: "Her cümle, her düğüm ve her cevap bir belge bölümüne bağlıdır.",
    en: "Every sentence, node, and answer is tied to a document chunk.",
  },

  // --- Zihin haritası (§11.9) ---
  mindMapAria: { tr: "Zihin haritası", en: "Mind map" },
  mindMapHint: {
    tr: "Düğümler arasında ok tuşlarıyla gezinin; seçili düğümün kaynakları yanda listelenir.",
    en: "Move between nodes with the arrow keys; the selected node's sources are listed beside it.",
  },
  mindMapNodeCount: {
    tr: (n: number) => `${n} konu`,
    en: (n: number) => `${n} topics`,
  },
  mindMapEdgeCount: {
    tr: (n: number) => `${n} ilişki`,
    en: (n: number) => `${n} links`,
  },
  mindMapEdgeHint: {
    tr: "İki konu merkezi arasındaki ham cosine benzerliği eşiği aştığında çizilir. Kenar yokluğu hata değildir.",
    en: "A link is drawn when the raw cosine between two topic centroids passes the threshold. No links is not an error.",
  },
  mindMapNoEdges: {
    tr: "Konular birbirinden uzak: bu korpusta ilişki çizgisi yok.",
    en: "The topics are far apart: no links in this corpus.",
  },
  labelSourceFallback: { tr: "korpustan türetildi", en: "derived from corpus" },
  labelSourceFallbackHint: {
    tr: "Modelin önerdiği etiket sadakat kapısından geçemedi. Düğüm silinmedi; adı korpustaki baskın belgeden türetildi.",
    en: "The model's proposed label did not pass the fidelity gate. The node was not removed; its name is derived from the dominant source document.",
  },
  droppedLabelsHeading: {
    tr: "Haritaya alınmayan etiket önerileri",
    en: "Label suggestions kept out of the map",
  },
  droppedReasonLabelInvalid: {
    tr: "biçim tutmadı (boş ya da çok uzun)",
    en: "malformed (empty or too long)",
  },
  nodeSourcesHeading: { tr: "Düğümün kaynakları", en: "Sources for this node" },
  nodeSelectHint: {
    tr: "Kaynaklarını görmek için bir düğüm seçin.",
    en: "Select a node to see its sources.",
  },

  // --- Quiz (§12.11) ---
  quizAria: { tr: "Quiz soruları", en: "Quiz questions" },
  quizQuestionCount: {
    tr: (n: number) => `${n} soru`,
    en: (n: number) => `${n} questions`,
  },
  quizIntro: {
    tr: "Her sorunun cevabı yüklediğiniz belgelerde doğrulanabilir. Cevapladıktan sonra kaynağı görürsünüz.",
    en: "Every answer is verifiable in your uploaded documents. You see the source after you submit.",
  },
  quizTypeMultipleChoice: { tr: "Çoktan seçmeli", en: "Multiple choice" },
  quizTypeTrueFalse: { tr: "Doğru / Yanlış", en: "True / False" },
  quizTypeFillBlank: { tr: "Boşluk doldurma", en: "Fill in the blank" },
  quizTypeShortAnswer: { tr: "Kısa cevap", en: "Short answer" },
  quizTrue: { tr: "Doğru", en: "True" },
  quizFalse: { tr: "Yanlış", en: "False" },
  quizAnswerPlaceholder: { tr: "Cevabınız", en: "Your answer" },
  quizSubmit: { tr: "Cevapları gönder", en: "Submit answers" },
  quizSubmitting: { tr: "Değerlendiriliyor…", en: "Scoring…" },
  quizRetry: { tr: "Tekrar dene", en: "Try again" },
  quizScoreLabel: { tr: "Puan", en: "Score" },
  quizScoreHint: {
    tr: "Yalnızca kesin puanlanabilen sorular (çoktan seçmeli, doğru/yanlış, boşluk) sayılır. Kısa cevaplar bir eşiğe indirgenmez.",
    en: "Only exactly scorable questions (multiple choice, true/false, fill in the blank) count. Short answers are not reduced to a threshold.",
  },
  quizCorrect: { tr: "Doğru", en: "Correct" },
  quizIncorrect: { tr: "Yanlış", en: "Incorrect" },
  quizExpectedLabel: { tr: "Beklenen cevap", en: "Expected answer" },
  quizEvidenceLabel: { tr: "Belgedeki dayanak", en: "Evidence in the document" },
  quizSimilarityLabel: { tr: "Benzerlik", en: "Similarity" },
  quizSimilarityHint: {
    tr: "Cevabınızla referans cevap arasındaki ham cosine benzerliği. Doğru/yanlış kararı VERİLMEZ; kaynağa bakıp kendi değerlendirmenizi yapın.",
    en: "Raw cosine similarity between your answer and the reference answer. No correct/incorrect verdict is made; check the source and judge for yourself.",
  },
  quizUnanswered: { tr: "boş bırakıldı", en: "left blank" },
  quizDroppedHeading: {
    tr: "Quiz'e alınmayan sorular",
    en: "Questions kept out of the quiz",
  },
  quizNoQuestions: {
    tr: "Bu korpustan doğrulanabilir soru üretilemedi.",
    en: "No verifiable question could be generated from this corpus.",
  },
} as const satisfies Namespace
