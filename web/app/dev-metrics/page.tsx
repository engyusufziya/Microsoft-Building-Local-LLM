"use client"

/**
 * GEÇİCİ doğrulama sayfası — `metrics-ui` çıktısını backend ve Foundry Local
 * olmadan görsel olarak kontrol etmek için. `app/page.tsx`'e dokunulmadı.
 *
 * `web/app/_dev-metrics` DEĞİL `dev-metrics`: Next.js 16'da `_` önekli
 * klasörler "private folder" sayılıp routing dışına çıkarılıyor
 * (node_modules/next/dist/docs/01-app/01-getting-started/
 * 02-project-structure.md, "Private folders").
 *
 * BURADAKİ SAYILAR SAHTEDİR ve yalnızca bu dosyada durur. Bileşenlerin
 * hiçbirinde gömülü sayı yoktur; hepsi `MetricsResponse`'tan gelir
 * (FEATURE_SPEC §6.3). Şema §6.2 ile birebir; eşik/skor aralıkları
 * `rag/config.py`'deki gerçek kalibrasyon ölçümleriyle aynı büyüklükte
 * tutuldu ki yerleşim gerçekçi bir veriyle sınansın.
 */

import * as React from "react"

import { ApiRequestError } from "@/lib/api"
import { LanguageProvider, useLocale } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { useT } from "@/lib/i18n"
import type {
  MetricsQuestionResult,
  MetricsResponse,
  MetricsThresholdSweepRow,
} from "@/lib/types"
import { ThemeProvider } from "@/components/theme-provider"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { MetricsPage } from "@/components/metrics"

// --------------------------------------------------------------------------- sahte veri

const ANSWERABLE_SCORES = [
  0.7828, 0.729, 0.6513, 0.841, 0.7015, 0.6842, 0.7466, 0.6907, 0.7183, 0.662,
]
const OTHER_SCORES = [0.7359, 0.5068, 0.741, 0.4291]
const SWEEP_THRESHOLDS = [0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]

/** Tarama tablosu skorlardan türetilir — elle yazılan satır tutarsızlık üretirdi. */
function buildSweepTable(): MetricsThresholdSweepRow[] {
  return SWEEP_THRESHOLDS.map((threshold) => ({
    threshold,
    answerable_passed: ANSWERABLE_SCORES.filter((s) => s >= threshold).length,
    answerable_total: ANSWERABLE_SCORES.length,
    other_passed: OTHER_SCORES.filter((s) => s >= threshold).length,
    other_total: OTHER_SCORES.length,
  }))
}

