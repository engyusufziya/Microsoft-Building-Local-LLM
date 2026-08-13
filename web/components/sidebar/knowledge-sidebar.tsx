"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { DocumentInfo, HealthResponse } from "@/lib/types"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useAppShellOptional } from "@/components/shell/app-shell-context"

import { CorpusStats } from "./corpus-stats"
import { DocumentList } from "./document-list"
import { DocumentUploader } from "./document-uploader"
import { failureText } from "./error-messages"
import type { KnowledgeSource } from "./knowledge-source"
import { SystemStatus } from "./system-status"
import { useKnowledge } from "./use-knowledge"

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
}: KnowledgeSidebarProps) {
  const t = useT(sidebarText)
  const tc = useT(common)
  const shell = useAppShellOptional()
  const knowledge = useKnowledge(source)

  const {
    documents,
    documentsLoading,
    documentsFailure,
    health,
    healthFailure,
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
  const healthErrorText = healthFailure
    ? failureText(healthFailure, t, tc)
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

  const showTitle = !shell?.isSidebarOverlay

  return (
    <div
      data-slot="knowledge-sidebar"
      className={cn("flex h-full min-h-0 flex-col bg-surface", className)}
    >
      {showTitle && (
        <div className="flex h-11 shrink-0 items-center border-b border-border px-3">
          <h2 className="truncate text-h3 font-semibold text-foreground">
            {t.panelTitle}
          </h2>
        </div>
      )}

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

      <div className="flex shrink-0 flex-col gap-3 border-t border-border p-3">
        <CorpusStats
          documentCount={documents?.length ?? null}
          pageCount={totals?.pages ?? null}
          chunkCount={totals?.chunks ?? null}
        />
        <SystemStatus
          health={health}
          errorText={healthErrorText}
          onRetry={() => {
            void refreshAll()
          }}
        />
      </div>
    </div>
  )
}

export { KnowledgeSidebar }
