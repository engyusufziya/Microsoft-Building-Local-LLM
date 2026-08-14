"use client"

import * as React from "react"
import { AlertCircleIcon, PanelRightOpenIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import { common } from "@/lib/i18n/common"
import type { ApiErrorBody } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { StreamingText } from "@/components/chat/streaming-text"
import { SourceChips } from "@/components/chat/source-chips"
import { ThinkingIndicator } from "@/components/chat/thinking-indicator"
import {
  chatActions,
  type AssistantMessage,
  type ChatMessage,
  type ChatPhase,
} from "@/components/chat/chat-store"

/**
 * Mesaj geçmişi.
 *
 * Asistan mesajının GÖRÜNÜMÜ tek bir yerde, `outcome` alanına göre dallanır
 * (FEATURE_SPEC §3.2'deki üç `reason` + iki hata dalı). Bu dallanmanın tek
 * noktada durması bilinçli: üç sonucun ayrımı bu ürünün dürüstlük iddiası ve
 * dağıtılırsa sessizce tutarsızlaşır.
 */

function useErrorText() {
  const t = useT(chat)
  const c = useT(common)
  return React.useCallback(
    (error: ApiErrorBody | null): string => {
      if (!error) return c.errorGeneric
      switch (error.code) {
        case "NO_DOCUMENTS":
          return t.errorNoDocuments
        case "MODEL_WARMING":
          return t.errorModelWarming
        case "EMPTY_QUERY":
          return t.errorEmptyQuery
        default:
          return error.message || c.errorGeneric
      }
    },
    [t, c]
  )
}

function UserBubble({ text }: { text: string }) {
  const t = useT(chat)
  return (
    <div className="flex flex-col items-end gap-1">
      <span className="text-caption font-medium text-text-tertiary">
        {t.userLabel}
      </span>
      <p className="max-w-[85%] rounded-lg bg-primary px-3 py-2 text-body whitespace-pre-wrap text-primary-fg">
        {text}
      </p>
    </div>
  )
}

/** İki ret dalının ortak gövdesi: yerelleştirilmiş metin + neden açıklaması. */
function NoAnswerBody({ explanation }: { explanation: string }) {
  const t = useT(chat)
  return (
    <div className="flex flex-col gap-1">
      <p className="text-body text-foreground">{t.noAnswer}</p>
      <p className="text-body-sm text-text-secondary">{explanation}</p>
    </div>
  )
}

function AssistantBody({
  message,
  phase,
}: {
  message: AssistantMessage
  phase: ChatPhase
}) {
  const t = useT(chat)
  const c = useT(common)
  const errorText = useErrorText()

  switch (message.outcome) {
    case "streaming":
      // Henüz token gelmediyse aşamalı gösterge, geldiyse akan metin + imleç.
      return message.text ? (
        <StreamingText text={message.text} streaming />
      ) : (
        <ThinkingIndicator phase={phase === "idle" ? "searching" : phase} />
      )

    case "answered":
      return (
        <div className="flex flex-col gap-3">
          <StreamingText text={message.text} />
          <SourceChips messageId={message.id} sources={message.sources} />
        </div>
      )

    // Kısa devre: LLM hiç çağrılmadı, hiç token akmadı (~0.1 sn). Ölü bir
    // duvar yerine kurtarma eylemi sunulur: rag/query_router.py'nin özetleme
    // yoluna (Görev 1) giden sabit bir soru, aynı sohbet akışından gönderilir.
    case "below_threshold":
      return (
        <div className="flex flex-col gap-3">
          <NoAnswerBody explanation={t.noAnswerBelowThreshold} />
          <div className="flex flex-col items-start gap-1.5">
            <p className="text-body-sm text-text-secondary">
              {t.belowThresholdRecoveryHint}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => chatActions.ask(t.belowThresholdRecoveryAction)}
            >
              {t.belowThresholdRecoveryAction}
            </Button>
          </div>
        </div>
      )

    // Token AKTI ama modelin ham Türkçe ret metni yerelleştirilmişle
    // DEĞİŞTİRİLİR (FEATURE_SPEC §3.2 [!warning]); kaynak gösterilmez.
    case "llm_refused":
      return <NoAnswerBody explanation={t.noAnswerRefused} />

    // §5 [!tip]: kısmi metin korunur.
    case "incomplete":
      return (
        <StreamingText
          text={message.text}
          incomplete
          incompleteLabel={t.streamIncomplete}
          incompleteDetail={message.error ? errorText(message.error) : undefined}
        />
      )

    case "failed":
      return (
        <div className="flex flex-col gap-2 rounded-lg border border-danger/30 bg-danger/5 p-3">
          <p className="flex items-center gap-1.5 text-body font-medium text-danger">
            <AlertCircleIcon aria-hidden="true" className="size-4 shrink-0" />
            {t.errorTitle}
          </p>
          <p className="text-body-sm text-text-secondary">
            {errorText(message.error)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-fit"
            onClick={() => chatActions.retry()}
          >
            {c.retry}
          </Button>
        </div>
      )
  }
}

function AssistantBlock({
  message,
  phase,
  selected,
  onOpenInspector,
}: {
  message: AssistantMessage
  phase: ChatPhase
  selected: boolean
  onOpenInspector?: () => void
}) {
  const t = useT(chat)
  const showElapsed =
    message.elapsedMs !== null &&
    (message.outcome === "answered" ||
      message.outcome === "below_threshold" ||
      message.outcome === "llm_refused")

  return (
    <div
      data-selected={selected}
      className={cn(
        "flex flex-col gap-1 border-l-2 pl-3 transition-colors duration-(--duration-hover) ease-(--ease-standard)",
        selected ? "border-l-primary/40" : "border-l-transparent"
      )}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-caption font-medium text-text-tertiary">
          {t.assistantLabel}
        </span>
        {showElapsed && (
          <span className="font-mono text-mono text-text-tertiary tabular-nums">
            {t.elapsedSeconds(message.elapsedMs ?? 0)}
          </span>
        )}
      </div>

      <AssistantBody message={message} phase={phase} />

      {/* Mobil/tablet: Inspector kalıcı kolon değil, drawer
          (DESIGN_SYSTEM.md §4). Drawer'ın kendisi kabuk agent'ının;
          buradan yalnızca açma isteği gönderilir. */}
      {onOpenInspector && message.retrieval && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-1 w-fit xl:hidden"
          onClick={() => {
            chatActions.selectMessage(message.id)
            onOpenInspector()
          }}
        >
          <PanelRightOpenIcon />
          {t.openInspector}
        </Button>
      )}
    </div>
  )
}