const QWEN_QUESTIONS: MetricsQuestionResult[] = [
  {
    id: "Q01",
    category: "answerable",
    passed: true,
    seconds: 24.1,
    expected_source: "belge_01_rag_nedir.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 3,
    answer:
      "RAG üç adımdan oluşur. Birinci adım retrieval: kullanıcının sorusuyla ilgili belge parçaları getirilir. İkinci adım augmentation: getirilen parçalar soruyla birlikte modele verilen bağlama eklenir. Üçüncü adım generation: model yalnızca bu bağlamı kullanarak cevabı üretir. [Kaynak: belge_01_rag_nedir.md]",
  },
  {
    id: "Q02",
    category: "answerable",
    passed: true,
    seconds: 6.4,
    expected_source: "belge_01_rag_nedir.md",
    source_found: true,
    keywords_matched: 2,
    keywords_total: 3,
    answer:
      "Bağlam dışarıdan getirildiği için model kendi eğitim belleğinden tahmin yürütmek zorunda kalmaz; bu da halüsinasyon riskini azaltır ve cevapların kaynak gösterilebilir olmasını sağlar.",
  },
  {
    id: "Q03",
    category: "answerable",
    passed: true,
    seconds: 5.9,
    expected_source: "belge_02_embedding_ve_benzerlik.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 3,
    answer:
      "Cosine similarity iki vektör arasındaki açıyı ölçer, vektörlerin büyüklüğünü değil. Değeri 1'e yaklaştıkça benzerlik artar, 0'a yaklaştıkça azalır.",
  },
  {
    id: "Q04",
    category: "answerable",
    passed: true,
    seconds: 8.2,
    expected_source: "belge_02_embedding_ve_benzerlik.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 4,
    answer:
      "Benzer anlama gelen metinler embedding uzayında birbirine yakın vektörler üretir; \"araba\" ve \"otomobil\" bu yüzden yakın çıkar. RAG'de kullanıcının sorusu da bir vektöre çevrilir ve bu yakınlık üzerinden en benzer metin parçaları bulunur.",
  },
  {
    id: "Q05",
    category: "answerable",
    passed: true,
    seconds: 4.1,
    expected_source: "belge_03_foundry_local.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 3,
    answer:
      "Foundry Local kullanılabilir donanımı (CPU, GPU veya NPU) otomatik olarak tespit eder ve en uygun model sürümünü seçer.",
  },
  {
    id: "Q06",
    category: "answerable",
    passed: true,
    seconds: 7.8,
    expected_source: "belge_03_foundry_local.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 4,
    answer:
      "Apple Silicon işlemcili Mac'lerde Foundry Local, Metal aracılığıyla GPU hızlandırması sunar. Ayrıca hem sohbet hem embedding modellerini desteklediği için yerel bir RAG sisteminin her iki bileşeni için de tek başına yeterlidir.",
  },
  {
    id: "Q07",
    category: "answerable",
    passed: true,
    seconds: 5.2,
    expected_source: "belge_04_sqlite_veri_saklama.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 3,
    answer:
      "Embedding vektörleri sayısal listeler olduğu için SQLite'a doğrudan yazılamaz. Vektör JSON formatında bir metne çevrilerek saklanır, okunurken tekrar sayısal listeye dönüştürülür.",
  },
  {
    id: "Q08",
    category: "answerable",
    passed: true,
    seconds: 4.6,
    expected_source: "belge_04_sqlite_veri_saklama.md",
    source_found: true,
    keywords_matched: 4,
    keywords_total: 4,
    answer:
      "Her satır bir belge parçasını temsil eder: benzersiz kimlik (id), kaynak belgenin adı (source), metnin kendisi (content) ve metnin embedding vektörü.",
  },
  {
    id: "Q09",
    category: "answerable",
    passed: true,
    seconds: 9.1,
    expected_source: "belge_05_prompt_engineering.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 4,
    answer:
      "Sistem mesajı modele nasıl davranacağını söyler; örneğin sadece verilen bağlamı kullanmasını ve bilgi yoksa bilmediğini söylemesini ister. Konudan sapmayı önlemek için üretim uzunluğunu sınırlamak da (örneğin en fazla üç cümle istemek) yardımcı olur.",
  },
  {
    id: "Q10",
    category: "answerable",
    passed: true,
    seconds: 6.7,
    expected_source: "belge_06_chunking_stratejisi.md",
    source_found: true,
    keywords_matched: 3,
    keywords_total: 4,
    answer:
      "Belgeleri paragraf sınırlarında bölmek ve her parçayı yaklaşık iki yüz ila dört yüz kelime uzunluğunda tutmak önerilir. Parçalar arasında bir paragraflık örtüşme bırakmak, bir cümlenin iki parça arasında bölünüp bağlamını kaybetmesini önler.",
  },
  {
    id: "Q11",
    category: "unanswerable",
    passed: true,
    seconds: 5.4,
    expected_source: null,
    source_found: null,
    keywords_matched: null,
    keywords_total: null,
    answer: "Bu bilgi yüklediğiniz belgelerde yok.",
  },
  {
    id: "Q12",
    category: "unanswerable",
    passed: true,
    seconds: 4.9,
    expected_source: null,
    source_found: null,
    keywords_matched: null,
    keywords_total: null,
    answer: "Bu bilgi yüklediğiniz belgelerde yok.",
  },
  {
    id: "Q13",
    category: "unanswerable",
    passed: true,
    seconds: 5.1,
    expected_source: null,
    source_found: null,
    keywords_matched: null,
    keywords_total: null,
    answer: "Bu bilgi yüklediğiniz belgelerde yok.",
  },
  {
    id: "Q14",
    category: "edge_case",
    passed: true,
    seconds: 0.1,
    expected_source: null,
    source_found: null,
    keywords_matched: null,
    keywords_total: null,
    answer: "Lütfen bir soru yazın.",
  },
  {
    id: "Q15",
    category: "edge_case",
    passed: true,
    seconds: 1.4,
    expected_source: null,
    source_found: null,
    keywords_matched: null,
    keywords_total: null,
    answer:
      "Sorunuzu biraz daraltabilir misiniz? Belgeler RAG'in adımlarını, embedding ve benzerlik hesabını, Foundry Local'ı, SQLite'ta saklamayı, prompt tasarımını ve chunking stratejisini kapsıyor.",
  },
]

