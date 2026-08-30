"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { DocumentInfo, HealthResponse } from "@/lib/types"
import { ScrollArea } from "@/components/ui/scroll-area"

import { CorpusStats } from "./corpus-stats"
import { DocumentList } from "./document-list"
import { DocumentUploader } from "./document-uploader"
import { failureText } from "./error-messages"
import type { KnowledgeSource } from "./knowledge-source"
import { useKnowledge } from "./use-knowledge"

type SidebarTabKey = "sources" | "outputs"

/** Sol panelin sekme düğmesi. Modernist: köşesiz, aktif olan alttan 3px kural. */
function SidebarTab({
  id,
  controls,
  selected,
  onSelect,
  className,
  children,
  ref,
}: {
  id: string
  controls: string
  selected: boolean
  onSelect: () => void
  className?: string
  children: React.ReactNode
  ref?: React.Ref<HTMLButtonElement>
}) {
  return (
    <button
      ref={ref}
      type="button"
      id={id}
      role="tab"
      aria-selected={selected}
      aria-controls={controls}
      tabIndex={selected ? 0 : -1}
      onClick={onSelect}
      className={cn(
        "-mb-0.5 flex-1 cursor-pointer border-b-[3px] px-4 py-3 text-left",
        "text-caption tracking-[0.08em] uppercase",
        "transition-colors duration-(--duration-hover) ease-(--ease-standard)",
        "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
        selected
          ? "border-primary font-semibold text-text-primary"
          : "border-transparent font-medium text-text-secondary hover:text-text-primary",
        className
      )}
    >
      {children}
    </button>
  )
}

export interface KnowledgeSidebarProps {
  className?: string
  /** Test/önizleme için backend yerine sahte kaynak. Kararlı bir referans olmalı. */
  source?: KnowledgeSource
  /**
   * Yükleme başlarken `true`, bitince `false`. FEATURE_SPEC §1.1:
   * ingest embedding modelini kullandığı için sohbet girdisi bu sürede
   * kilitlenmeli ve sebebi yazılmalı.
   */
  onUploadingChange?: (uploading: boolean) => void
  /**
   * Liste her tazelendiğinde. Sohbet "belge yok → girdi kilitli" durumunu
   * (FEATURE_SPEC §5) buradan bilir.
   */
  onDocumentsChange?: (documents: DocumentInfo[]) => void
  /**
   * `/api/health` her tazelendiğinde. `min_score`/`top_k` tüketicileri
   * (Inspector eşik çizgisi) değeri BURADAN alır, koda gömmez.
   */
  onHealthChange?: (health: HealthResponse | null) => void
  /**
   * "Çıktılar" sekmesinin içeriği — FEATURE_SPEC §13.2 ile artefakt listesi
   * sağ kolondan buraya taşındı. Slot olarak alınır, doğrudan import
   * EDİLMEZ: `sidebar/` ile `studio/` ayrı sahiplerde (AGENTS.md ownership
   * map) ve bu bileşen Studio'nun içeriğini bilmemeli, yalnızca yerini.
   */
  outputs?: React.ReactNode
}

/**
 * Sidebar'ın birleştirici kökü: yükleyici + liste + korpus/sistem özeti.
 *
 * Durum sahipliği burada: `DocumentUploader` bir belge bitirdiğinde liste
 * ve sayaçlar tazelenir (FEATURE_SPEC §1.1 son adım), silme sonrası da
 * aynı (§1.4). Entegrasyonun `app/page.tsx` içinde bu bağlantıları
 * yeniden kurmasına gerek yok — tek bir `<KnowledgeSidebar />` yeter.
 */
