"use client"

import * as React from "react"
import Link from "next/link"
import { BarChart3Icon } from "lucide-react"

import { ChatPanel, type ChatLockReason } from "@/components/chat"
import { LanguageToggle } from "@/components/language-toggle"
import { AppShell, useAppShell } from "@/components/shell"
import { KnowledgeSidebar, useKnowledge } from "@/components/sidebar"
import { ReportView, RightPanelTabs, useArtifacts } from "@/components/studio"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { metrics as metricsStrings } from "@/lib/i18n/metrics"
import { studio as studioStrings } from "@/lib/i18n/studio"

function Brand() {
  return (
    <Link href="/" className="flex items-baseline gap-2 no-underline">
      <span className="text-h2 font-semibold text-text-primary">
        Local RAG Assistant
      </span>
      <span className="hidden text-caption font-medium text-text-tertiary sm:inline">
        Foundry Local
      </span>
    </Link>
  )
}

function HeaderActions() {
  const c = useT(common)
  const m = useT(metricsStrings)
  return (
    <div className="flex items-center gap-1">
      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              render={<Link href="/metrics" aria-label={m.pageTitle} />}
            />
          }
        >
          <BarChart3Icon className="size-4" aria-hidden="true" />
        </TooltipTrigger>
        <TooltipContent>{m.pageTitle}</TooltipContent>
      </Tooltip>
      <LanguageToggle />
      <ThemeToggle
        labels={{ light: c.themeLight, dark: c.themeDark, system: c.themeSystem }}
      />
    </div>
  )
}

/**
 * Sohbetin "kaynakları incele" düğmesini kabuğun Inspector drawer'ına bağlar.
 *
 * İki agent paralel çalıştığı için `ChatPanel` kabuğun context'ini doğrudan
 * kullanamadı (o dosya başka bir agent'ındı) ve `onOpenInspector` prop'unu
 * dışarıya bıraktı; `AppShell` de simetrik olarak `openInspector()`'ı context
 * ile sunuyor. Bu köprü ikisini birleştiriyor. AppShell'in `chat` slotu
 * provider'ın İÇİNDE render edildiği için `useAppShell()` burada geçerli.
 */
function ChatSlot({
  lock,
  documentCount,
}: {
  lock: ChatLockReason | null
  documentCount: number | undefined
}) {
  const { openInspector, isInspectorOverlay } = useAppShell()
  return (
    <ChatPanel
      lock={lock}
      documentCount={documentCount}
      // Kalıcı kolon modunda düğmeye gerek yok; Inspector zaten görünür.
      onOpenInspector={isInspectorOverlay ? openInspector : undefined}
    />
  )
}

/**
 * `<main>` ya sohbeti ya açık raporu gösterir — FEATURE_SPEC §10.12.
 *
 * Rapor açıkken sohbet UNMOUNT edilmez, `hidden` ile gizlenir: aksi halde
 * rapora bakıp geri dönmek sohbet geçmişini ve akış durumunu sıfırlardı
 * (`right-panel-tabs.tsx`'teki sekme kararının aynısı).
 */
function MainSlot(props: { lock: ChatLockReason | null; documentCount: number | undefined }) {
  const { open, close } = useArtifacts()
  return (
    <>
      <div hidden={open !== null} className="flex min-h-0 flex-1 flex-col">
        <ChatSlot {...props} />
      </div>
      {open !== null && <ReportView artifact={open} onClose={close} />}
    </>
  )
}

export default function Home() {
  // Sidebar'ın callback'leri yerine aynı store'a doğrudan bağlanıyoruz:
  // mobilde sidebar drawer kapalıyken UNMOUNT oluyor ve callback'ler susuyor,
  // oysa sohbet kilidinin her breakpoint'te doğru olması gerekiyor.
  // `useKnowledge()` aynı örneğe bağlanır, ek istek üretmez.
  const { documents, health } = useKnowledge()
  const [uploading, setUploading] = React.useState(false)
  const s = useT(studioStrings)

  // FEATURE_SPEC §5 durum matrisi. Sıra önemli: model hazır değilse belge
  // sayısından bağımsız olarak "warming" gösterilmeli.
  const lock: ChatLockReason | null =
    health?.status === "error"
      ? "modelError"
      : health?.status === "warming"
        ? "warming"
        : uploading
          ? "uploading"
          : documents !== null && documents.length === 0
            ? "noDocuments"
            : null

  return (
    <AppShell
      brand={<Brand />}
      headerActions={<HeaderActions />}
      sidebar={<KnowledgeSidebar onUploadingChange={setUploading} />}
      chat={<MainSlot lock={lock} documentCount={documents?.length} />}
      inspector={<RightPanelTabs />}
      inspectorTitle={s.panelDrawerTitle}
    />
  )
}
