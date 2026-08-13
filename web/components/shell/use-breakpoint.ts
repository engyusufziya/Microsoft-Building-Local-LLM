"use client"

import * as React from "react"

/**
 * DESIGN_SYSTEM.md §4'teki üç kırılma noktası.
 *
 * Piksel değerleri Tailwind'in `md` (768) ve `xl` (1280) varsayılanlarıyla
 * BİREBİR aynıdır — layout'un CSS tarafı (`md:` / `xl:` varyantları) ile
 * JS tarafı (bu hook) aynı sınırı görmek zorunda, aksi halde bir aralıkta
 * hem kalıcı kolon hem drawer görünürdü.
 *
 * Neden JS ile ölçüyoruz? Aynı React düğümü (örn. `sidebar` slot'u) hem
 * kalıcı kolonda hem `Sheet` içinde CSS ile gösterilemez; iki yere birden
 * yazmak bileşeni İKİ KEZ mount eder (iki `listDocuments()` isteği, iki
 * ayrı yükleme kuyruğu). Bu yüzden yerleşim seçimi render zamanında
 * yapılır ve düğüm her zaman TEK bir yerde bulunur.
 */
export type Breakpoint = "mobile" | "tablet" | "desktop"

const TABLET_MIN_PX = 768
const DESKTOP_MIN_PX = 1280

const TABLET_QUERY = `(min-width: ${TABLET_MIN_PX}px)`
const DESKTOP_QUERY = `(min-width: ${DESKTOP_MIN_PX}px)`

function canMatchMedia(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
}

function subscribe(onStoreChange: () => void): () => void {
  if (!canMatchMedia()) return () => {}
  const lists = [
    window.matchMedia(TABLET_QUERY),
    window.matchMedia(DESKTOP_QUERY),
  ]
  for (const list of lists) list.addEventListener("change", onStoreChange)
  return () => {
    for (const list of lists) list.removeEventListener("change", onStoreChange)
  }
}

function getSnapshot(): Breakpoint {
  if (!canMatchMedia()) return "desktop"
  if (window.matchMedia(DESKTOP_QUERY).matches) return "desktop"
  if (window.matchMedia(TABLET_QUERY).matches) return "tablet"
  return "mobile"
}

/**
 * Statik export'ta (`output: "export"`) HTML build anında üretilir ve
 * `window` yoktur. Sunucu anlık görüntüsü "desktop": üretilen statik HTML
 * üç kolonlu tam yerleşimi içerir, JS yüklenmeden önce de doğru iskelet
 * görünür. Dar ekranda hydration sonrası ilk render'da düzeltilir.
 */
const getServerSnapshot = (): Breakpoint => "desktop"

/**
 * Aktif kırılma noktası. `useSyncExternalStore` bilinçli tercih:
 * `useState` + `useEffect` + `setState` deseni bu projenin eslint kuralına
 * (`react-hooks/set-state-in-effect`) takılır; aynı desen theme-toggle.tsx
 * ve lib/i18n/index.ts içinde de kullanılıyor.
 */
export function useBreakpoint(): Breakpoint {
  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
