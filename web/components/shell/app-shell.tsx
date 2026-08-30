"use client"

import * as React from "react"
import { PanelLeftIcon, PanelRightIcon, XIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"

import { AppShellProvider, type AppShellContextValue } from "./app-shell-context"
import { useBreakpoint } from "./use-breakpoint"

export interface AppShellProps {
  /** Belge yönetimi paneli (`components/sidebar/**`). */
  sidebar: React.ReactNode
  /** Sohbet bölgesi — içeriği `frontend-chat` yazar, burası yalnızca yerleşim. */
  chat: React.ReactNode
  /** Retrieval inspector — içeriği `frontend-chat` yazar. */
  inspector: React.ReactNode
  /** Başlık çubuğunun sol tarafı (uygulama adı/logo). Entegrasyon doldurur. */
  brand?: React.ReactNode
  /** Başlık çubuğunun sağ tarafı (tema/dil düğmeleri). Entegrasyon doldurur. */
  headerActions?: React.ReactNode
  /** Mobil drawer başlığı; verilmezse sidebar namespace'inden gelir. */
  sidebarTitle?: string
  /**
   * Inspector drawer başlığı. Varsayılan `sidebar.sourcesPanelTitle`;
   * `frontend-chat` kendi namespace'inden (`chat.ts`) geçirebilir.
   */
  inspectorTitle?: string
  /** Kontrollü kullanım: inspector drawer'ı dışarıdan yönetmek için. */
  inspectorOpen?: boolean
  onInspectorOpenChange?: (open: boolean) => void
  className?: string
}

/**
 * DESIGN_SYSTEM.md §4'teki üç kolonlu düzen.
 *
 * | | Genişlik | Sidebar | Chat | Alıntı çekmecesi |
 * |---|---|---|---|---|
 * | Mobile  | < 768px    | `Sheet` drawer | tam genişlik | `Sheet` drawer |
 * | Tablet  | 768–1279px | kalıcı 272px   | esnek        | `Sheet` drawer |
 * | Desktop | ≥ 1280px   | kalıcı 272px   | esnek, min 480px | `Sheet` drawer |
 *
 * Sağ kolon v3'te KALICI DEĞİL (§13.2): çekmece bağlama duyarlıdır ve
 * masaüstünde de üstte açılır.
 *
 * Bölgeler slot prop'u olarak alınır: bu bileşen sohbetin ya da
 * inspector'ın İÇERİĞİNİ bilmez, yalnızca nereye konacağını bilir.
 *
 * Her slot aynı anda TEK bir yerde render edilir (kalıcı kolon ya da
 * drawer); `hidden`/`block` ile iki kopya tutulmaz, çünkü bu bileşenleri
 * iki kez mount ederdi (bkz. use-breakpoint.ts).
 */
function AppShell({
  sidebar,
  chat,
  inspector,
  brand,
  headerActions,
  sidebarTitle,
  inspectorTitle,
  inspectorOpen: inspectorOpenProp,
  onInspectorOpenChange,
  className,
}: AppShellProps) {
  const t = useT(sidebarText)
  const breakpoint = useBreakpoint()

  const isSidebarOverlay = breakpoint === "mobile"

  const [sidebarOpen, setSidebarOpen] = React.useState(false)
  const [uncontrolledInspectorOpen, setUncontrolledInspectorOpen] =
    React.useState(false)

  const inspectorOpen = inspectorOpenProp ?? uncontrolledInspectorOpen
  const setInspectorOpen = React.useCallback(
    (open: boolean) => {
      if (inspectorOpenProp === undefined) setUncontrolledInspectorOpen(open)
      onInspectorOpenChange?.(open)
    },
    [inspectorOpenProp, onInspectorOpenChange]
  )

  const contextValue = React.useMemo<AppShellContextValue>(
    () => ({
      breakpoint,
      isSidebarOverlay,
      // v3'te sağ kolon KALICI DEĞİL (FEATURE_SPEC §13.2): alıntı çekmecesi
      // bağlama duyarlıdır, bir numaraya basınca açılır — masaüstünde de.
      // Kırılıma bakmadığı için sabit; tüketiciler (sohbetin "kaynakları
      // incele" düğmesi) sözleşmeyi değiştirmeden okumaya devam eder.
      isInspectorOverlay: true,
      sidebarOpen,
      setSidebarOpen,
      openSidebar: () => setSidebarOpen(true),
      closeSidebar: () => setSidebarOpen(false),
      inspectorOpen,
      setInspectorOpen,
      openInspector: () => setInspectorOpen(true),
      closeInspector: () => setInspectorOpen(false),
    }),
    [
      breakpoint,
      isSidebarOverlay,
      sidebarOpen,
      inspectorOpen,
      setInspectorOpen,
    ]
  )

  const resolvedSidebarTitle = sidebarTitle ?? t.panelTitle
  const resolvedInspectorTitle = inspectorTitle ?? t.sourcesPanelTitle

  return (
    <AppShellProvider value={contextValue}>
      <div
        data-slot="app-shell"
        data-breakpoint={breakpoint}
        className={cn(
          "flex h-dvh min-h-0 w-full flex-col overflow-hidden bg-background text-foreground",
          className
        )}
      >
        {/* data-print="hide": yazdırma sözleşmesi (FEATURE_SPEC §10.12) —
            kabuğun denetimleri kâğıda basılmaz, yalnızca artefakt basılır. */}
        <header
          data-print="hide"
          className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface px-3 md:px-4"
        >
          {isSidebarOverlay && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t.openDocuments}
              onClick={() => setSidebarOpen(true)}
            >
              <PanelLeftIcon />
            </Button>
          )}
          <div className="flex min-w-0 flex-1 items-center gap-2">{brand}</div>
          <div className="flex shrink-0 items-center gap-1">
            {headerActions}
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t.openSources}
              onClick={() => setInspectorOpen(true)}
            >
              <PanelRightIcon />
            </Button>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          {/* 272px — mockup'ın sol panel genişliği. v2'de 240/260px'ti;
              §13.2 ile artefakt listesi de bu kolona girdiği için tek ve
              daha geniş bir değere sabitlendi. */}
          {!isSidebarOverlay && (
            <aside
              data-print="hide"
              aria-label={t.regionDocuments}
              className="flex h-full w-68 shrink-0 flex-col overflow-hidden border-r-2 border-border bg-surface"
            >
              {sidebar}
            </aside>
          )}

          {/* Chat esnek; masaüstünde 480px'in altına inmez. */}
          <main
            aria-label={t.regionChat}
            className="flex h-full min-w-0 flex-1 flex-col overflow-hidden xl:min-w-120"
          >
            {chat}
          </main>

        </div>

        {isSidebarOverlay && (
          <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
            <SheetContent
              data-print="hide"
              side="left"
              showCloseButton={false}
              className="gap-0 p-0 data-[side=left]:w-[86vw] data-[side=left]:sm:max-w-80"
            >
              <SheetHeader className="flex-row items-center justify-between gap-2 border-b border-border p-3">
                <SheetTitle>{resolvedSidebarTitle}</SheetTitle>
                <SheetClose
                  render={
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t.closeDocuments}
                    />
                  }
                >
                  <XIcon />
                </SheetClose>
              </SheetHeader>
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                {sidebar}
              </div>
            </SheetContent>
          </Sheet>
        )}

        <Sheet open={inspectorOpen} onOpenChange={setInspectorOpen}>
          <SheetContent
            data-print="hide"
            side="right"
            showCloseButton={false}
            className="gap-0 p-0 data-[side=right]:w-[86vw] data-[side=right]:sm:max-w-100"
          >
            <SheetHeader className="flex-row items-center justify-between gap-2 border-b-2 border-border p-3">
              <SheetTitle>{resolvedInspectorTitle}</SheetTitle>
              <SheetClose
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t.closeSources}
                  />
                }
              >
                <XIcon />
              </SheetClose>
            </SheetHeader>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {inspector}
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </AppShellProvider>
  )
}

export { AppShell }
