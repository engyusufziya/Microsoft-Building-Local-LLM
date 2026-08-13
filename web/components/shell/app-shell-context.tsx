"use client"

import * as React from "react"

import type { Breakpoint } from "./use-breakpoint"

/**
 * AppShell'in yerleşim durumunu çocuklara açar.
 *
 * Neden gerekli: DESIGN_SYSTEM.md §4 "Mobilde Inspector'a erişim: her
 * asistan mesajının altındaki 'Kaynakları incele' butonu drawer'ı açar"
 * diyor. O buton `components/chat/**` altında (başka bir agent'ın dosyası)
 * yaşıyor ama açması gereken drawer AppShell'e ait. Prop drilling yerine
 * context: chat/inspector tarafı `useAppShell().openInspector()` çağırır,
 * AppShell'in iç durumunu bilmek zorunda kalmaz.
 */
export interface AppShellContextValue {
  breakpoint: Breakpoint
  /** <768px: sidebar bir `Sheet` drawer'ı (DESIGN_SYSTEM.md §4). */
  isSidebarOverlay: boolean
  /** <1280px: inspector bir overlay drawer; ≥1280px kalıcı kolon. */
  isInspectorOverlay: boolean
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  openSidebar: () => void
  closeSidebar: () => void
  inspectorOpen: boolean
  setInspectorOpen: (open: boolean) => void
  /**
   * Inspector'ı gösterir. Kalıcı kolon modunda (desktop) zaten görünür
   * olduğu için etkisizdir — çağıran tarafın breakpoint'i bilmesi gerekmez.
   */
  openInspector: () => void
  closeInspector: () => void
}

const AppShellContext = React.createContext<AppShellContextValue | null>(null)

export const AppShellProvider = AppShellContext.Provider

/**
 * AppShell dışında çağrılırsa `null` döner — bileşenini kendi önizleme
 * sayfasında (AppShell olmadan) render eden agent'lar için güvenli yol.
 */
export function useAppShellOptional(): AppShellContextValue | null {
  return React.useContext(AppShellContext)
}

/** AppShell içinde olmayı şart koşar (bkz. lib/i18n/index.ts::useLocale deseni). */
export function useAppShell(): AppShellContextValue {
  const ctx = useAppShellOptional()
  if (!ctx) {
    throw new Error("useAppShell() bir <AppShell> içinde kullanılmalı.")
  }
  return ctx
}