export interface MessageListProps {
  messages: ChatMessage[]
  phase: ChatPhase
  /** Inspector'ın hangi mesajı gösterdiği — sol kenar çizgisiyle işaretlenir. */
  selectedMessageId: string | null
  onOpenInspector?: () => void
  className?: string
}

export function MessageList({
  messages,
  phase,
  selectedMessageId,
  onOpenInspector,
  className,
}: MessageListProps) {
  const scrollRef = React.useRef<HTMLDivElement | null>(null)
  // Kullanıcı yukarı kaydırdıysa akış onu aşağı ZORLAMAZ; sadece dibe
  // yapışıkken takip eder. Ref, çünkü bu bilgi render'ı etkilemiyor.
  const pinnedRef = React.useRef(true)

  React.useEffect(() => {
    const element = scrollRef.current
    if (element && pinnedRef.current) {
      element.scrollTop = element.scrollHeight
    }
  }, [messages, phase])

  return (
    <div
      ref={scrollRef}
      onScroll={(event) => {
        const element = event.currentTarget
        pinnedRef.current =
          element.scrollHeight - element.scrollTop - element.clientHeight < 48
      }}
      className={cn("min-h-0 flex-1 overflow-y-auto", className)}
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 sm:px-6">
        {messages.map((message) =>
          message.role === "user" ? (
            <UserBubble key={message.id} text={message.text} />
          ) : (
            <AssistantBlock
              key={message.id}
              message={message}
              phase={phase}
              selected={message.id === selectedMessageId}
              onOpenInspector={onOpenInspector}
            />
          )
        )}
      </div>
    </div>
  )
}
