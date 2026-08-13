"use client"

import { FolderOpenIcon, RefreshCwIcon, TriangleAlertIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { DocumentInfo } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

import { DocumentCard } from "./document-card"

export interface DocumentListProps {
  /** `null` = henüz hiç yüklenmedi (ilk istek sürüyor ya da başarısız oldu). */
  documents: DocumentInfo[] | null
  loading?: boolean
  /** Yerelleştirilmiş liste hatası metni. */
  errorText?: string
  onRefresh?: () => void
  onDelete?: (filename: string) => boolean | void | Promise<boolean | void>
  deletingFilename?: string | null
  /** Silinemeyen belgenin adı — hata yalnızca o kartta gösterilir. */
  deleteErrorFilename?: string | null
  deleteErrorText?: string
  className?: string
}

/**
 * Belge listesi + boş/yükleniyor/hata durumları (FEATURE_SPEC §5 matrisi).
 *
 * Boş durum yalnızca "hiç belge yok" demez, ne yapılacağını da söyler:
 * sohbet girdisi belge olmadan kilitli olduğu için buradaki yönlendirme
 * kullanıcının tek çıkış yolu.
 */
function DocumentList({
  documents,
  loading = false,
  errorText,
  onRefresh,
  onDelete,
  deletingFilename,
  deleteErrorFilename,
  deleteErrorText,
  className,
}: DocumentListProps) {
  const t = useT(sidebarText)
  const tc = useT(common)

  const isInitialLoad = loading && documents === null
  const showError = errorText !== undefined && documents === null && !loading

  return (
    <section aria-label={t.documentsTitle} className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <h2 className="text-h3 font-semibold text-foreground">
          {t.documentsTitle}
        </h2>
        {documents !== null && (
          <span className="text-caption font-medium text-text-secondary">
            {t.documentCount(documents.length)}
          </span>
        )}
        {onRefresh && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            className="ml-auto"
            aria-label={t.refresh}
            disabled={loading}
            onClick={onRefresh}
          >
            <RefreshCwIcon className={cn(loading && "animate-spin")} />
          </Button>
        )}
      </div>

      {isInitialLoad && (
        <div className="flex flex-col gap-2" aria-hidden="true">
          {[0, 1, 2].map((row) => (
            <div
              key={row}
              className="flex flex-col gap-2 rounded-lg border border-border bg-surface-raised p-2.5"
            >
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
          <span className="sr-only">{tc.loading}</span>
        </div>
      )}

      {showError && (
        <div className="flex flex-col items-start gap-2 rounded-lg border border-border bg-danger/5 p-3">
          <p className="inline-flex items-center gap-1.5 text-body-sm text-danger">
            <TriangleAlertIcon aria-hidden="true" className="size-4 shrink-0" />
            {t.listFailed}
          </p>
          <p className="text-caption text-text-secondary">{errorText}</p>
          {onRefresh && (
            <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
              {tc.retry}
            </Button>
          )}
        </div>
      )}

      {documents !== null && documents.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-6 text-center">
          <FolderOpenIcon
            aria-hidden="true"
            className="size-5 text-text-secondary"
          />
          <p className="text-body-sm font-medium text-foreground">
            {t.emptyTitle}
          </p>
          <p className="text-caption text-text-secondary">{t.emptyBody}</p>
          <p className="text-caption text-text-tertiary">{t.emptyHint}</p>
        </div>
      )}

      {documents !== null && documents.length > 0 && (
        <ul className="flex list-none flex-col gap-2">
          {documents.map((document) => (
            <li key={document.filename}>
              <DocumentCard
                document={document}
                onDelete={onDelete}
                deleting={deletingFilename === document.filename}
                isLast={documents.length === 1}
                deleteErrorText={
                  deleteErrorFilename === document.filename
                    ? deleteErrorText
                    : undefined
                }
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export { DocumentList }
