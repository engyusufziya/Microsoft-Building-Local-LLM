"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"

import { DocumentUploader } from "./document-uploader"
import { useKnowledge } from "./use-knowledge"

/**
 * İlk açılış / boş korpus ekranı — FEATURE_SPEC §13.5 (Faz 5).
 *
 * Mockup'ta bu ekran TAM EKRAN (`inset:0`) ve sidebar'ı da kaplıyor. Sebebi
 * şu: korpus boşken sol panelde gösterilecek bir şey yok, ve kullanıcının
 * yapması gereken tek bir şey var. Tek çağrı, tek hedef.
 *
 * KENDİ YÜKLEYİCİSİNİ KURMAZ: var olan `DocumentUploader` bileşenini render
 * eder. İki ayrı yükleme yolu olsaydı SSE ilerlemesi, yinelenen dosya adı
 * kontrolü ve hata eşlemesi iki yerde bakım isterdi.
 *
 * Mockup'ın "Örnek defteri aç" düğmesi ALINMADI: depoda paketlenmiş bir
 * örnek korpus yok, eklemek düzen işi değil yeni bir yetenek olurdu.
 * Alt satırdaki "6.2 GB RAM" de alınmadı — cihaz telemetrisi §13.6'da
 * kapsam dışı; satır yalnızca backend'in gerçekten bildiğini yazıyor.
 */
export interface EmptyWorkspaceProps {
  onUploadingChange?: (uploading: boolean) => void
  className?: string
}

export function EmptyWorkspace({
  onUploadingChange,
  className,
}: EmptyWorkspaceProps) {
  const t = useT(sidebarText)
  const { health, refreshAll } = useKnowledge()

  const uploadDisabled = health !== null && health.status !== "ready"
  const uploadDisabledReason = !uploadDisabled
    ? undefined
    : health?.status === "warming"
      ? t.uploadWarming
      : t.statusError

  const steps = [
    { title: t.firstRunStep1Title, body: t.firstRunStep1Body },
    { title: t.firstRunStep2Title, body: t.firstRunStep2Body },
    { title: t.firstRunStep3Title, body: t.firstRunStep3Body },
  ]

  return (
    <div
      data-slot="empty-workspace"
      className={cn(
        "fixed inset-0 z-50 overflow-y-auto bg-background",
        className
      )}
    >
      <div className="mx-auto w-full max-w-4xl px-6 py-14">
        <p className="text-caption font-medium tracking-[0.1em] text-primary uppercase">
          {t.firstRunKicker}
        </p>
        <h1 className="mt-3 text-h1 leading-[1.05] font-semibold text-text-primary">
          {t.firstRunTitle}
        </h1>
        <p className="mt-3.5 max-w-[52ch] text-body text-text-secondary">
          {t.firstRunBody}
        </p>

        <div className="mt-8 border-2 border-text-primary p-6">
          <DocumentUploader
            disabled={uploadDisabled}
            disabledReason={uploadDisabledReason}
            existingFilenames={[]}
            onUploadingChange={onUploadingChange}
            onUploaded={() => {
              void refreshAll()
            }}
          />
        </div>

        <div className="mt-10 border-t-2 border-border pt-5">
          <p className="text-caption font-medium tracking-[0.08em] text-text-secondary uppercase">
            {t.firstRunStepsTitle}
          </p>
          <ol className="mt-4 grid border-2 border-text-primary sm:grid-cols-3">
            {steps.map((step, index) => (
              <li
                key={step.title}
                className={cn(
                  "p-5",
                  index < steps.length - 1 &&
                    "border-b-2 border-text-primary sm:border-r-2 sm:border-b-0"
                )}
              >
                <p className="text-h1 font-semibold text-primary tabular-nums">
                  {String(index + 1).padStart(2, "0")}
                </p>
                <p className="mt-3 text-body-sm font-semibold text-text-primary">
                  {step.title}
                </p>
                <p className="mt-1.5 text-caption text-text-secondary">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>

        {health !== null && (
          <p className="mt-6 flex items-center gap-2.5 font-mono text-mono text-text-tertiary">
            <span
              aria-hidden="true"
              className={cn(
                "size-1.5 shrink-0",
                health.status === "ready" ? "bg-primary" : "bg-warning"
              )}
            />
            {t.firstRunEngineLine(health.chat_model)}
          </p>
        )}
      </div>
    </div>
  )
}
