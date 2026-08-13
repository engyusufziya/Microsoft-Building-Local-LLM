"use client"

import * as React from "react"
import { useTheme } from "next-themes"
import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

type ThemeChoice = "light" | "dark" | "system"

const NEXT: Record<ThemeChoice, ThemeChoice> = {
  light: "dark",
  dark: "system",
  system: "light",
}

const ICON: Record<ThemeChoice, React.ComponentType<{ className?: string }>> = {
  light: SunIcon,
  dark: MoonIcon,
  system: MonitorIcon,
}

export interface ThemeToggleProps {
  className?: string
  /** Tooltip/aria metinleri; i18n'den geçirilir. Verilmezse İngilizce varsayılan. */
  labels?: Partial<Record<ThemeChoice, string>>
}

const DEFAULT_LABELS: Record<ThemeChoice, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
}

// next-themes'in kendi dokümantasyonu `theme`'in mount öncesi undefined
// olduğunu ve UI'ın mount sonrasına ertelenmesi gerektiğini söylüyor
// (bkz. next-themes README "Avoid Hydration Mismatch"). Klasik
// useState+useEffect deseni yerine useSyncExternalStore kullanıyoruz: aynı
// sonucu (SSR'da false, client mount sonrası true) effect içinde setState
// çağırmadan verir — bu projenin eslint kuralı (react-hooks/set-state-in-effect)
// bunu zorunlu kılıyor.
const emptySubscribe = () => () => {}
function useHasMounted() {
  return React.useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  )
}

/**
 * Light → dark → system → light döngüsünde tek butonla tema değiştirir.
 */
function ThemeToggle({ className, labels }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme()
  const mounted = useHasMounted()

  const current = (mounted ? (theme as ThemeChoice) : undefined) ?? "system"
  const Icon = ICON[current]
  const label = labels?.[current] ?? DEFAULT_LABELS[current]

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className={className}
            onClick={() => setTheme(NEXT[current])}
            aria-label={label}
          />
        }
      >
        <Icon className="size-4" />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

export { ThemeToggle }