/** Kıyas kartını doldurmak için türetilmiş ikinci model (yine SAHTE veri). */
const PHI_QUESTIONS: MetricsQuestionResult[] = QWEN_QUESTIONS.map((question, index) => {
  const failed = index === 3 || index === 8 || index === 10 || index === 12
  return {
    ...question,
    passed: !failed,
    seconds: Math.round(question.seconds * 0.58 * 10) / 10,
    source_found: question.source_found,
    keywords_matched:
      question.keywords_total === null
        ? null
        : Math.max(0, (question.keywords_matched ?? 0) - (failed ? 2 : 0)),
    answer: failed
      ? "Belgelerde bu konuda genel bilgiler var, ancak sorunun tam karşılığı verilmemiş; yine de tahmin edilebilir bir cevap şöyle olabilir…"
      : question.answer,
  }
})

const MOCK_METRICS: MetricsResponse = {
  generated_at: "2026-08-13T15:00:00+03:00",
  config: {
    min_score: 0.45,
    top_k: 4,
    chunk_words: 130,
    chunk_overlap_words: 30,
  },
  corpus: { chunk_count: 17, document_count: 6 },
  models: [
    {
      alias: "qwen2.5-7b",
      model_id: "qwen2.5-7b-instruct-generic-gpu:4",
      is_active: true,
      summary: {
        passed: 15,
        total: 15,
        by_category: {
          answerable: [10, 10],
          unanswerable: [3, 3],
          edge_case: [2, 2],
        },
        retrieval_hits: [10, 10],
        avg_seconds: 6.6,
      },
      questions: QWEN_QUESTIONS,
    },
    {
      alias: "phi-4-mini",
      model_id: "phi-4-mini-instruct-generic-gpu:1",
      is_active: false,
      summary: {
        passed: 11,
        total: 15,
        by_category: {
          answerable: [8, 10],
          unanswerable: [1, 3],
          edge_case: [2, 2],
        },
        retrieval_hits: [10, 10],
        avg_seconds: 3.9,
      },
      questions: PHI_QUESTIONS,
    },
  ],
  threshold_sweep: {
    answerable_scores: ANSWERABLE_SCORES,
    other_scores: OTHER_SCORES,
    table: buildSweepTable(),
  },
}

const SINGLE_MODEL_METRICS: MetricsResponse = {
  ...MOCK_METRICS,
  models: MOCK_METRICS.models.slice(0, 1),
}

// --------------------------------------------------------------------------- yükleyiciler
// Modül düzeyinde tanımlı: MetricsPage'in `load` prop'u kararlı bir referans
// bekliyor (her render'da yeni kapanış geçilirse effect döngüye girer).

const loadReady = () => Promise.resolve(MOCK_METRICS)
const loadSingleModel = () => Promise.resolve(SINGLE_MODEL_METRICS)
const loadNotGenerated = () =>
  Promise.reject(
    new ApiRequestError(503, {
      code: "METRICS_NOT_GENERATED",
      message: "Değerlendirme sonuçları henüz üretilmedi.",
    })
  )
const loadFailure = () =>
  Promise.reject(
    new ApiRequestError(500, {
      code: "INTERNAL",
      message: "eval/results.json okunamadı: beklenmeyen bir hata oluştu.",
    })
  )
const loadPending = () => new Promise<MetricsResponse>(() => {})

