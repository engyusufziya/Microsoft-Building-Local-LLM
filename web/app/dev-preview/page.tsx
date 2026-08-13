"use client"

/**
 * GEÇİCİ doğrulama sayfası — design-system görevinin çıktısını backend/model
 * olmadan görsel olarak kontrol etmek için. app/page.tsx'e dokunulmadı.
 * `web/app/_dev-preview` DEĞİL `dev-preview` kullanıldı: Next.js 16'da
 * `_` önekli klasörler "private folder" sayılıp routing'den tamamen
 * çıkarılıyor (node_modules/next/dist/docs/01-app/01-getting-started/
 * 02-project-structure.md, "Private folders") — o isimle sayfa hiç
 * erişilebilir olmazdı.
 */

import * as React from "react"

import { ThemeProvider } from "@/components/theme-provider"
import { ThemeToggle } from "@/components/theme-toggle"
import { LanguageProvider, useLocale, useT } from "@/lib/i18n"
import { common } from "@/lib/i18n/common"
import { ScoreBadge } from "@/components/ui/score-badge"
import { RelevanceBar } from "@/components/ui/relevance-bar"
import { OcrBadge } from "@/components/ui/ocr-badge"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"

// Demo eşiği: gerçek backend olmadığı için rag/config.py::MIN_SCORE'un
// bugünkü değeriyle (0.45) aynı sayı burada SADECE prop olarak geçiliyor.
// ScoreBadge/RelevanceBar bu değeri hiçbir yerde hard-code etmiyor.
const DEMO_THRESHOLD = 0.45

const SCORE_SAMPLES = [0.82, 0.61, 0.5, 0.3]

function LocaleSwitcher() {
  const { locale, setLocale } = useLocale()
  const t = useT(common)
  return (
    <div className="flex items-center gap-2">
      <span className="text-caption font-medium text-muted-foreground">
        {t.languageLabel}
      </span>
      <Button
        variant={locale === "tr" ? "default" : "outline"}
        size="xs"
        onClick={() => setLocale("tr")}
      >
        TR
      </Button>
      <Button
        variant={locale === "en" ? "default" : "outline"}
        size="xs"
        onClick={() => setLocale("en")}
      >
        EN
      </Button>
    </div>
  )
}

function CommonTextsDemo() {
  const t = useT(common)
  return (
    <div className="flex flex-wrap gap-2 text-body-sm text-text-secondary">
      <span>{t.retry}</span>
      <span>·</span>
      <span>{t.errorGeneric}</span>
      <span>·</span>
      <span>{t.itemCount(3)}</span>
      <span>·</span>
      <span>{t.itemCount(1)}</span>
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-h2 font-semibold text-foreground">{title}</h2>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  )
}

function PreviewBody() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-10">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-display font-semibold text-foreground">
            Design System Preview
          </h1>
          <p className="text-body text-text-secondary">
            docs/DESIGN_SYSTEM.md token katmanı + primitive doğrulaması
            (geçici sayfa)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <Section title="Tipografi ölçeği (§2.2)">
        <p className="text-display font-semibold text-foreground">
          Display 30/36 · 600
        </p>
        <p className="text-h1 font-semibold text-foreground">H1 24/32 · 600</p>
        <p className="text-h2 font-semibold text-foreground">H2 18/28 · 600</p>
        <p className="text-h3 font-semibold text-foreground">H3 15/22 · 600</p>
        <p className="text-body text-foreground">Body 14/22 · 400</p>
        <p className="text-body-sm text-foreground">Body small 13/20 · 400</p>
        <p className="text-caption font-medium text-text-secondary">
          CAPTION 12/16 · 500
        </p>
        <p className="font-mono text-mono font-medium text-text-secondary">
          MONO 12/16 · 500 — 0.72
        </p>
      </Section>

      <Separator />

      <Section title="ScoreBadge — dört bant (§1.2)">
        <div className="flex flex-wrap items-center gap-3">
          {SCORE_SAMPLES.map((score) => (
            <ScoreBadge key={score} score={score} threshold={DEMO_THRESHOLD} />
          ))}
        </div>
        <p className="text-caption text-text-tertiary">
          Eşik (elendi sınırı) prop olarak geçirildi: {DEMO_THRESHOLD} — koda
          gömülü değil.
        </p>
      </Section>

      <Section title="RelevanceBar">
        <div className="flex flex-col gap-3">
          {SCORE_SAMPLES.map((score) => (
            <div key={score} className="flex items-center gap-3">
              <span className="w-10 shrink-0 font-mono text-mono text-text-secondary">
                {score.toFixed(2)}
              </span>
              <RelevanceBar score={score} threshold={DEMO_THRESHOLD} />
            </div>
          ))}
        </div>
      </Section>

      <Section title="OcrBadge (§1.3)">
        <div className="flex items-center gap-2">
          <OcrBadge />
          <OcrBadge label="OCR ile okundu" />
          <span className="text-body-sm text-text-secondary">
            Skordan bağımsız, her zaman aynı renk.
          </span>
        </div>
      </Section>

      <Separator />

      <Section title="Button varyantları">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="default">Default</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="xs">XS</Button>
          <Button size="sm">SM</Button>
          <Button size="default">Default</Button>
          <Button size="lg">LG</Button>
        </div>
      </Section>

      <Section title="Badge varyantları">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default">Default</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="destructive">Destructive</Badge>
          <Badge variant="outline">Outline</Badge>
          <Badge variant="ghost">Ghost</Badge>
        </div>
      </Section>

      <Section title="Card / Skeleton / Tooltip / Dialog">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Kart başlığı</CardTitle>
            <CardDescription>
              radius-lg (12px), surface zemin, ring-foreground/10.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </CardContent>
          <CardFooter className="justify-between">
            <Tooltip>
              <TooltipTrigger render={<Button variant="ghost" size="sm" />}>
                Tooltip&apos;li buton
              </TooltipTrigger>
              <TooltipContent>Base UI tooltip, delay=200</TooltipContent>
            </Tooltip>
            <Dialog>
              <DialogTrigger render={<Button size="sm" />}>
                Dialog aç
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>radius-xl (16px)</DialogTitle>
                  <DialogDescription>
                    Modal her zaman radius-xl kullanır, kart radius-lg.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter showCloseButton />
              </DialogContent>
            </Dialog>
          </CardFooter>
        </Card>
      </Section>

      <Separator />

      <Section title="i18n — useT(common) canlı örnek">
        <CommonTextsDemo />
      </Section>
    </div>
  )
}

export default function DevPreviewPage() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <PreviewBody />
      </LanguageProvider>
    </ThemeProvider>
  )
}
