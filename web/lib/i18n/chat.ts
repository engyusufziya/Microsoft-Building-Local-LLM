import type { Namespace } from "./index"

/**
 * Sohbet + Retrieval Inspector metinleri — DESIGN_SYSTEM.md §7.
 *
 * Bu dosya `frontend-chat`'e ait TEK metin kaynağıdır: components/chat/** ve
 * components/inspector/** içinde sabit string bulunmaz, hepsi buradan gelir.
 *
 * `noAnswer` özel bir anahtar: FEATURE_SPEC §3.2'ye göre hem `below_threshold`
 * (LLM hiç çağrılmadı) hem `llm_refused` (LLM Türkçe ret metnini akıttı)
 * dallarında ekrana basılan metin BUDUR. Backend'den gelen ham
 * `NO_ANSWER_TEXT` doğrudan gösterilmez — aksi halde UI dili İngilizce iken
 * Türkçe metin basılırdı.
 */
export const chat = {
  // ------------------------------------------------------------------ panel
  panelTitle: { tr: "Sohbet", en: "Chat" },
  assistantLabel: { tr: "Asistan", en: "Assistant" },
  userLabel: { tr: "Siz", en: "You" },

  // -------------------------------------------------- boş durumlar (§5)
  emptyNoDocumentsTitle: {
    tr: "Önce bir belge yükleyin",
    en: "Upload a document first",
  },
  emptyNoDocumentsBody: {
    tr: "Bu asistan yalnızca sizin yüklediğiniz belgelerden cevap üretir. Soru sorabilmek için soldaki panelden en az bir PDF yükleyin.",
    en: "This assistant answers only from documents you upload. Add at least one PDF from the sidebar to start asking questions.",
  },
  emptyNoQuestionTitle: {
    tr: "Belgelerinize soru sorun",
    en: "Ask your documents",
  },
  emptyNoQuestionBody: {
    tr: "Cevaplar yalnızca yüklediğiniz belgelerden üretilir; model kendi bilgisini eklemez. Sağdaki panel hangi bölümlerin kullanıldığını ve skorlarını gösterir.",
    en: "Answers are produced only from your uploaded documents; the model adds nothing of its own. The panel on the right shows which passages were used and their scores.",
  },
  suggestionsLabel: { tr: "Örnek sorular", en: "Try asking" },
  suggestion1: {
    tr: "Bu belgeler ne hakkında?",
    en: "What are these documents about?",
  },
  suggestion2: {
    tr: "Ana adımlar nelerdir?",
    en: "What are the main steps?",
  },
  suggestion3: {
    tr: "Öne çıkan sayılar neler?",
    en: "What are the key numbers?",
  },

  // ------------------------------------------------------------------ girdi
  inputPlaceholder: {
    tr: "Belgelerinize bir soru sorun…",
    en: "Ask a question about your documents…",
  },
  send: { tr: "Gönder", en: "Send" },
  sendHintMac: { tr: "⌘ + Enter ile gönder", en: "⌘ + Enter to send" },
  sendHintOther: { tr: "Ctrl + Enter ile gönder", en: "Ctrl + Enter to send" },

  // Girdi kilidi — sebep HER ZAMAN yazılır (FEATURE_SPEC §1.1 [!important], §5).
  lockWarming: {
    tr: "Modeller yükleniyor, birazdan hazır olacak.",
    en: "Models are loading, this will be ready shortly.",
  },
  lockUploading: {
    tr: "Belge yükleniyor. Aynı embedding modeli kullanıldığı için yükleme bitene kadar soru sorulamaz.",
    en: "A document is being ingested. Questions are paused until it finishes, because both use the same embedding model.",
  },
  lockNoDocuments: {
    tr: "Soru sorabilmek için önce bir belge yükleyin.",
    en: "Upload a document before asking a question.",
  },
  lockModelError: {
    tr: "Modeller yüklenemedi. Foundry Local çalışıyor mu kontrol edin.",
    en: "Models could not be loaded. Check that Foundry Local is running.",
  },
  lockBusy: {
    tr: "Önceki soru hâlâ cevaplanıyor.",
    en: "The previous question is still being answered.",
  },

  // ---------------------------------------------- aşamalı gösterge (§1.2)
  phaseSearching: { tr: "Belgelerde aranıyor…", en: "Searching your documents…" },
  phaseGenerating: { tr: "Cevap üretiliyor…", en: "Generating the answer…" },

  // ------------------------------------------------------------- sonuçlar
  /**
   * FEATURE_SPEC §3.2 — `below_threshold` ve `llm_refused` dallarının
   * yerelleştirilmiş cevabı. Motorun ham Türkçe `NO_ANSWER_TEXT`'i yerine
   * bu basılır.
   */
  noAnswer: {
    tr: "Bu bilgi yüklediğiniz belgelerde yok.",
    en: "That information is not in the documents you uploaded.",
  },
  noAnswerBelowThreshold: {
    tr: "Sorunuza yeterince yakın bir bölüm bulunamadı, bu yüzden dil modeli hiç çağrılmadı.",
    en: "No passage was close enough to your question, so the language model was never called.",
  },
  noAnswerRefused: {
    tr: "İlgili bölümler bulundu ama cevabı içermiyorlardı.",
    en: "Relevant passages were found, but none of them contained the answer.",
  },

  sourcesLabel: { tr: "Kaynaklar", en: "Sources" },
  sourceChipHint: {
    tr: "Bu bölümü sağdaki panelde göster",
    en: "Show this passage in the panel",
  },
  openInspector: { tr: "Kaynakları incele", en: "Inspect sources" },

  // Akış ortasında kopma — kısmi metin korunur (§5 [!tip]).
  streamIncomplete: {
    tr: "Yanıt tamamlanamadı.",
    en: "The answer could not be completed.",
  },
  errorTitle: { tr: "Cevap alınamadı", en: "Could not get an answer" },
  errorNoDocuments: {
    tr: "Korpus boş. Önce bir belge yükleyin.",
    en: "The corpus is empty. Upload a document first.",
  },
  errorModelWarming: {
    tr: "Modeller henüz hazır değil, birkaç saniye sonra tekrar deneyin.",
    en: "The models are not ready yet — try again in a few seconds.",
  },
  errorEmptyQuery: { tr: "Soru boş olamaz.", en: "The question cannot be empty." },

  elapsedSeconds: {
    tr: (ms: number) => `${(ms / 1000).toFixed(1)} sn`,
    en: (ms: number) => `${(ms / 1000).toFixed(1)} s`,
  },

  // ----------------------------------------------------- Inspector (§4)
  inspectorTitle: { tr: "Retrieval Inspector", en: "Retrieval Inspector" },
  inspectorSubtitle: {
    tr: "Cevabın hangi bölümlerden üretildiği",
    en: "Which passages the answer came from",
  },
  inspectorEmptyTitle: { tr: "Soru sorun", en: "Ask a question" },
  inspectorEmptyBody: {
    tr: "Bir soru sorduğunuzda, getirilen bölümler skorlarıyla birlikte burada listelenir — elenenler dahil.",
    en: "Once you ask something, the retrieved passages appear here with their scores — including the ones that were filtered out.",
  },
  inspectorSearchingTitle: { tr: "Bölümler aranıyor…", en: "Retrieving passages…" },
  inspectorSummary: {
    tr: (passed: number, total: number) =>
      `${total} bölüm getirildi, ${passed} tanesi eşiği geçti`,
    en: (passed: number, total: number) =>
      `${total} passage(s) retrieved, ${passed} above the threshold`,
  },
  inspectorElapsed: {
    tr: (ms: number) => `${ms} ms`,
    en: (ms: number) => `${ms} ms`,
  },

  /** §4.3 eşik çizgisi etiketi — değer olaydan gelir, koda gömülmez. */
  thresholdLine: {
    tr: (value: number) => `eşik ${value.toFixed(2)}`,
    en: (value: number) => `threshold ${value.toFixed(2)}`,
  },
  nonePassedTitle: {
    tr: "Hiçbir bölüm eşiği geçemedi",
    en: "No passage passed the threshold",
  },
  nonePassedBody: {
    tr: "Aşağıdaki bölümler getirildi ama hepsi eşiğin altında kaldı; dil modeline hiçbiri gönderilmedi.",
    en: "The passages below were retrieved but all scored under the threshold, so none were sent to the language model.",
  },
  allPassedNote: {
    tr: "Getirilen bölümlerin tümü eşiği geçti.",
    en: "Every retrieved passage passed the threshold.",
  },

  // ------------------------------------------------------- ChunkCard (§4.2)
  rejectedBadge: { tr: "elendi", en: "filtered out" },
  rejectedHint: {
    tr: "Eşiğin altında kaldı, dil modeline gönderilmedi.",
    en: "Below the threshold — never sent to the language model.",
  },
  ocrBadge: { tr: "OCR", en: "OCR" },
  ocrHint: {
    tr: "Bu bölüm taranmış sayfadan OCR ile okundu, metin hataları olabilir.",
    en: "This passage was read from a scanned page via OCR and may contain errors.",
  },
  pageLabel: {
    tr: (page: number) => `s.${page}`,
    en: (page: number) => `p.${page}`,
  },
  pageAria: {
    tr: (page: number) => `Sayfa ${page}`,
    en: (page: number) => `Page ${page}`,
  },
  expandChunk: { tr: "Tamamını göster", en: "Show full text" },
  collapseChunk: { tr: "Kısalt", en: "Show less" },

  scoreBandStrong: { tr: "güçlü", en: "strong" },
  scoreBandMedium: { tr: "orta", en: "medium" },
  scoreBandWeak: { tr: "zayıf", en: "weak" },
  scoreBandRejected: { tr: "elendi", en: "filtered out" },
  scoreAria: {
    tr: (band: string, score: number) =>
      `İlgi skoru ${score.toFixed(2)} — ${band}`,
    en: (band: string, score: number) =>
      `Relevance score ${score.toFixed(2)} — ${band}`,
  },
} as const satisfies Namespace
