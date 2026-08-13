import type { Namespace } from "./index"

/**
 * Belge yönetimi (sidebar) + uygulama iskeleti metinleri — DESIGN_SYSTEM.md §7.
 *
 * Kural: `components/shell/**` ve `components/sidebar/**` altındaki hiçbir
 * bileşen sabit string yazmaz; kullanıcıya görünen her metin buradan gelir.
 * Sayı/isim içeren metinler string birleştirme ile değil FONKSİYON olarak
 * kurulur (§7 adlandırma kuralı).
 *
 * Not — backend'den gelen ham metin doğrudan basılmaz (§7 [!warning]):
 *  - `/api/documents` SSE'sinin `stage` alanı motordan TÜRKÇE gelir
 *    (rag/ingest.py: "32/41 chunk embed edildi"). `stage*` anahtarları bu
 *    metinlerin yerelleştirilmiş karşılığıdır; eşleme
 *    components/sidebar/upload-stage.ts içinde yapılır.
 *  - Hata gövdesinin `message` alanı da Türkçedir; UI yalnızca `code`'a
 *    bakar ve buradaki `error*` anahtarlarını basar
 *    (components/sidebar/error-messages.ts).
 */
export const sidebar = {
  // --- AppShell: bölge adları ve drawer kontrolleri (§4) ---
  panelTitle: { tr: "Bilgi tabanı", en: "Knowledge base" },
  regionDocuments: { tr: "Belge yönetimi", en: "Document management" },
  regionChat: { tr: "Sohbet", en: "Chat" },
  regionSources: { tr: "Kaynak incelemesi", en: "Source inspector" },
  sourcesPanelTitle: { tr: "Kaynaklar", en: "Sources" },
  openDocuments: { tr: "Belge panelini aç", en: "Open document panel" },
  closeDocuments: { tr: "Belge panelini kapat", en: "Close document panel" },
  openSources: { tr: "Kaynak panelini aç", en: "Open source panel" },
  closeSources: { tr: "Kaynak panelini kapat", en: "Close source panel" },

  // --- DocumentUploader (FEATURE_SPEC §1.1) ---
  uploadTitle: { tr: "PDF yükleyin", en: "Upload PDF" },
  uploadHint: {
    tr: "Dosyaları buraya sürükleyin ya da seçin. Belgeler cihazınızdan çıkmaz.",
    en: "Drag files here or pick them. Documents never leave your device.",
  },
  uploadBrowse: { tr: "Dosya seç", en: "Choose files" },
  uploadDropActive: { tr: "PDF'leri bırakın", en: "Drop the PDFs" },
  uploadArea: { tr: "PDF yükleme alanı", en: "PDF upload area" },
  uploadWarming: {
    tr: "Modeller hazırlanıyor; yükleme birazdan açılacak.",
    en: "Models are warming up; uploading unlocks shortly.",
  },
  uploadBusyHint: {
    tr: "Yükleme sürerken sohbet kilitli kalır.",
    en: "Chat stays locked while an upload is running.",
  },
  clearFinished: { tr: "Tamamlananları temizle", en: "Clear finished" },
  removeFromList: { tr: "Listeden çıkar", en: "Remove from list" },

  // --- Yükleme aşamaları (SSE `progress.stage` karşılıkları, §3.4) ---
  stageQueued: { tr: "Sırada", en: "Queued" },
  stageReading: {
    tr: (filename: string) => `${filename} okunuyor…`,
    en: (filename: string) => `Reading ${filename}…`,
  },
  stageEmbeddingStart: {
    tr: (total: number) => `${total} bölüm gömülüyor…`,
    en: (total: number) => `Embedding ${total} chunk${total === 1 ? "" : "s"}…`,
  },
  stageEmbedding: {
    tr: (done: number, total: number) => `${done}/${total} bölüm gömüldü`,
    en: (done: number, total: number) => `${done}/${total} chunks embedded`,
  },
  stageSaving: {
    tr: "Veritabanına yazılıyor…",
    en: "Writing to the database…",
  },
  stageWorking: { tr: "İşleniyor…", en: "Processing…" },

  // --- Yükleme sonuçları ---
  uploadDone: {
    tr: (chunks: number) => `${chunks} bölüm eklendi`,
    en: (chunks: number) => `${chunks} chunk${chunks === 1 ? "" : "s"} added`,
  },
  uploadReplaced: {
    tr: "Aynı adlı belge güncellendi",
    en: "Existing document updated",
  },
  uploadFailed: { tr: "Yükleme başarısız", en: "Upload failed" },
  pagesSkipped: {
    tr: (n: number) => `${n} sayfa okunamadı`,
    en: (n: number) => `${n} page${n === 1 ? "" : "s"} could not be read`,
  },
  skippedPagesList: {
    tr: (pages: readonly number[]) => `Atlanan sayfalar: ${pages.join(", ")}`,
    en: (pages: readonly number[]) => `Skipped pages: ${pages.join(", ")}`,
  },

  // --- Hata kodları (FEATURE_SPEC §2.2) + istemci ön kontrolleri ---
  errorNotPdf: {
    tr: "Yalnızca PDF dosyası yüklenebilir.",
    en: "Only PDF files can be uploaded.",
  },
  errorFileTooLarge: {
    tr: (mb: number) => `Dosya ${mb} MB sınırını aşıyor.`,
    en: (mb: number) => `The file exceeds the ${mb} MB limit.`,
  },
  errorInvalidPdf: {
    tr: "PDF açılamadı; bozuk ya da şifreli olabilir.",
    en: "The PDF could not be opened; it may be corrupt or encrypted.",
  },
  errorNoContent: {
    tr: "Belge boş ya da tamamen taranmış görüntüden oluşuyor.",
    en: "The document is empty or made entirely of scanned images.",
  },
  errorModelWarming: {
    tr: "Modeller henüz hazır değil.",
    en: "The models are not ready yet.",
  },
  errorNotFound: { tr: "Belge bulunamadı.", en: "Document not found." },
  errorNoDocuments: {
    tr: "Korpus boş; önce belge yükleyin.",
    en: "The corpus is empty; upload a document first.",
  },

  // --- DocumentList / DocumentCard (FEATURE_SPEC §1.4, §5) ---
  documentsTitle: { tr: "Belgeler", en: "Documents" },
  documentCount: {
    tr: (n: number) => `${n} belge`,
    en: (n: number) => `${n} document${n === 1 ? "" : "s"}`,
  },
  refresh: { tr: "Listeyi yenile", en: "Refresh list" },
  emptyTitle: { tr: "Henüz belge yok", en: "No documents yet" },
  emptyBody: {
    tr: "Soru sorabilmek için önce bir PDF yükleyin.",
    en: "Upload a PDF before you can ask questions.",
  },
  emptyHint: {
    tr: "Yükleme, indeksleme ve arama tamamen çevrimdışı çalışır.",
    en: "Ingestion, indexing and search all run fully offline.",
  },
  listFailed: {
    tr: "Belge listesi alınamadı.",
    en: "Could not load the document list.",
  },
  pageCount: {
    tr: (n: number) => `${n} sayfa`,
    en: (n: number) => `${n} page${n === 1 ? "" : "s"}`,
  },
  chunkCount: {
    tr: (n: number) => `${n} bölüm`,
    en: (n: number) => `${n} chunk${n === 1 ? "" : "s"}`,
  },
  addedAt: {
    tr: (date: string) => `Eklendi: ${date}`,
    en: (date: string) => `Added ${date}`,
  },
  ocrBadge: { tr: "OCR", en: "OCR" },
  ocrTooltip: {
    tr: "Bu belgenin bazı bölümleri OCR ile okundu; o metin daha az güvenilir olabilir.",
    en: "Parts of this document were read with OCR; that text can be less reliable.",
  },
  deleteAction: {
    tr: (filename: string) => `${filename} belgesini sil`,
    en: (filename: string) => `Delete ${filename}`,
  },
  deleteConfirmTitle: { tr: "Belge silinsin mi?", en: "Delete this document?" },
  deleteConfirmBody: {
    tr: (filename: string) =>
      `“${filename}” ve ona ait tüm bölümler kalıcı olarak silinecek.`,
    en: (filename: string) =>
      `“${filename}” and all of its chunks will be removed permanently.`,
  },
  deleteLastWarning: {
    tr: "Bu son belge. Silindiğinde sohbet boş duruma döner.",
    en: "This is the last document. Deleting it returns the chat to its empty state.",
  },
  deleting: { tr: "Siliniyor…", en: "Deleting…" },
  deleteFailed: {
    tr: "Belge silinemedi.",
    en: "Could not delete the document.",
  },

  // --- CorpusStats ---
  corpusTitle: { tr: "Korpus", en: "Corpus" },
  corpusDocuments: { tr: "Belge", en: "Docs" },
  corpusChunks: { tr: "Bölüm", en: "Chunks" },
  corpusPages: { tr: "Sayfa", en: "Pages" },

  // --- SystemStatus (/api/health, FEATURE_SPEC §2.1, §7) ---
  systemTitle: { tr: "Sistem", en: "System" },
  statusReady: { tr: "Hazır", en: "Ready" },
  statusWarming: { tr: "Modeller yükleniyor…", en: "Loading models…" },
  statusError: { tr: "Sistem yanıt vermiyor", en: "System not responding" },
  statusUnknown: { tr: "Durum okunuyor…", en: "Reading status…" },
  warmingHint: {
    tr: "Modeller belleğe alınıyor; ilk açılışta birkaç dakika sürebilir. Bu sırada soru sorulamaz.",
    en: "Models are loading into memory; the first start can take a few minutes. Questions are locked until then.",
  },
  chatModelLabel: { tr: "Sohbet modeli", en: "Chat model" },
  embeddingModelLabel: { tr: "Gömme modeli", en: "Embedding model" },
  topKLabel: { tr: "Getirilen bölüm", en: "Retrieved chunks" },
  topKHint: {
    tr: "Her soruda en iyi eşleşen kaç bölümün getirileceği (top_k).",
    en: "How many best-matching chunks each question retrieves (top_k).",
  },
  minScoreLabel: { tr: "Eşik", en: "Threshold" },
  minScoreHint: {
    tr: "Bu skorun altında kalan bölümler modele hiç gönderilmez (min_score).",
    en: "Chunks scoring below this never reach the model (min_score).",
  },
  ocrLabel: { tr: "OCR", en: "OCR" },
  ocrAvailable: { tr: "Kullanılabilir", en: "Available" },
  ocrUnavailable: { tr: "Kapalı", en: "Off" },
  healthFailed: {
    tr: "Sistem durumu okunamadı.",
    en: "Could not read system status.",
  },
} as const satisfies Namespace
