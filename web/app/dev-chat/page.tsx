"use client"

/**
 * GEÇİCİ doğrulama sayfası — sohbet akışını ve Retrieval Inspector'ı backend
 * ve Foundry Local ÇALIŞTIRMADAN doğrulamak için. `app/page.tsx`'e
 * dokunulmadı.
 *
 * Klasör adı `_dev-chat` DEĞİL `dev-chat`: Next.js 16'da `_` önekli klasörler
 * "private folder" sayılıp routing'den tamamen çıkarılıyor
 * (node_modules/next/dist/docs/01-app/01-getting-started/
 * 02-project-structure.md), o isimle sayfa hiç erişilebilir olmazdı.
 *
 * Nasıl çalışır: `setChatTransport()` ile gerçek `streamChat` yerine
 * SAHTE BİR OLAY DİZİSİ takılır. Olay nesneleri `lib/types.ts` içindeki
 * `ChatRetrievalEvent` / `ChatTokenEvent` / `ChatDoneEvent` tipleridir —
 * yani SSE çerçevelerinin `data:` yükleriyle birebir aynı şey
 * (docs/FEATURE_SPEC.md §3.1). Zamanlamalar da ölçülen değerlerden:
 * retrieval ~0.3 sn, ilk token ~0.74 sn (TTFT).
 *
 * Bu dosyadaki senaryo etiketleri i18n'e girmez: ürün yüzeyi değil, geçici
 * bir test koşum tahtasıdır.
 */

import * as React from "react"

import { ApiRequestError, type ChatCallbacks } from "@/lib/api"
import type { ChunkHit } from "@/lib/types"
import { LanguageProvider, useLocale } from "@/lib/i18n"
import { ThemeProvider } from "@/components/theme-provider"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { ChatPanel, chatActions, setChatTransport, type ChatTransport } from "@/components/chat"
import { RetrievalInspector } from "@/components/inspector"

// --------------------------------------------------------------------------- fixtures

/** Gerçek eşik `/api/health`'ten gelir; burada SAHTE olayın alanı olarak taşınır. */
const THRESHOLD = 0.45

function hit(
  score: number,
  source: string,
  page: number,
  content: string,
  viaOcr = false
): ChunkHit {
  return {
    score,
    source,
    page,
    content,
    via_ocr: viaOcr,
    citation: page > 0 ? `[Kaynak: ${source} s.${page}]` : `[Kaynak: ${source}]`,
    passed_threshold: score >= THRESHOLD,
  }
}

const LOREM =
  "RAG üç adımdan oluşur: kullanıcının sorusu bir vektöre çevrilir, vektör veritabanında en benzer bölümler aranır ve bulunan bölümler bağlam olarak dil modeline verilir. Bu sayede model yalnızca verilen belgelerdeki bilgiye dayanarak cevap üretir ve kaynak gösterilebilir hale gelir."

/** Skora göre AZALAN — backend de böyle gönderiyor (§4.3 sıralama varsayımı). */
const MIXED_HITS: ChunkHit[] = [
  hit(0.7828, "belge_01_rag_nedir.md", 0, LOREM),
  hit(0.729, "belge_02_embedding_ve_benzerlik.md", 0, LOREM.slice(0, 180)),
  hit(
    0.6104,
    "cok-uzun-bir-dosya-adi-ortadan-kisaltilmali-2026-rapor.pdf",
    4,
    "Taranmış sayfadan OCR ile okunan metin örneği. " + LOREM.slice(0, 140),
    true
  ),
  hit(0.4312, "belge_05_prompt_engineering.md", 0, LOREM.slice(0, 120)),
]

const ALL_REJECTED_HITS: ChunkHit[] = [
  hit(0.4312, "belge_03_foundry_local.md", 0, LOREM.slice(0, 160)),
  hit(0.3907, "belge_04_sqlite_veri_saklama.md", 2, LOREM.slice(0, 140)),
  hit(0.3555, "belge_06_chunking_stratejisi.md", 0, LOREM.slice(0, 120)),
]

