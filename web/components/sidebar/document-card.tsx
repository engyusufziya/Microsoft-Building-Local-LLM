"use client"

import * as React from "react"
import { FileTextIcon, Trash2Icon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useLocale, useT, type Locale } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { DocumentInfo } from "@/lib/types"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { OcrBadge } from "@/components/ui/ocr-badge"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

export interface DocumentCardProps {
  document: DocumentInfo
  /**
   * `false` dönerse onay diyaloğu AÇIK kalır ve hata metni orada gösterilir;
   * başka her dönüşte kapanır.
   */
  onDelete?: (filename: string) => boolean | void | Promise<boolean | void>
  deleting?: boolean
  /** Korpustaki tek belge mi — onay diyaloğunda ek uyarı (FEATURE_SPEC §1.4). */
  isLast?: boolean
  /** Silme hatası; yerelleştirilmiş metin olarak geçirilir. */
  deleteErrorText?: string
  className?: string
}

/**
 * `ingested_at` ISO 8601 (rag/store.py: `datetime.now().isoformat()`, saat
 * dilimi eki yok → yerel saat kabul edilir). Ayrıştırılamazsa ham metin
 * gösterilir; tarih formatı aktif dile göre `Intl` ile kurulur.
 */
function formatIngestedAt(iso: string, locale: Locale): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(locale === "tr" ? "tr-TR" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

/**
 * Tek bir belgenin kartı: ad, sayfa/bölüm sayısı, OCR rozeti ve silme.
 * Silme her zaman onay diyaloğundan geçer (FEATURE_SPEC §1.4).
 */
function DocumentCard({
  document,
  onDelete,
  deleting = false,
  isLast = false,
  deleteErrorText,
  className,
}: DocumentCardProps) {
  const t = useT(sidebarText)
  const tc = useT(common)
  const { locale } = useLocale()
  const [confirmOpen, setConfirmOpen] = React.useState(false)

  const ingestedAt = React.useMemo(
    () => formatIngestedAt(document.ingested_at, locale),
    [document.ingested_at, locale]
  )

  const handleConfirm = async () => {
    const result = await onDelete?.(document.filename)
    if (result !== false) setConfirmOpen(false)
  }

  return (
    <div
      data-slot="document-card"
      className={cn(
        "flex flex-col gap-1 rounded-lg border border-border bg-surface-raised p-2.5 transition-opacity duration-[var(--duration-hover)] ease-[var(--ease-standard)]",
        deleting && "opacity-60",
        className
      )}
    >
      <div className="flex items-start gap-2">
        <FileTextIcon
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-text-secondary"
        />
        <p
          className="min-w-0 flex-1 truncate text-body-sm font-medium text-foreground"
          title={document.filename}
        >
          {document.filename}
        </p>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                disabled={deleting}
                aria-label={t.deleteAction(document.filename)}
              />
            }
          >
            <Trash2Icon />
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t.deleteConfirmTitle}</DialogTitle>
              <DialogDescription>
                {t.deleteConfirmBody(document.filename)}
              </DialogDescription>
            </DialogHeader>
            {isLast && (
              <p className="text-body-sm text-warning">{t.deleteLastWarning}</p>
            )}
            {deleteErrorText && (
              <p className="text-body-sm text-danger">{deleteErrorText}</p>
            )}
            <DialogFooter>
              <DialogClose
                render={<Button type="button" variant="outline" />}
                disabled={deleting}
              >
                {tc.cancel}
              </DialogClose>
              <Button
                type="button"
                variant="destructive"
                disabled={deleting}
                onClick={handleConfirm}
              >
                {deleting ? t.deleting : tc.delete}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 pl-6 text-caption text-text-secondary">
        <span>{t.pageCount(document.page_count)}</span>
        <span aria-hidden="true">·</span>
        <span>{t.chunkCount(document.chunk_count)}</span>
        {document.has_ocr_chunks && (
          <Tooltip>
            <TooltipTrigger render={<OcrBadge label={t.ocrBadge} tabIndex={0} />} />
            <TooltipContent>{t.ocrTooltip}</TooltipContent>
          </Tooltip>
        )}
      </div>

      <p className="pl-6 text-caption text-text-tertiary">
        {t.addedAt(ingestedAt)}
      </p>
    </div>
  )
}

export { DocumentCard }
