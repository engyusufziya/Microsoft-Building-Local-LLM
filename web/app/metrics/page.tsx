"use client"

import Link from "next/link"
import { ArrowLeftIcon } from "lucide-react"

import { LanguageToggle } from "@/components/language-toggle"
import { MetricsPage } from "@/components/metrics"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"

/**
 * Değerlendirme sonuçları. Ana uygulamanın üç kolonlu düzeni burada
 * kullanılmıyor — bu tam genişlikte bir rapor sayfası.
 *
 * Veri `/api/metrics`'ten gelir ve backend `eval/results.json`'ı olduğu gibi
 * servis eder. Dosya üretilmemişse 503 + METRICS_NOT_GENERATED döner;
 * MetricsPage bu durumu ayırt edip "henüz çalıştırılmadı" ekranı gösterir --
 * sahte sayı basmaz.
 */
export default function Metrics() {
  const c = useT(common)

  return (
    <div className="flex min-h-full flex-col bg-background">
      <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-background/95 px-4 backdrop-blur-sm sm:px-6">
        <Button
          variant="ghost"
          size="sm"
          render={<Link href="/" />}
          className="gap-1.5"
        >
          <ArrowLeftIcon className="size-4" aria-hidden="true" />
          {c.back}
        </Button>
        <div className="flex items-center gap-1">
          <LanguageToggle />
          <ThemeToggle
            labels={{
              light: c.themeLight,
              dark: c.themeDark,
              system: c.themeSystem,
            }}
          />
        </div>
      </header>
      <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <MetricsPage />
      </main>
    </div>
  )
}
