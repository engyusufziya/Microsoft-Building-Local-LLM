"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import { Button } from "@/components/ui/button"
import { RetrievalInspector } from "@/components/inspector"
import { StudioPanel } from "./studio-panel"

/**
 * Sağ panelin "Kaynaklar | Studio" sekme anahtarı — docs/FEATURE_SPEC.md
 * §9.9.3. `AppShell`'in `inspector` slotuna verilen TEK bileşen budur
 * (`web/app/page.tsx`); `AppShell` dosyasının kendisi değişmez.
 *
 * İki sekme için `web/components/ui/` altına yeni bir `Tabs` primitifi
 * eklenmez (AGENTS.md §2.2 -- tek kullanımlık soyutlama). Bunun yerine
 * mevcut `Button` ile kurulan iki düğmelik bir segment denetimi,
 * WAI-ARIA tabs deseninin gerektirdiği role/aria/klavye davranışını elle
 * sağlar:
 *   - kapsayıcı `role="tablist"`, her düğme `role="tab"` + `aria-selected`
 *     + `aria-controls`
 *   - her panel `role="tabpanel"` + `aria-labelledby`
 *   - ok tuşlarıyla gezinme (roving tabindex: yalnızca seçili sekme
 *     `tabIndex=0`) + `Home`/`End`
 *   - odak, `Button`'ın kendi `focus-visible` halkasından gelir
 *
 * Sekme değişimi yalnızca bu paneli etkiler; `<main>` (sohbet) hiç
 * yeniden render olmaz. Her iki panel de her zaman mount'lu kalır ve
 * `hidden` ile gizlenir -- aksi halde Studio sekmesine geçip geri dönmek
 * Inspector'ın kaydırma/vurgu durumunu sıfırlardı.
 */

type RightPanelTab = "sources" | "studio"

export interface RightPanelTabsProps {
  className?: string
}

export function RightPanelTabs({ className }: RightPanelTabsProps) {
  const t = useT(studio)
  const [active, setActive] = React.useState<RightPanelTab>("sources")

  const sourcesTabId = React.useId()
  const studioTabId = React.useId()
  const sourcesPanelId = React.useId()
  const studioPanelId = React.useId()

  const sourcesButtonRef = React.useRef<HTMLButtonElement | null>(null)
  const studioButtonRef = React.useRef<HTMLButtonElement | null>(null)

  const focusAndSelect = React.useCallback((tab: RightPanelTab) => {
    setActive(tab)
    const target = tab === "sources" ? sourcesButtonRef.current : studioButtonRef.current
    target?.focus()
  }, [])

  const handleKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      switch (event.key) {
        case "ArrowRight":
        case "ArrowLeft":
          event.preventDefault()
          focusAndSelect(active === "sources" ? "studio" : "sources")
          break
        case "Home":
          event.preventDefault()
          focusAndSelect("sources")
          break
        case "End":
          event.preventDefault()
          focusAndSelect("studio")
          break
        default:
          break
      }
    },
    [active, focusAndSelect]
  )

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <div
        role="tablist"
        aria-label={t.tabListLabel}
        onKeyDown={handleKeyDown}
        className="flex shrink-0 items-center gap-1 border-b border-border px-3 py-2"
      >
        <Button
          ref={sourcesButtonRef}
          type="button"
          id={sourcesTabId}
          role="tab"
          aria-selected={active === "sources"}
          aria-controls={sourcesPanelId}
          tabIndex={active === "sources" ? 0 : -1}
          variant={active === "sources" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActive("sources")}
        >
          {t.sourcesTab}
        </Button>
        <Button
          ref={studioButtonRef}
          type="button"
          id={studioTabId}
          role="tab"
          aria-selected={active === "studio"}
          aria-controls={studioPanelId}
          tabIndex={active === "studio" ? 0 : -1}
          variant={active === "studio" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActive("studio")}
        >
          {t.studioTab}
        </Button>
      </div>

      <div
        id={sourcesPanelId}
        role="tabpanel"
        aria-labelledby={sourcesTabId}
        hidden={active !== "sources"}
        className="flex min-h-0 flex-1 flex-col"
      >
        <RetrievalInspector />
      </div>
      <div
        id={studioPanelId}
        role="tabpanel"
        aria-labelledby={studioTabId}
        hidden={active !== "studio"}
        className="flex min-h-0 flex-1 flex-col"
      >
        <StudioPanel />
      </div>
    </div>
  )
}
