"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import { ChatEmptyState } from "@/components/chat/empty-state"
import { ChatInput } from "@/components/chat/chat-input"
import { MessageList } from "@/components/chat/message-list"
import { chatActions, useChatState } from "@/components/chat/chat-store"

/**
 * Sohbet kolonu: geçmiş + boş durumlar + girdi.
 *
 * Durum `components/chat/chat-store.ts` içindeki modül düzeyinde store'da
 * durur; `RetrievalInspector` aynı store'u okuduğu için iki panel provider'a
 * gerek olmadan senkron kalır (gerekçe store dosyasının başında).
 *
 * DIŞARIDAN GELEN TEK BİLGİ KİLİT: yükleme sürüyor mu, modeller ısınıyor mu,
 * korpus boş mu — hepsi sidebar/health tarafının bilgisi. `lock` prop'u
 * verilmezse panel çalışır durumda kabul edilir.
 */

/** FEATURE_SPEC §5 durum matrisindeki kilit sebepleri. */
export type ChatLockReason =
  | "warming"
  | "uploading"
  | "noDocuments"
  | "modelError"

export interface ChatPanelProps {
  /** Kilit sebebi; `null`/verilmemiş = kilit yok. */
  lock?: ChatLockReason | null
  /**
   * Korpustaki belge sayısı. `0` ise "belge yok" boş durumu gösterilir.
   * Bilinmiyorsa (henüz `/api/health` gelmediyse) verilmez.
   */
  documentCount?: number
  /** Boş durumdaki örnek sorular; verilmezse i18n varsayılanları kullanılır. */
  suggestions?: string[]
  /** Mobil/tablet: Inspector drawer'ını açma isteği (kabuk agent'ı sağlar). */
  onOpenInspector?: () => void
  className?: string
}

export function ChatPanel({
  lock = null,
  documentCount,
  suggestions,
  onOpenInspector,
  className,
}: ChatPanelProps) {
  const t = useT(chat)
  const { messages, phase, selectedMessageId } = useChatState()

  const streaming = phase !== "idle"
  const effectiveLock: ChatLockReason | "busy" | null = lock ?? (streaming ? "busy" : null)

  const lockReasonText = React.useMemo(() => {
    switch (effectiveLock) {
      case "warming":
        return t.lockWarming
      case "uploading":
        return t.lockUploading
      case "noDocuments":
        return t.lockNoDocuments
      case "modelError":
        return t.lockModelError
      case "busy":
        return t.lockBusy
      default:
        return undefined
    }
  }, [effectiveLock, t])

  // "Belge yok" hem boş durumu hem kilidi belirler; ikisi aynı gerçeğin
  // iki yüzü (§5: "Boş durum, girdi kilitli").
  const noDocuments = documentCount === 0 || lock === "noDocuments"
  const canAsk = effectiveLock === null

  return (
    <section
      aria-label={t.panelTitle}
      className={cn("flex h-full min-h-0 flex-col", className)}
    >
      {messages.length === 0 ? (
        <ChatEmptyState
          variant={noDocuments ? "noDocuments" : "noQuestion"}
          suggestions={suggestions}
          onSelectSuggestion={canAsk ? (question) => chatActions.ask(question) : undefined}
        />
      ) : (
        <MessageList
          messages={messages}
          phase={phase}
          selectedMessageId={selectedMessageId}
          onOpenInspector={onOpenInspector}
        />
      )}

      <div className="border-t border-border bg-background px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <ChatInput
            onSubmit={(question) => chatActions.ask(question)}
            disabled={!canAsk}
            disabledReason={lockReasonText}
          />
        </div>
      </div>
    </section>
  )
}
