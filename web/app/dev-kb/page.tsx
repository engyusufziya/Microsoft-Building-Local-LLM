"use client"

/**
 * GEÇİCİ doğrulama sayfası — `frontend-kb` çıktısını (AppShell + sidebar)
 * backend ve Foundry Local modelleri OLMADAN çalıştırmak için. app/page.tsx
 * entegrasyonun dosyası, ona dokunulmadı.
 *
 * Klasör adı `dev-kb` (alt çizgisiz): Next.js 16'da `_` önekli klasörler
 * "private folder" sayılıp routing'den çıkarılıyor
 * (node_modules/next/dist/docs/01-app/01-getting-started/
 * 02-project-structure.md) — `_dev-kb` ile sayfa hiç erişilebilir olmazdı.
 *
 * Sahte kaynak (`KnowledgeSource`) gerçek `lib/api.ts` ile aynı arayüzü
 * uygular; bileşenler üretimdeki kod yollarının aynısını çalıştırır.
 */

import * as React from "react"

import { ThemeProvider } from "@/components/theme-provider"
import { ThemeToggle } from "@/components/theme-toggle"
import { LanguageProvider, useLocale, useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { UploadCallbacks } from "@/lib/api"
import type { DeleteResponse, DocumentInfo, HealthResponse } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AppShell } from "@/components/shell/app-shell"
import { useAppShell } from "@/components/shell/app-shell-context"
import { useBreakpoint } from "@/components/shell/use-breakpoint"
import { KnowledgeSidebar } from "@/components/sidebar/knowledge-sidebar"
import type { KnowledgeSource } from "@/components/sidebar/knowledge-source"
import { useKnowledge } from "@/components/sidebar/use-knowledge"

type Scenario = "ready" | "empty" | "warming" | "offline"

const SCENARIOS: Scenario[] = ["ready", "empty", "warming", "offline"]

const SAMPLE_DOCUMENTS: DocumentInfo[] = [
  {
    filename: "foundry_local_plan.pdf",
    page_count: 13,
    chunk_count: 41,
    ingested_at: "2026-08-13T10:24:00",
    has_ocr_chunks: false,
  },
  {
    filename: "taranmis_teknik_sartname_2026_revizyon_final.pdf",
    page_count: 27,
    chunk_count: 96,
    ingested_at: "2026-08-12T18:05:00",
    has_ocr_chunks: true,
  },
  {
    filename: "belge_01_rag_nedir.md",
    page_count: 1,
    chunk_count: 3,
    ingested_at: "2026-08-11T09:40:00",
    has_ocr_chunks: false,
  },
]

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function offline(): never {
  // `fetch` ağ hatasında TypeError atar — `toFailure()` bunu "network"
  // olarak sınıflar (bkz. components/sidebar/error-messages.ts).
  throw new TypeError("dev-kb: sunucuya ulaşılamadı (sahte)")
}

/**
 * Sahte backend. Yükleme ilerlemesi motorun ÜRETTİĞİ ham Türkçe aşama
 * metinleriyle yayılır (rag/ingest.py) — böylece `localizeUploadStage()`
 * eşlemesi de gerçek girdiyle doğrulanmış olur.
 */
function createMockSource(scenario: Scenario): KnowledgeSource {
  let documents: DocumentInfo[] =
    scenario === "empty" ? [] : SAMPLE_DOCUMENTS.map((doc) => ({ ...doc }))

  return {
    listDocuments: async () => {
      await delay(500)
      if (scenario === "offline") offline()
      return documents.map((doc) => ({ ...doc }))
    },

    deleteDocument: async (filename: string): Promise<DeleteResponse> => {
      await delay(400)
      if (scenario === "offline") offline()
      documents = documents.filter((doc) => doc.filename !== filename)
      return { deleted: true }
    },

    getHealth: async (): Promise<HealthResponse> => {
      await delay(250)
      if (scenario === "offline") offline()
      return {
        status: scenario === "warming" ? "warming" : "ready",
        chat_model: "qwen2.5-7b",
        embedding_model: "qwen3-embedding-0.6b",
        min_score: 0.45,
        top_k: 4,
        document_count: documents.length,
        chunk_count: documents.reduce((sum, doc) => sum + doc.chunk_count, 0),
        ocr_available: true,
      }
    },

    uploadDocument: async (file: File, callbacks: UploadCallbacks) => {
      const name = file.name.toLowerCase()

      await delay(500)
      callbacks.onProgress?.({ pct: 0, stage: `${file.name} okunuyor...` })

      if (name.includes("bozuk")) {
        await delay(500)
        callbacks.onError?.({
          code: "INVALID_PDF",
          message: "pypdf dosyayı açamadı (sahte).",
        })
        return
      }
      if (name.includes("bos")) {
        await delay(500)
        callbacks.onError?.({
          code: "NO_CONTENT",
          message: "Hiç chunk çıkmadı (sahte).",
        })
        return
      }

      const total = 12
      await delay(400)
      callbacks.onProgress?.({
        pct: 0,
        stage: `${total} chunk embed ediliyor...`,
      })
      for (let done = 4; done <= total; done += 4) {
        await delay(500)
        callbacks.onProgress?.({
          pct: done / total,
          stage: `${done}/${total} chunk embed edildi`,
        })
      }
      await delay(300)
      callbacks.onProgress?.({ pct: 1, stage: "Veritabanına yazıldı." })

      const skipped = name.includes("atla") ? [3, 7] : []
      const uploaded: DocumentInfo = {
        filename: file.name,
        page_count: 9,
        chunk_count: total,
        ingested_at: new Date().toISOString().slice(0, 19),
        has_ocr_chunks: name.includes("ocr"),
      }
      documents = [
        uploaded,
        ...documents.filter((doc) => doc.filename !== file.name),
      ]
      await delay(200)
      callbacks.onComplete?.({
        filename: uploaded.filename,
        page_count: uploaded.page_count,
        chunk_count: uploaded.chunk_count,
        skipped_pages: skipped,
      })
    },
  }
}