const ALL_PASSED_HITS: ChunkHit[] = [
  hit(0.8321, "belge_01_rag_nedir.md", 0, LOREM),
  hit(0.7104, "belge_02_embedding_ve_benzerlik.md", 3, LOREM.slice(0, 160)),
]

const MARKDOWN_ANSWER = `RAG üç adımdan oluşur:

1. Soru bir **vektöre** çevrilir.
2. En benzer bölümler aranır.
3. Bulunan bölümler bağlam olarak modele verilir.

| Aşama | Süre |
| --- | --- |
| Retrieval | 0.31 sn |
| İlk token | 0.74 sn |

\`\`\`python
hits = get_top_chunks(query, min_score=config.MIN_SCORE)
\`\`\`

Kısa cevap: \`min_score\` unutulursa eleme hiç yapılmaz.`

/** Motorun system prompt'una gömülü ham TÜRKÇE ret metni (config.NO_ANSWER_TEXT). */
const RAW_REFUSAL = "Bu bilgi yüklediğiniz belgelerde yok."

// --------------------------------------------------------------------------- sahte transport

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Metni ~2-3 kelimelik parçalara böler; gerçek token akışına yakın. */
function tokenize(text: string): string[] {
  return text.match(/\S+\s*/g)?.reduce<string[]>((chunks, word, index) => {
    if (index % 3 === 0) chunks.push(word)
    else chunks[chunks.length - 1] += word
    return chunks
  }, []) ?? []
}

type ScenarioKey =
  | "answered"
  | "belowThreshold"
  | "llmRefused"
  | "allPassed"
  | "midStreamError"
  | "requestError"

const SCENARIOS: Array<{ key: ScenarioKey; label: string; question: string }> = [
  { key: "answered", label: "1 · reason: null", question: "RAG kaç adımdan oluşur?" },
  {
    key: "belowThreshold",
    label: "2 · below_threshold",
    question: "İstanbul'un nüfusu kaçtır?",
  },
  {
    key: "llmRefused",
    label: "3 · llm_refused",
    question: "Chunk boyutunun maliyeti kaç dolar?",
  },
  { key: "allPassed", label: "4 · eşik çizgisi yok", question: "Embedding nedir?" },
  {
    key: "midStreamError",
    label: "5 · akış ortasında hata",
    question: "Foundry Local nedir?",
  },
  { key: "requestError", label: "6 · istek hatası", question: "Modeller hazır mı?" },
]

let activeScenario: ScenarioKey = "answered"

const fakeTransport: ChatTransport = async (
  _question: string,
  callbacks: ChatCallbacks
) => {
  const scenario = activeScenario

  if (scenario === "requestError") {
    await sleep(200)
    // streamChat, HTTP hata gövdesini ApiRequestError olarak FIRLATIR.
    throw new ApiRequestError(503, {
      code: "MODEL_WARMING",
      message: "Modeller henüz yüklenmedi.",
    })
  }

  // --- event: retrieval (HER ZAMAN ilk olay, ~0.3 sn) ---
  await sleep(300)
  const hits =
    scenario === "belowThreshold"
      ? ALL_REJECTED_HITS
      : scenario === "allPassed"
        ? ALL_PASSED_HITS
        : MIXED_HITS
  const passed = hits.filter((h) => h.passed_threshold)
  callbacks.onRetrieval?.({
    hits,
    threshold: THRESHOLD,
    passed_count: passed.length,
    rejected_count: hits.length - passed.length,
    elapsed_ms: 312,
  })

  // --- kısa devre: hiç token akmaz (~0.1 sn) ---
  if (scenario === "belowThreshold") {
    await sleep(100)
    callbacks.onDone?.({
      answered: false,
      reason: "below_threshold",
      sources: [],
      elapsed_ms: 412,
      token_count: 0,
    })
    return
  }

  // --- event: token* (ilk token ~0.74 sn) ---
  await sleep(440)
  const answer = scenario === "llmRefused" ? RAW_REFUSAL : MARKDOWN_ANSWER
  const tokens = tokenize(answer)
  const cutoff =
    scenario === "midStreamError" ? Math.floor(tokens.length / 3) : tokens.length

  for (let index = 0; index < cutoff; index += 1) {
    callbacks.onToken?.({ text: tokens[index] })
    await sleep(25)
  }

  if (scenario === "midStreamError") {
    callbacks.onError?.({ code: "INTERNAL", message: "Bağlantı beklenmedik şekilde kapandı." })
    return
  }

  // --- event: done ---
  callbacks.onDone?.(
    scenario === "llmRefused"
      ? {
          answered: false,
          reason: "llm_refused",
          sources: [],
          elapsed_ms: 2140,
          token_count: tokens.length,
        }
      : {
          answered: true,
          reason: null,
          sources: passed.map((h) => h.citation),
          elapsed_ms: 3090,
          token_count: tokens.length,
        }
  )
}

