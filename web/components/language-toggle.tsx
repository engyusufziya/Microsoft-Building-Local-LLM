"use client"

import { LanguagesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { common } from "@/lib/i18n/common"
import { useLocale, useT } from "@/lib/i18n"

/**
 * TR ↔ EN arasında geçiş yapar.
 *
 * `theme-toggle.tsx` ile aynı desen; dil tercihi `LanguageProvider` içinde
 * localStorage'a yazılır. Hidrasyon uyumsuzluğu riski yok: `useLocale`
 * `useSyncExternalStore` üzerine kurulu ve sunucu anlık görüntüsü her zaman
 * varsayılan dili döndürüyor (bkz. lib/i18n/index.ts).
 */
export function LanguageToggle({ className }: { className?: string }) {
  const { locale, setLocale } = useLocale()
  const t = useT(common)
  const next = locale === "tr" ? "en" : "tr"

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={className}
            onClick={() => setLocale(next)}
            aria-label={`${t.languageLabel}: ${locale.toUpperCase()}`}
          />
        }
      >
        <LanguagesIcon className="size-4" aria-hidden="true" />
        <span className="font-medium tabular-nums">{locale.toUpperCase()}</span>
      </TooltipTrigger>
      <TooltipContent>
        {t.languageLabel}: {next.toUpperCase()}
      </TooltipContent>
    </Tooltip>
  )
}