function LocaleSwitcher() {
  const { locale, setLocale } = useLocale()
  const t = useT(common)
  return (
    <div className="flex items-center gap-1" aria-label={t.languageLabel}>
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

/** Sohbet slot'unun yerine geçen sahte panel (içeriği frontend-chat yazacak). */
function MockChat({
  uploading,
  documentCount,
  callbackCount,
  status,
}: {
  uploading: boolean
  documentCount: number | null
  callbackCount: number | null
  status: string
}) {
  const shell = useAppShell()
  const t = useT(sidebarText)

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">chat slot</Badge>
        <Badge variant="secondary">breakpoint: {shell.breakpoint}</Badge>
        <Badge variant={uploading ? "destructive" : "ghost"}>
          {uploading ? "input locked (upload)" : "input unlocked"}
        </Badge>
        <Badge variant="ghost">
          documents: {documentCount === null ? "…" : documentCount}
        </Badge>
        <Badge variant="ghost">
          onDocumentsChange: {callbackCount === null ? "…" : callbackCount}
        </Badge>
        <Badge variant="ghost">health: {status}</Badge>
      </div>
      <p className="text-body text-text-secondary">
        Bu alan <code className="font-mono text-mono">frontend-chat</code>{" "}
        agent&apos;ına ait. AppShell yalnızca yerleşimi kurar ve bölgeyi slot
        olarak alır.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={shell.openInspector}
      >
        {t.openSources}
      </Button>
      <div className="min-h-0 flex-1 rounded-lg border border-dashed border-border" />
    </div>
  )
}

/** Inspector slot'unun yerine geçen sahte panel. */
function MockInspector() {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <Badge variant="outline">inspector slot</Badge>
      <p className="text-body-sm text-text-secondary">
        ≥1280px&apos;te kalıcı kolon, altında overlay drawer
        (DESIGN_SYSTEM.md §4).
      </p>
      <div className="min-h-0 flex-1 rounded-lg border border-dashed border-border" />
    </div>
  )
}

function PreviewBody() {
  const [scenario, setScenario] = React.useState<Scenario>("ready")
  const [uploading, setUploading] = React.useState(false)
  const [callbackDocuments, setCallbackDocuments] = React.useState<
    DocumentInfo[] | null
  >(null)
  const breakpoint = useBreakpoint()

  // Kaynak KARARLI bir referans olmalı: her render'da yenisi üretilirse
  // her seferinde yeni bir store kurulur.
  const source = React.useMemo(() => createMockSource(scenario), [scenario])

  // Entegrasyonun (app/page.tsx) izleyeceği desen: sayfa düzeyinde aynı
  // store'a bağlan. Mobilde sidebar drawer kapalıyken mount edilmediği için
  // sohbetin belge sayısını buradan öğrenmesi gerekir.
  const { documents, health } = useKnowledge(source)

  const handleDocuments = React.useCallback((next: DocumentInfo[]) => {
    setCallbackDocuments(next)
  }, [])

  return (
    <AppShell
      key={scenario}
      brand={
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-h3 font-semibold">dev-kb</span>
          <span className="hidden text-caption text-text-tertiary sm:inline">
            {breakpoint}
          </span>
        </div>
      }
      headerActions={
        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-1 md:flex">
            {SCENARIOS.map((option) => (
              <Button
                key={option}
                size="xs"
                variant={scenario === option ? "default" : "outline"}
                onClick={() => setScenario(option)}
              >
                {option}
              </Button>
            ))}
          </div>
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      }
      sidebar={
        <KnowledgeSidebar
          source={source}
          onUploadingChange={setUploading}
          onDocumentsChange={handleDocuments}
        />
      }
      chat={
        <MockChat
          uploading={uploading}
          documentCount={documents?.length ?? null}
          callbackCount={callbackDocuments?.length ?? null}
          status={health?.status ?? "…"}
        />
      }
      inspector={<MockInspector />}
    />
  )
}

export default function DevKbPage() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <PreviewBody />
      </LanguageProvider>
    </ThemeProvider>
  )
}
