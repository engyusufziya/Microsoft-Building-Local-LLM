"use client"

import * as React from "react"
import {
  CircleAlertIcon,
  CircleCheckIcon,
  FileTextIcon,
  LoaderIcon,
  TriangleAlertIcon,
  UploadCloudIcon,
  XIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { useLocale, useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import type { UploadCompleteEvent } from "@/lib/types"
import { Button } from "@/components/ui/button"
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "@/components/ui/progress"

import {
  DEFAULT_MAX_UPLOAD_BYTES,
  apiFailure,
  failureText,
  toFailure,
  type Failure,
} from "./error-messages"
import { defaultKnowledgeSource, type KnowledgeSource } from "./knowledge-source"
import { localizeUploadStage } from "./upload-stage"

type UploadStatus = "queued" | "uploading" | "done" | "error"

interface UploadItem {
  id: string
  filename: string
  status: UploadStatus
  /** 0–1 (SSE `progress.pct` ile aynı ölçek). */
  pct: number
  /** Backend'den gelen HAM aşama metni; render'da yerelleştirilir. */
  stage: string | null
  chunkCount: number | null
  skippedPages: readonly number[]
  /** Aynı adlı belge zaten vardı → `upsert_document` üzerine yazdı. */
  replaced: boolean
  failure: Failure | null
}

export interface DocumentUploaderProps {
  className?: string
  /** Modeller hazır değilken yükleme kilitlenir (FEATURE_SPEC §5). */
  disabled?: boolean
  /** Kilidin sebebi — kullanıcıya yazılır. */
  disabledReason?: string
  /**
   * Yükleme anındaki belge adları. FEATURE_SPEC §1.1: aynı dosya adı
   * sessizce üzerine yazılır, kullanıcıya "güncellendi" denir.
   */
  existingFilenames?: readonly string[]
  /** İstemci ön kontrolü; backend sınırıyla aynı olmalı. */
  maxFileBytes?: number
  /** Enjeksiyon noktası — varsayılan `lib/api.ts::uploadDocument`. */
  upload?: KnowledgeSource["uploadDocument"]
  /** Kuyruk başlarken `true`, bitince `false`. Sohbet girdisi buna bakar. */
  onUploadingChange?: (uploading: boolean) => void
  /** Her başarılı belge sonrası — liste tazelemek için. */
  onUploaded?: (event: UploadCompleteEvent) => void
}

function isPdf(file: File): boolean {
  return (
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
  )
}

/**
 * Sürükle-bırak + dosya seçici ile çoklu PDF yükleme (FEATURE_SPEC §1.1).
 *
 * Dosyalar SIRAYLA yüklenir: ingest embedding modelini kullanıyor ve
 * backend tüm model çağrılarını tek bir kilit arkasında serileştiriyor
 * (FEATURE_SPEC §7). Paralel göndermek kuyruğu backend'e taşımaktan
 * başka bir işe yaramaz, ilerleme göstergesini ise okunmaz hale getirir.
 *
 * Bir dosyanın hatası kuyruğu durdurmaz — §1.1'deki hata dalları tablosu
 * "diğer dosyalar devam eder" diyor.
 */
function DocumentUploader({
  className,
  disabled = false,
  disabledReason,
  existingFilenames,
  maxFileBytes = DEFAULT_MAX_UPLOAD_BYTES,
  upload,
  onUploadingChange,
  onUploaded,
}: DocumentUploaderProps) {
  const t = useT(sidebarText)
  const tc = useT(common)
  const { locale } = useLocale()

  const [items, setItems] = React.useState<UploadItem[]>([])
  const [dragging, setDragging] = React.useState(false)
  const [uploading, setUploading] = React.useState(false)

  const inputRef = React.useRef<HTMLInputElement>(null)
  const idRef = React.useRef(0)
  const queueRef = React.useRef<{ id: string; file: File }[]>([])
  const runningRef = React.useRef(false)

  // Uzun süren kuyruk, başladığı andaki prop'lara takılı kalmasın diye
  // değişkenler ref üzerinden okunur (yükleme dakikalar sürebilir).
  const latestRef = React.useRef({
    upload,
    existingFilenames,
    maxFileBytes,
    onUploadingChange,
    onUploaded,
  })
  React.useEffect(() => {
    latestRef.current = {
      upload,
      existingFilenames,
      maxFileBytes,
      onUploadingChange,
      onUploaded,
    }
  })

  const patch = React.useCallback(
    (id: string, changes: Partial<UploadItem>) => {
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, ...changes } : item))
      )
    },
    []
  )

  const uploadOne = React.useCallback(
    async (id: string, file: File) => {
      const {
        upload: uploadFn,
        existingFilenames: existing,
        maxFileBytes: maxBytes,
        onUploaded: notifyUploaded,
      } = latestRef.current
      const send = uploadFn ?? defaultKnowledgeSource.uploadDocument
      const existed = new Set(existing ?? [])

      patch(id, { status: "uploading", pct: 0, stage: null, failure: null })

      let finished = false
      try {
        await send(file, {
          onProgress: (event) => {
            patch(id, { pct: event.pct, stage: event.stage })
          },
          onComplete: (event) => {
            finished = true
            patch(id, {
              status: "done",
              pct: 1,
              stage: null,
              chunkCount: event.chunk_count,
              skippedPages: event.skipped_pages,
              replaced: existed.has(event.filename),
            })
            notifyUploaded?.(event)
          },
          onError: (body) => {
            finished = true
            patch(id, {
              status: "error",
              failure: apiFailure(body.code, maxBytes),
            })
          },
        })
        if (!finished) {
          // Akış ne `complete` ne `error` ile bitti (bağlantı koptu).
          patch(id, { status: "error", failure: { kind: "network" } })
        }
      } catch (error) {
        patch(id, { status: "error", failure: toFailure(error, maxBytes) })
      }
    },
    [patch]
  )

  const runQueue = React.useCallback(async () => {
    if (runningRef.current) return
    runningRef.current = true
    setUploading(true)
    latestRef.current.onUploadingChange?.(true)
    try {
      for (
        let next = queueRef.current.shift();
        next !== undefined;
        next = queueRef.current.shift()
      ) {
        await uploadOne(next.id, next.file)
      }
    } finally {
      runningRef.current = false
      setUploading(false)
      latestRef.current.onUploadingChange?.(false)
    }
  }, [uploadOne])

  const addFiles = React.useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return
      const maxBytes = latestRef.current.maxFileBytes ?? DEFAULT_MAX_UPLOAD_BYTES

      const created: UploadItem[] = []
      const queued: { id: string; file: File }[] = []

      for (const file of Array.from(fileList)) {
        idRef.current += 1
        const id = `upload-${idRef.current}`
        const base: UploadItem = {
          id,
          filename: file.name,
          status: "queued",
          pct: 0,
          stage: null,
          chunkCount: null,
          skippedPages: [],
          replaced: false,
          failure: null,
        }

        // FEATURE_SPEC §1.1: dosya tipi/boyut ÖN kontrolü istemcide.
        if (!isPdf(file)) {
          created.push({ ...base, status: "error", failure: { kind: "not-pdf" } })
          continue
        }
        if (file.size > maxBytes) {
          created.push({
            ...base,
            status: "error",
            failure: { kind: "too-large", maxBytes },
          })
          continue
        }

        created.push(base)
        queued.push({ id, file })
      }

      setItems((prev) => [...prev, ...created])
      queueRef.current.push(...queued)
      if (queued.length > 0) void runQueue()
    },
    [runQueue]
  )

  const removeItem = React.useCallback((id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const clearFinished = React.useCallback(() => {
    setItems((prev) =>
      prev.filter((item) => item.status === "queued" || item.status === "uploading")
    )
  }, [])

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    addFiles(event.dataTransfer.files)
  }

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    if (disabled) return
    event.preventDefault()
    event.dataTransfer.dropEffect = "copy"
    setDragging(true)
  }

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    // Alt öğeler arasında gezinirken sönmesin.
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
    setDragging(false)
  }

  const hasFinished = items.some(
    (item) => item.status === "done" || item.status === "error"
  )
  const numberLocale = locale === "tr" ? "tr-TR" : "en-US"

  return (
    <section
      data-slot="document-uploader"
      aria-label={t.uploadArea}
      className={cn("flex flex-col gap-2", className)}
    >
      <div
        data-dragging={dragging || undefined}
        aria-disabled={disabled || undefined}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border border-dashed border-border-strong bg-surface-raised px-3 py-4 text-center transition-colors duration-[var(--duration-hover)] ease-[var(--ease-standard)]",
          dragging && !disabled && "border-primary bg-primary/5",
          disabled && "opacity-60"
        )}
      >
        <UploadCloudIcon aria-hidden="true" className="size-5 text-text-secondary" />
        <p className="text-body-sm font-medium text-foreground">
          {dragging && !disabled ? t.uploadDropActive : t.uploadTitle}
        </p>
        <p className="text-caption text-text-secondary">{t.uploadHint}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          {t.uploadBrowse}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            addFiles(event.target.files)
            // Aynı dosya arka arkaya seçilebilsin.
            event.target.value = ""
          }}
        />
      </div>

      {disabled && disabledReason && (
        <p className="text-caption text-warning">{disabledReason}</p>
      )}
      {uploading && (
        <p className="text-caption text-text-secondary">{t.uploadBusyHint}</p>
      )}

      {items.length > 0 && (
        <ul className="flex list-none flex-col gap-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="rounded-md border border-border bg-surface-raised p-2"
            >
              <div className="flex items-start gap-2">
                <StatusIcon status={item.status} />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <p
                    className="truncate text-body-sm font-medium text-foreground"
                    title={item.filename}
                  >
                    {item.filename}
                  </p>

                  {item.status === "queued" && (
                    <p className="text-caption text-text-secondary">
                      {t.stageQueued}
                    </p>
                  )}

                  {item.status === "uploading" && (
                    <Progress
                      value={Math.round(item.pct * 100)}
                      locale={numberLocale}
                      className="gap-1"
                    >
                      <ProgressLabel className="text-caption font-normal text-text-secondary">
                        {localizeUploadStage(item.stage, t)}
                      </ProgressLabel>
                      <ProgressValue className="font-mono text-mono text-text-secondary" />
                    </Progress>
                  )}

                  {item.status === "done" && (
                    <div className="flex flex-col gap-1">
                      <p className="text-caption text-success">
                        {t.uploadDone(item.chunkCount ?? 0)}
                      </p>
                      {item.replaced && (
                        <p className="text-caption text-text-secondary">
                          {t.uploadReplaced}
                        </p>
                      )}
                      {item.skippedPages.length > 0 && (
                        <div className="flex flex-col gap-0.5 rounded-sm bg-warning/10 px-1.5 py-1 text-warning">
                          <span className="inline-flex items-center gap-1 text-caption font-medium">
                            <TriangleAlertIcon
                              aria-hidden="true"
                              className="size-3"
                            />
                            {t.pagesSkipped(item.skippedPages.length)}
                          </span>
                          <span className="font-mono text-mono">
                            {t.skippedPagesList(item.skippedPages)}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {item.status === "error" && item.failure && (
                    <p className="text-caption text-danger">
                      <span className="font-medium">{t.uploadFailed}</span>{" "}
                      {failureText(item.failure, t, tc)}
                    </p>
                  )}
                </div>

                {(item.status === "done" || item.status === "error") && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    aria-label={t.removeFromList}
                    onClick={() => removeItem(item.id)}
                  >
                    <XIcon />
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {hasFinished && (
        <Button
          type="button"
          variant="ghost"
          size="xs"
          className="self-start"
          onClick={clearFinished}
        >
          {t.clearFinished}
        </Button>
      )}
    </section>
  )
}

function StatusIcon({ status }: { status: UploadStatus }) {
  const className = "mt-0.5 size-4 shrink-0"
  switch (status) {
    case "uploading":
      return (
        <LoaderIcon
          aria-hidden="true"
          className={cn(className, "animate-spin text-primary")}
        />
      )
    case "done":
      return (
        <CircleCheckIcon aria-hidden="true" className={cn(className, "text-success")} />
      )
    case "error":
      return (
        <CircleAlertIcon aria-hidden="true" className={cn(className, "text-danger")} />
      )
    default:
      return (
        <FileTextIcon
          aria-hidden="true"
          className={cn(className, "text-text-secondary")}
        />
      )
  }
}

export { DocumentUploader }