function KnowledgeSidebar({
  className,
  source,
  onUploadingChange,
  onDocumentsChange,
  onHealthChange,
  outputs,
}: KnowledgeSidebarProps) {
  const t = useT(sidebarText)
  const tc = useT(common)
  const knowledge = useKnowledge(source)

  const {
    documents,
    documentsLoading,
    documentsFailure,
    health,
    deletingFilename,
    deleteFailure,
    refreshDocuments,
    refreshAll,
    removeDocument,
  } = knowledge

  // Üst bileşene haber verme: prop'lar ref'te tutulur ki satır içi ok
  // fonksiyonu geçen bir ebeveyn sonsuz effect döngüsü kurmasın.
  const notifyRef = React.useRef({ onDocumentsChange, onHealthChange })
  React.useEffect(() => {
    notifyRef.current = { onDocumentsChange, onHealthChange }
  })

  React.useEffect(() => {
    if (documents !== null) notifyRef.current.onDocumentsChange?.(documents)
  }, [documents])

  React.useEffect(() => {
    notifyRef.current.onHealthChange?.(health)
  }, [health])

  const filenames = React.useMemo(
    () => (documents ?? []).map((document) => document.filename),
    [documents]
  )

  const totals = React.useMemo(() => {
    if (documents === null) return null
    return documents.reduce(
      (acc, document) => ({
        pages: acc.pages + document.page_count,
        chunks: acc.chunks + document.chunk_count,
      }),
      { pages: 0, chunks: 0 }
    )
  }, [documents])

  const documentsErrorText = documentsFailure
    ? failureText(documentsFailure, t, tc)
    : undefined
  const deleteErrorText = deleteFailure
    ? `${t.deleteFailed} ${failureText(deleteFailure.failure, t, tc)}`
    : undefined

  // FEATURE_SPEC §5: modeller hazır değilken yükleme kilitli.
  const uploadDisabled = health !== null && health.status !== "ready"
  const uploadDisabledReason = !uploadDisabled
    ? undefined
    : health?.status === "warming"
      ? t.uploadWarming
      : t.statusError

  // WAI-ARIA tabs: roving tabindex + ok/Home/End. Sağ panelin sekme
  // anahtarından TAŞINDI (o dosya §13.2 ile kaldırıldı), kopyalanmadı.
  const [active, setActive] = React.useState<SidebarTabKey>("sources")
  const sourcesTabId = React.useId()
  const outputsTabId = React.useId()
  const sourcesPanelId = React.useId()
  const outputsPanelId = React.useId()
  const sourcesButtonRef = React.useRef<HTMLButtonElement | null>(null)
  const outputsButtonRef = React.useRef<HTMLButtonElement | null>(null)

  const focusAndSelect = React.useCallback((tab: SidebarTabKey) => {
    setActive(tab)
    const target =
      tab === "sources" ? sourcesButtonRef.current : outputsButtonRef.current
    target?.focus()
  }, [])

  const handleTabKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      switch (event.key) {
        case "ArrowRight":
        case "ArrowLeft":
          event.preventDefault()
          focusAndSelect(active === "sources" ? "outputs" : "sources")
          break
        case "Home":
          event.preventDefault()
          focusAndSelect("sources")
          break
        case "End":
          event.preventDefault()
          focusAndSelect("outputs")
          break
        default:
          break
      }
    },
    [active, focusAndSelect]
  )

  return (
    <div
      data-slot="knowledge-sidebar"
      className={cn("flex h-full min-h-0 flex-col bg-surface", className)}
    >
      {/* Sekme anahtarı başlığın YERİNİ alır (§13.2): panelin adı artık
          hangi sekmede olduğundur. Mobil drawer'da da görünür — bu bir
          başlık değil, gezinme. */}
      <div
        role="tablist"
        aria-label={t.tabListLabel}
        onKeyDown={handleTabKeyDown}
        className="flex shrink-0 border-b-2 border-border"
      >
        <SidebarTab
          ref={sourcesButtonRef}
          id={sourcesTabId}
          controls={sourcesPanelId}
          selected={active === "sources"}
          onSelect={() => setActive("sources")}
        >
          {t.tabSources}
        </SidebarTab>
        <SidebarTab
          ref={outputsButtonRef}
          id={outputsTabId}
          controls={outputsPanelId}
          selected={active === "outputs"}
          className="border-l border-border"
          onSelect={() => setActive("outputs")}
        >
          {t.tabOutputs}
        </SidebarTab>
      </div>

      {/* Her iki panel de mount'lu kalır, `hidden` ile gizlenir: aksi halde
          Çıktılar'a geçip dönmek yükleme ilerlemesini ve liste kaydırmasını
          sıfırlardı (sağ panel sekmelerinin aynı gerekçesi). */}
      <div
        id={outputsPanelId}
        role="tabpanel"
        aria-labelledby={outputsTabId}
        hidden={active !== "outputs"}
        className="flex min-h-0 flex-1 flex-col"
      >
        {outputs}
      </div>

      <div
        id={sourcesPanelId}
        role="tabpanel"
        aria-labelledby={sourcesTabId}
        hidden={active !== "sources"}
        className="flex min-h-0 flex-1 flex-col"
      >
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-4 p-3">
          <DocumentUploader
            disabled={uploadDisabled}
            disabledReason={uploadDisabledReason}
            existingFilenames={filenames}
            upload={source?.uploadDocument}
            onUploadingChange={onUploadingChange}
            onUploaded={() => {
              void refreshAll()
            }}
          />

          <DocumentList
            documents={documents}
            loading={documentsLoading}
            errorText={documentsErrorText}
            onRefresh={() => {
              void refreshDocuments()
            }}
            onDelete={removeDocument}
            deletingFilename={deletingFilename}
            deleteErrorFilename={deleteFailure?.filename ?? null}
            deleteErrorText={deleteErrorText}
          />
        </div>
      </ScrollArea>
      </div>

      <div className="flex shrink-0 flex-col gap-3 border-t-2 border-border p-3">
        <CorpusStats
          documentCount={documents?.length ?? null}
          pageCount={totals?.pages ?? null}
          chunkCount={totals?.chunks ?? null}
        />
      </div>
    </div>
  )
}

export { KnowledgeSidebar }
