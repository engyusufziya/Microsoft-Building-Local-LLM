"use client"

import * as React from "react"
import Link from "next/link"
import { BarChart3Icon, XIcon } from "lucide-react"

import { ChatPanel, type ChatLockReason } from "@/components/chat"
import { CitationDrawer } from "@/components/inspector"
import { LanguageToggle } from "@/components/language-toggle"
import { AppShell, useAppShell } from "@/components/shell"
import {
  EmptyWorkspace,
  KnowledgeSidebar,
  SettingsPanel,
  useKnowledge,
} from "@/components/sidebar"
import { ArtifactViewer, StudioPanel, useArtifacts } from "@/components/studio"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { sidebar as sidebarStrings } from "@/lib/i18n/sidebar"
import { metrics as metricsStrings } from "@/lib/i18n/metrics"

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

/**
 * Başlıktaki motor çipi + salt-okunur ayarlar çekmecesi (§13.5 Faz 5).
 *
 * Mockup'ın çipi "qwen2.5-7b · 18 tok/s · 6.2 GB" yazıyordu; tok/s ve RAM
 * cihaz telemetrisi ve §13.6'da kapsam dışı bırakıldı. Çip yalnızca
 * BACKEND'İN GERÇEKTEN BİLDİĞİNİ taşıyor: durum noktası + sohbet modeli.
 */
function EngineChip() {
  const t = useT(sidebarStrings)
  const { health } = useKnowledge()
  const [open, setOpen] = React.useState(false)

  const tone =
    health === null
      ? "bg-text-tertiary"
      : health.status === "ready"
        ? "bg-success"
        : health.status === "warming"
          ? "bg-warning"
          : "bg-danger"

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={t.openSettings}
        onClick={() => setOpen(true)}
      >
        <span aria-hidden="true" className={cn("size-1.5 shrink-0", tone)} />
        <span className="font-mono text-mono">
          {health?.chat_model ?? "—"}
        </span>
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          data-print="hide"
          side="right"
          showCloseButton={false}
          className="gap-0 p-0 data-[side=right]:w-[86vw] data-[side=right]:sm:max-w-100"
        >
          <SheetHeader className="flex-row items-center justify-between gap-2 border-b-2 border-border p-3">
            <SheetTitle>{t.settingsTitle}</SheetTitle>
            <SheetClose
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={t.closeSettings}
                />
              }
            >
              <XIcon />
            </SheetClose>
          </SheetHeader>
          <SettingsPanel />
        </SheetContent>
      </Sheet>
    </>
  )
}

function HeaderActions() {
  const c = useT(common)
  const m = useT(metricsStrings)
  return (
    <div className="flex items-center gap-1">
      <EngineChip />
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
  const { openInspector } = useAppShell()
  return (
    <ChatPanel
      lock={lock}
      documentCount={documentCount}
      // v3'te çekmece her kırılımda bağlama duyarlı (§13.2), yani düğme
      // her zaman gerekli — kalıcı kolon kalmadı.
      onOpenInspector={openInspector}
    />
  )
}

/**
 * `<main>` ya sohbeti ya açık artefaktı gösterir — FEATURE_SPEC §10.12.
 * Hangi görüntüleyicinin açılacağına `ArtifactViewer` karar verir (§11.9).
 *
 * Artefakt açıkken sohbet UNMOUNT edilmez, `hidden` ile gizlenir: aksi halde
 * artefakta bakıp geri dönmek sohbet geçmişini ve akış durumunu sıfırlardı
 * (sol panelin sekme kararının aynısı).
 */
function MainSlot(props: { lock: ChatLockReason | null; documentCount: number | undefined }) {
  const { open, close } = useArtifacts()
  return (
    <>
      <div hidden={open !== null} className="flex min-h-0 flex-1 flex-col">
        <ChatSlot {...props} />
      </div>
      {open !== null && <ArtifactViewer artifact={open} onClose={close} />}
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
      sidebar={
        <KnowledgeSidebar
          onUploadingChange={setUploading}
          // Artefakt listesi §13.2 ile sağ kolondan sol "Çıktılar"
          // sekmesine taşındı; sağ kolon artık alıntı çekmecesi.
          outputs={<StudioPanel />}
        />
      }
      chat={<MainSlot lock={lock} documentCount={documents?.length} />}
      inspector={<CitationDrawer />}
    >
      {/* Korpus boşken tam-ekran ilk açılış (§13.5 Faz 5). `documents === null`
          iken GÖSTERİLMEZ: liste henüz yüklenmedi, o anda basmak açılışta bir
          an "boş" yanıp sönmesine yol açardı. */}
      {documents !== null && documents.length === 0 && (
        <EmptyWorkspace onUploadingChange={setUploading} />
      )}
    </AppShell>
  )
}