// --------------------------------------------------------------------------- sayfa

type LockChoice = "none" | "warming" | "uploading" | "noDocuments" | "modelError"

const LOCKS: Array<{ key: LockChoice; label: string }> = [
  { key: "none", label: "kilit yok" },
  { key: "warming", label: "warming" },
  { key: "uploading", label: "yükleme" },
  { key: "noDocuments", label: "belge yok" },
  { key: "modelError", label: "model hatası" },
]

function LocaleSwitcher() {
  const { locale, setLocale } = useLocale()
  return (
    <div className="flex items-center gap-1">
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

function Harness() {
  const [lock, setLock] = React.useState<LockChoice>("none")
  // Mobil/tablet: Inspector kalıcı kolon değil, drawer (DESIGN_SYSTEM.md §4).
  // Gerçek drawer'ı kabuk agent'ı kuracak; burada yalnızca sözleşmenin
  // (onOpenInspector prop'u) çalıştığını doğruluyoruz.
  const [drawerOpen, setDrawerOpen] = React.useState(false)

  // Sahte akış YALNIZCA bu sayfa monteliyken geçerli; ayrılırken gerçek
  // `streamChat` geri gelir (istemci tarafı gezinmede sızmasın diye).
  React.useEffect(() => {
    setChatTransport(fakeTransport)
    return () => {
      setChatTransport(null)
      chatActions.reset()
    }
  }, [])

  return (
    <div className="flex h-dvh min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-surface px-4 py-2">
        <span className="text-caption font-medium text-text-secondary">
          dev-chat · sahte SSE
        </span>

        <div className="flex flex-wrap items-center gap-1">
          {SCENARIOS.map((scenario) => (
            <Button
              key={scenario.key}
              variant="outline"
              size="xs"
              onClick={() => {
                activeScenario = scenario.key
                chatActions.ask(scenario.question)
              }}
            >
              {scenario.label}
            </Button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1">
          {LOCKS.map((choice) => (
            <Button
              key={choice.key}
              variant={lock === choice.key ? "secondary" : "ghost"}
              size="xs"
              onClick={() => setLock(choice.key)}
            >
              {choice.label}
            </Button>
          ))}
        </div>

        <Button variant="ghost" size="xs" onClick={() => chatActions.reset()}>
          sıfırla
        </Button>

        <div className="ml-auto flex items-center gap-2">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1">
          <ChatPanel
            lock={lock === "none" ? null : lock}
            documentCount={lock === "noDocuments" ? 0 : 6}
            onOpenInspector={() => setDrawerOpen(true)}
          />
        </div>
        <div className="hidden w-[380px] shrink-0 border-l border-border xl:block">
          <RetrievalInspector />
        </div>
      </div>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="right" className="w-full p-0 sm:max-w-[380px]">
          <SheetTitle className="sr-only">Retrieval Inspector</SheetTitle>
          <RetrievalInspector className="pt-6" />
        </SheetContent>
      </Sheet>
    </div>
  )
}

export default function DevChatPage() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <Harness />
      </LanguageProvider>
    </ThemeProvider>
  )
}