const SCENARIOS = [
  { key: "ready", label: "Dolu (2 model)", load: loadReady },
  { key: "single", label: "Tek model", load: loadSingleModel },
  { key: "not-generated", label: "METRICS_NOT_GENERATED", load: loadNotGenerated },
  { key: "error", label: "Hata", load: loadFailure },
  { key: "loading", label: "Yükleniyor", load: loadPending },
] as const

type ScenarioKey = (typeof SCENARIOS)[number]["key"]

/**
 * Başlangıç senaryosu ve dili URL'den okunabilir (`?state=error&lang=en`),
 * böylece her durum tek tek tıklanmadan da açılabilir/kaydedilebilir.
 *
 * `useSyncExternalStore` deseni bilinçli: statik export'ta HTML önceden
 * üretildiği için `window`'u render sırasında doğrudan okumak hydration
 * uyuşmazlığı yaratırdı, effect içinde setState ise bu projenin lint
 * kuralına (react-hooks/set-state-in-effect) takılırdı. Aynı çözüm
 * components/theme-toggle.tsx'te de kullanılıyor.
 */
const emptySubscribe = () => () => {}

function readParam(name: string): string | null {
  if (typeof window === "undefined") return null
  return new URLSearchParams(window.location.search).get(name)
}

function useInitialScenario(): ScenarioKey {
  return React.useSyncExternalStore(
    emptySubscribe,
    () => {
      const value = readParam("state")
      return SCENARIOS.some((s) => s.key === value)
        ? (value as ScenarioKey)
        : "ready"
    },
    () => "ready" as ScenarioKey
  )
}

/**
 * Dil tercihi React başlamadan ÖNCE yazılır.
 *
 * `LanguageProvider` aktif dili modül düzeyinde bir kez önbelleğe alıyor ve
 * önce localStorage'a bakıyor (lib/i18n/index.ts). `defaultLocale` prop'unu
 * hydration'dan sonra değiştirmek bu yüzden etkisiz kalır; tercihi doğrudan
 * depoya yazmak önizlemede dili gerçekten değiştiren tek yol. Yalnızca bu
 * geçici sayfaya ait bir kolaylık.
 */
if (typeof window !== "undefined") {
  const lang = new URLSearchParams(window.location.search).get("lang")
  if (lang === "tr" || lang === "en") {
    window.localStorage.setItem("rag-assistant:locale", lang)
  }
}

// --------------------------------------------------------------------------- sayfa

function LocaleSwitcher() {
  const { locale, setLocale } = useLocale()
  const t = useT(common)
  return (
    <div className="flex items-center gap-2">
      <span className="text-caption font-medium text-muted-foreground">
        {t.languageLabel}
      </span>
      <Button
        variant={locale === "tr" ? "default" : "outline"}
        size="xs"
        onClick={() => setLocale("tr")}
      >
        TR
      </Button>
      <Button
        variant={locale === "en" ? "default" : "outline"}
        size="xs"
        onClick={() => setLocale("en")}
      >
        EN
      </Button>
    </div>
  )
}

function PreviewBody() {
  const initialScenario = useInitialScenario()
  const [override, setOverride] = React.useState<ScenarioKey | null>(null)
  const scenario = override ?? initialScenario
  const setScenario = setOverride
  const active = SCENARIOS.find((s) => s.key === scenario) ?? SCENARIOS[0]

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <div className="sticky top-0 z-20 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-surface-raised px-6 py-3">
        <span className="text-caption font-medium text-muted-foreground">Durum</span>
        {SCENARIOS.map((s) => (
          <Button
            key={s.key}
            size="xs"
            variant={s.key === scenario ? "default" : "outline"}
            onClick={() => setScenario(s.key)}
          >
            {s.label}
          </Button>
        ))}
        <Separator orientation="vertical" className="hidden h-6 sm:block" />
        <LocaleSwitcher />
        <ThemeToggle />
      </div>

      {/* key: senaryo değişince MetricsPage'in durumu sıfırdan kurulsun. */}
      <MetricsPage key={active.key} load={active.load} />
    </div>
  )
}

export default function DevMetricsPage() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <PreviewBody />
      </LanguageProvider>
    </ThemeProvider>
  )
}
