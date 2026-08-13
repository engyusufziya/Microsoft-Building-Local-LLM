import type { Namespace } from "./index"

/**
 * Metrics sayfası metinleri — DESIGN_SYSTEM.md §7.
 *
 * `web/components/metrics/**` altındaki HİÇBİR bileşen sabit string
 * yazmaz; hepsi buradan gelir. Sayı içeren metinler string birleştirme
 * yerine fonksiyon olarak kurulur (§7 adlandırma kuralı).
 *
 * DİKKAT — burada ölçüm SONUCU yazmayın. Bu dosya yalnızca etiket ve
 * açıklama taşır; her sayı `MetricsResponse`'tan gelir (FEATURE_SPEC §6.3:
 * "sahte sayı göstermez"). Kalibrasyon anlatısı da bu yüzden sayısız
 * yazılmıştır — desteklediği rakamlar `threshold_sweep`'ten türetilir.
 */
export const metrics = {
  // ------------------------------------------------------------------ sayfa
  pageTitle: { tr: "Ölçüm ve kalibrasyon", en: "Measurement & calibration" },
  pageSubtitle: {
    tr: "Değerlendirme seti sonuçları, retrieval eşiği taraması ve model kıyası.",
    en: "Evaluation set results, retrieval threshold sweep and model comparison.",
  },
  generatedAt: {
    tr: (when: string) => `Ölçüm zamanı: ${when}`,
    en: (when: string) => `Measured: ${when}`,
  },
  sourceNote: {
    tr: "Bu sayfadaki her sayı önceden üretilmiş eval/results.json dosyasından okunur; istek anında değerlendirme çalıştırılmaz.",
    en: "Every number on this page is read from the pre-generated eval/results.json; no evaluation is run on request.",
  },

  // ------------------------------------------------------------------ durumlar
  loadingLabel: { tr: "Sonuçlar yükleniyor…", en: "Loading results…" },

  notGeneratedTitle: {
    tr: "Değerlendirme henüz çalıştırılmadı",
    en: "The evaluation has not been run yet",
  },
  notGeneratedBody: {
    tr: "Sonuç dosyası (eval/results.json) henüz üretilmedi. Değerlendirme istek anında çalıştırılmaz: yaklaşık iki dakika sürer ve sohbet modeliyle aynı kaynağı kullanır. Bu yüzden burada hiçbir sayı gösterilmiyor — tahmin edilmiş veya örnek değerler basmak, ölçülmüş bir sonuç gibi okunurdu.",
    en: "The results file (eval/results.json) has not been generated yet. The evaluation is never run on request: it takes about two minutes and competes with the chat model for the same resource. No numbers are shown here for that reason — printing estimated or sample values would read as a measured result.",
  },
  notGeneratedHowTo: {
    tr: "Üretmek için (yerel makinede, modeller yüklüyken):",
    en: "To generate it (locally, with the models loaded):",
  },
  commandRunEval: {
    tr: "python eval/run_eval.py --json",
    en: "python eval/run_eval.py --json",
  },
  commandSweep: {
    tr: "python eval/run_eval.py --sweep-threshold --json",
    en: "python eval/run_eval.py --sweep-threshold --json",
  },
  commandCompare: {
    tr: "python eval/run_eval.py --model phi-4-mini --json",
    en: "python eval/run_eval.py --model phi-4-mini --json",
  },

  errorTitle: { tr: "Sonuçlar okunamadı", en: "Could not load the results" },
  emptyModelsTitle: {
    tr: "Sonuç dosyasında model kaydı yok",
    en: "The results file contains no model runs",
  },
  emptyModelsBody: {
    tr: "Dosya eşik taramasını içeriyor olabilir ama hiçbir model çalıştırması kaydedilmemiş.",
    en: "The file may contain the threshold sweep, but no model run was recorded.",
  },

  // ------------------------------------------------------------------ özet kartları
  summaryHeading: { tr: "Özet", en: "Summary" },
  passedLabel: { tr: "Geçen test", en: "Tests passed" },
  passedHelp: {
    tr: "Aktif modelin değerlendirme seti sonucu.",
    en: "Evaluation set result for the active model.",
  },
  categoryLabel: { tr: "Kategori kırılımı", en: "By category" },
  categoryHelp: {
    tr: "Cevaplanabilir · cevaplanamaz · kenar durum.",
    en: "Answerable · unanswerable · edge case.",
  },
  retrievalLabel: { tr: "Retrieval isabeti", en: "Retrieval accuracy" },
  retrievalHelp: {
    tr: "Beklenen kaynak belge, getirilen parçalar arasında bulundu mu.",
    en: "Was the expected source document among the retrieved chunks.",
  },
  avgSecondsLabel: { tr: "Ortalama süre", en: "Average latency" },
  avgSecondsHelp: {
    tr: "Soru başına, akışsız ölçüm.",
    en: "Per question, non-streaming measurement.",
  },

  configHeading: { tr: "Yapılandırma", en: "Configuration" },
  configThreshold: { tr: "Eşik (min_score)", en: "Threshold (min_score)" },
  configTopK: { tr: "Getirilen parça (top_k)", en: "Retrieved chunks (top_k)" },
  configChunkWords: { tr: "Parça uzunluğu", en: "Chunk size" },
  configOverlap: { tr: "Parça örtüşmesi", en: "Chunk overlap" },
  corpusDocuments: { tr: "Belge", en: "Documents" },
  corpusChunks: { tr: "Parça", en: "Chunks" },

  // ------------------------------------------------------------------ eşik grafiği
  thresholdTitle: {
    tr: "Eşik kalibrasyonu — iki grup örtüşüyor",
    en: "Threshold calibration — the two groups overlap",
  },
  thresholdSubtitle: {
    tr: "Her nokta bir değerlendirme sorusunun en yüksek retrieval skoru. Üst şerit cevabı belgelerde OLAN sorular, alt şerit olmayanlar.",
    en: "Each dot is one evaluation question's top retrieval score. The upper strip is questions whose answer IS in the corpus, the lower strip those whose answer is not.",
  },
  axisLabel: {
    tr: "En yüksek retrieval skoru (kosinüs benzerliği)",
    en: "Top retrieval score (cosine similarity)",
  },
  groupAnswerable: { tr: "Cevaplanabilir", en: "Answerable" },
  groupOther: { tr: "Cevaplanamaz + kenar durum", en: "Unanswerable + edge case" },
  groupSummary: {
    tr: (count: number, lo: number, hi: number) =>
      `${count} soru · ${lo.toFixed(2)}–${hi.toFixed(2)}`,
    en: (count: number, lo: number, hi: number) =>
      `${count} questions · ${lo.toFixed(2)}–${hi.toFixed(2)}`,
  },
  overlapLabel: { tr: "örtüşme bölgesi", en: "overlap zone" },
  overlapRange: {
    tr: (lo: number, hi: number) => `${lo.toFixed(2)} – ${hi.toFixed(2)}`,
    en: (lo: number, hi: number) => `${lo.toFixed(2)} – ${hi.toFixed(2)}`,
  },
  overlapCounts: {
    tr: (answerable: number, other: number) =>
      `Bu bölgede ${answerable} cevaplanabilir ve ${other} cevaplanamaz soru var — aynı skor aralığında.`,
    en: (answerable: number, other: number) =>
      `${answerable} answerable and ${other} unanswerable questions land in this zone — the same score range.`,
  },
  noOverlapNote: {
    tr: "Bu veri kümesinde iki grubun skor aralıkları örtüşmüyor.",
    en: "In this dataset the two groups' score ranges do not overlap.",
  },
  activeThresholdLabel: { tr: "aktif eşik", en: "active threshold" },
  chartAria: {
    tr: (a: number, o: number) =>
      `Skor dağılımı: ${a} cevaplanabilir, ${o} cevaplanamaz soru. Sayısal karşılığı aşağıdaki eşik taraması tablosundadır.`,
    en: (a: number, o: number) =>
      `Score distribution: ${a} answerable, ${o} unanswerable questions. The numeric equivalent is in the threshold sweep table below.`,
  },
  dotTooltip: {
    tr: (group: string, score: number) => `${group} · ${score.toFixed(3)}`,
    en: (group: string, score: number) => `${group} · ${score.toFixed(3)}`,
  },

  // --- §6.4 anlatılması gereken içgörü ---
  insightTitle: {
    tr: "Tek bir eşik bu iki grubu ayıramaz",
    en: "No single threshold can separate these two groups",
  },
  insightBody: {
    tr: "Anlamsal benzerlik, cevabın orada olduğu anlamına gelmez. Korpusla aynı konuda ama cevabı belgelerde bulunmayan bir soru, cevabı olan bir sorudan daha yüksek skor alabiliyor. Grafikteki taralı alan tam olarak bunu gösteriyor: eşiği nereye koyarsanız koyun, ya cevaplanabilir soruları elersiniz ya da cevapsızları geçirirsiniz.",
    en: "Semantic similarity does not mean the answer is there. A question on the corpus's own topic whose answer is absent can score higher than one whose answer is present. The hatched band shows exactly that: wherever the threshold goes, it either rejects answerable questions or admits unanswerable ones.",
  },
  defenseTitle: { tr: "Bu yüzden savunma iki katmanlı", en: "Hence a two-layer defense" },
  defenseLayerOne: {
    tr: "Eşik, konu DIŞI soruyu LLM'e hiç göndermeden eler — ucuz, kesin ve yaklaşık on kat daha hızlı.",
    en: "The threshold rejects OFF-topic questions without ever calling the LLM — cheap, decisive and roughly ten times faster.",
  },
  defenseLayerTwo: {
    tr: "\"Konu yakın ama cevap yok\" kararını LLM'in kendisi verir; system prompt yalnızca verilen bağlamı kullanmasını ve bilmediğini söylemesini zorunlu kılar.",
    en: "The \"on topic but not answered\" call is made by the LLM itself; the system prompt requires it to use only the given context and to say when it does not know.",
  },
  defenseLayerOneTag: { tr: "1. katman · eşik", en: "Layer 1 · threshold" },
  defenseLayerTwoTag: { tr: "2. katman · LLM", en: "Layer 2 · LLM" },

  // --- Kalibrasyon hikâyesi (aşırı uydurma) ---
  calibrationTitle: {
    tr: "Eşik önce fazla yüksek seçilmişti",
    en: "The threshold was first set too high",
  },
  calibrationBody: {
    tr: "İlk eşik doğrudan değerlendirme setine bakarak seçildi. Setin cevaplanabilir sorularının hepsi rahatça geçiyordu, dolayısıyla eşiği yükseltmenin bedeli yok görünüyordu. Sonra set DIŞINDAN, cevabı bir belgede açıkça yazan bir soru soruldu ve reddedildi: eşik, on örneğin ifade biçimlerine aşırı uydurulmuştu (overfitting). Değerlendirme seti gerçek skor tabanını temsil etmiyordu.",
    en: "The first threshold was chosen by looking straight at the evaluation set. Every answerable question in the set cleared it comfortably, so raising it looked free. Then a question from OUTSIDE the set — one whose answer is stated plainly in a document — was rejected: the threshold had been overfitted to the phrasing of ten examples. The evaluation set was not the real score floor.",
  },
  calibrationEvidence: {
    tr: (headroom: number, active: number) =>
      `Aşağıdaki tabloda tuzağı görebilirsiniz: değerlendirme setinde eşiği ${headroom.toFixed(2)}'ye kadar yükseltseniz bile cevaplanabilir soruların tamamı geçmeye devam ediyor. Set bu yüzden yanıltıcı; eşik ${active.toFixed(2)}'e indirildi ve sonuç değişmedi, ama set dışı sorular için recall payı büyüdü.`,
    en: (headroom: number, active: number) =>
      `The trap is visible in the table below: on the evaluation set you could push the threshold up to ${headroom.toFixed(2)} and every answerable question would still pass. That is what makes the set misleading; the threshold was lowered to ${active.toFixed(2)} with no change in the result, but with far more headroom for questions outside the set.`,
  },
  calibrationTradeoff: {
    tr: "Yanlış negatif (cevabı olan soruyu reddetmek) kullanıcı için, zor bir soruyu LLM'e gönderip birkaç saniyede doğru şekilde reddettirmekten daha kötü. İkinci katman güvenilir çalıştığı için eşiği agresif tutmanın getirisi yok.",
    en: "A false negative — rejecting a question that does have an answer — is worse for the user than sending a hard question to the LLM and letting it refuse correctly a few seconds later. Since the second layer is reliable, an aggressive threshold buys nothing.",
  },

  // --- Eşik tarama tablosu ---
  sweepTitle: { tr: "Eşik taraması", en: "Threshold sweep" },
  sweepSubtitle: {
    tr: "Yukarıdaki dağılımın sayısal karşılığı: her eşikte kaç soru geçiyor.",
    en: "The numeric form of the distribution above: how many questions pass at each threshold.",
  },
  sweepColThreshold: { tr: "Eşik", en: "Threshold" },
  sweepColAnswerable: { tr: "Geçen cevaplanabilir", en: "Answerable passing" },
  sweepColOther: { tr: "Geçen cevaplanamaz", en: "Unanswerable passing" },
  sweepActiveRow: { tr: "aktif", en: "active" },
  sweepNote: {
    tr: "\"Cevaplanamaz\" grubunun eşiği geçmesi başarısızlık değildir: konu yakın sorularda reddetme kararını ikinci katman (LLM) verir. Eşiğin işi yalnızca konu DIŞI soruları elemektir.",
    en: "The unanswerable group passing the threshold is not a failure: for on-topic questions the refusal is made by the second layer (the LLM). The threshold's only job is to reject OFF-topic questions.",
  },

  // ------------------------------------------------------------------ model kıyası
  modelsTitle: { tr: "Model kıyası", en: "Model comparison" },
  modelsSubtitle: {
    tr: "Aynı değerlendirme seti, aynı korpus, aynı eşik — yalnızca sohbet modeli değişiyor.",
    en: "Same evaluation set, same corpus, same threshold — only the chat model changes.",
  },
  modelActiveBadge: { tr: "aktif", en: "active" },
  modelSingleNote: {
    tr: "Sonuç dosyasında tek bir model çalıştırması var. Kıyas için ikinci bir modelle eval'i tekrar çalıştırıp sonucu aynı dosyaya eklemek gerekir — ölçülmemiş bir kıyas burada gösterilmez.",
    en: "The results file contains a single model run. A comparison requires running the evaluation again with a second model and appending it to the same file — an unmeasured comparison is not shown here.",
  },
  modelIdLabel: { tr: "Model kimliği", en: "Model id" },
  modelPassedLabel: { tr: "Geçen", en: "Passed" },
  modelAvgLabel: { tr: "Ortalama süre", en: "Average latency" },
  modelRetrievalLabel: { tr: "Retrieval", en: "Retrieval" },
  modelRetrievalShared: {
    tr: "Retrieval sohbet modelinden bağımsızdır; bu satır modeller arasında aynı kalmalıdır.",
    en: "Retrieval is independent of the chat model; this row should be identical across models.",
  },

  // ------------------------------------------------------------------ soru tablosu
  evalTitle: { tr: "Soru bazında sonuçlar", en: "Per-question results" },
  evalSubtitle: {
    tr: "Değerlendirme setindeki her sorunun sonucu, süresi ve üretilen cevap.",
    en: "Every question in the evaluation set with its outcome, latency and generated answer.",
  },
  filterLabel: { tr: "Kategori", en: "Category" },
  modelFilterLabel: { tr: "Model", en: "Model" },
  categoryAll: { tr: "Tümü", en: "All" },
  categoryAnswerable: { tr: "Cevaplanabilir", en: "Answerable" },
  categoryUnanswerable: { tr: "Cevaplanamaz", en: "Unanswerable" },
  categoryEdgeCase: { tr: "Kenar durum", en: "Edge case" },
  colId: { tr: "No", en: "ID" },
  colCategory: { tr: "Kategori", en: "Category" },
  colStatus: { tr: "Sonuç", en: "Outcome" },
  colSeconds: { tr: "Süre", en: "Time" },
  colSource: { tr: "Beklenen kaynak", en: "Expected source" },
  colKeywords: { tr: "Anahtar kelime", en: "Keywords" },
  colAnswer: { tr: "Cevap", en: "Answer" },
  statusPassed: { tr: "Geçti", en: "Passed" },
  statusFailed: { tr: "Kaldı", en: "Failed" },
  sourceFound: { tr: "bulundu", en: "found" },
  sourceMissing: { tr: "bulunamadı", en: "not found" },
  notApplicable: { tr: "—", en: "—" },
  notApplicableAria: {
    tr: "Bu kategori için ölçülmüyor",
    en: "Not measured for this category",
  },
  keywordsValue: {
    tr: (matched: number, total: number) => `${matched}/${total}`,
    en: (matched: number, total: number) => `${matched}/${total}`,
  },
  keywordsFootnote: {
    tr: "Anahtar kelime metriği kasıtlı olarak gevşek raporlar: eşleşme küçük/büyük harf duyarsız bir kök aramasıdır, cevap tamamen doğruyken de eksik görünebilir (belgelerde sayılar yazıyla geçiyor, çekim ekleri değişiyor). Eksik eşleşme başarısızlık DEĞİLDİR — \"Sonuç\" sütunu bağlayıcıdır. Metrik gevşetilmedi çünkü sıkı ölçüp yorumlamak, gevşek ölçüp iyi görünmekten dürüst.",
    en: "The keyword metric deliberately under-reports: matching is a case-insensitive stem search, so it can look incomplete while the answer is entirely correct (documents spell numbers out, Turkish inflects word endings). A partial match is NOT a failure — the \"Outcome\" column is authoritative. The metric was left strict on purpose: measuring strictly and interpreting honestly beats measuring loosely and looking good.",
  },
  expandAnswer: { tr: "Tam cevabı göster", en: "Show full answer" },
  collapseAnswer: { tr: "Cevabı kısalt", en: "Collapse answer" },
  emptyAnswer: { tr: "(boş cevap)", en: "(empty answer)" },
  filterEmpty: {
    tr: "Bu kategoride soru yok.",
    en: "No questions in this category.",
  },
  rowCount: {
    tr: (shown: number, total: number) => `${shown} / ${total} soru`,
    en: (shown: number, total: number) => `${shown} / ${total} questions`,
  },

  // ------------------------------------------------------------------ ortak biçimlendirme
  ratio: {
    tr: (a: number, b: number) => `${a}/${b}`,
    en: (a: number, b: number) => `${a}/${b}`,
  },
  seconds: {
    tr: (v: number) => `${v.toFixed(1)} sn`,
    en: (v: number) => `${v.toFixed(1)} s`,
  },
  secondsShort: {
    tr: (v: number) => `${v.toFixed(1)}sn`,
    en: (v: number) => `${v.toFixed(1)}s`,
  },
  words: {
    tr: (n: number) => `${n} kelime`,
    en: (n: number) => `${n} words`,
  },
  percent: {
    tr: (v: number) => `%${Math.round(v)}`,
    en: (v: number) => `${Math.round(v)}%`,
  },
  score: {
    tr: (v: number) => v.toFixed(2),
    en: (v: number) => v.toFixed(2),
  },
} as const satisfies Namespace
