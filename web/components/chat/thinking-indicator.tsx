"use client"

import { SearchIcon, SparklesIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import type { ChatPhase } from "@/components/chat/chat-store"

/**
 * Aşamalı bekleme göstergesi — FEATURE_SPEC §1.2.
 *
 * İki aşama var ve ayrımı KULLANICIYA GÖRÜNÜR olmalı: `retrieval` olayı
 * (~0.3 sn) geldiğinde "aranıyor" -> "üretiliyor"a geçer. Bu geçiş, ilk
 * kelimeden (ölçülen TTFT 0.74 sn) yarım saniye önce sistemin canlı olduğunu
 * söyler; tek bir "yükleniyor" göstergesi bu bilgiyi kaybederdi.
 *
 * "Üretiliyor" aşaması `--accent` (AI/üretim göstergesi, DESIGN_SYSTEM.md
 * §1.1) rengini kullanır; "aranıyor" nötr kalır çünkü henüz model çalışmıyor.
 */
export interface ThinkingIndicatorProps {
  phase: Exclude<ChatPhase, "idle">
  className?: string
}

export function ThinkingIndicator({ phase, className }: ThinkingIndicatorProps) {
  const t = useT(chat)
  const searching = phase === "searching"
  const Icon = searching ? SearchIcon : SparklesIcon
  const label = searching ? t.phaseSearching : t.phaseGenerating

  return (
    <p
      role="status"
      aria-live="polite"
      data-phase={phase}
      className={cn(
        "flex items-center gap-2 text-body-sm",
        searching ? "text-text-secondary" : "text-accent",
        className
      )}
    >
      <Icon
        aria-hidden="true"
        className="size-3.5 animate-pulse motion-reduce:animate-none"
      />
      {label}
    </p>
  )
}
