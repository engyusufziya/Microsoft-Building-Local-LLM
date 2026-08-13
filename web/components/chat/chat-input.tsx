"use client"

import * as React from "react"
import { ArrowUpIcon, LockIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import { Button } from "@/components/ui/button"

/**
 * Soru girdisi — FEATURE_SPEC §1.2, §5.
 *
 * KİLİT DURUMU PROP OLARAK GELİR. Yükleme sürüyor mu, modeller hâlâ ısınıyor
 * mu, korpus boş mu — bunların hepsi sidebar/health tarafının bilgisi ve
 * `frontend-chat`'in görebileceği bir şey değil. Bileşen yalnızca "kilitli mi"
 * ve "sebebi ne" bilgisini alır; sebebi HER ZAMAN yazar (§1.1 [!important]:
 * kilidi sessizce uygulamak kullanıcıyı tıkanmış hissettirir).
 *
 * Gönderme kısayolu ⌘/Ctrl + Enter. Düz Enter satır atlar: sorular çok
 * satırlı olabiliyor ve yanlışlıkla gönderim, 3 saniyelik bir akışı ve model
 * kilidini boşa harcar.
 */

const MAX_HEIGHT_PX = 200

const emptySubscribe = () => () => {}

/**
 * Kısayol ipucunun platforma göre yazılması. Mount öncesi (SSR/statik export)
 * `false` döner — `useSyncExternalStore` ile, effect içinde setState
 * çağırmadan (`react-hooks/set-state-in-effect`).
 */
function useIsApplePlatform() {
  return React.useSyncExternalStore(
    emptySubscribe,
    () => /Mac|iPhone|iPad|iPod/.test(navigator.userAgent),
    () => false
  )
}

function autoGrow(element: HTMLTextAreaElement | null) {
  if (!element) return
  element.style.height = "auto"
  element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT_PX)}px`
  element.style.overflowY =
    element.scrollHeight > MAX_HEIGHT_PX ? "auto" : "hidden"
}

export interface ChatInputProps {
  onSubmit: (question: string) => void
  /** Girdi kilitli mi. */
  disabled?: boolean
  /** Kilit sebebi — yerelleştirilmiş metin, çağıran taraf verir. */
  disabledReason?: string
  className?: string
}

export function ChatInput({
  onSubmit,
  disabled = false,
  disabledReason,
  className,
}: ChatInputProps) {
  const t = useT(chat)
  const isApple = useIsApplePlatform()
  const [value, setValue] = React.useState("")
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null)
  const reasonId = React.useId()

  const canSend = value.trim().length > 0 && !disabled

  function submit() {
    if (!canSend) return
    onSubmit(value.trim())
    setValue("")
    // Değer sıfırlandı; yükseklik de tek satıra dönmeli.
    requestAnimationFrame(() => autoGrow(textareaRef.current))
  }

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
        className={cn(
          "flex items-end gap-2 rounded-lg border border-border-strong bg-surface-raised p-2",
          "transition-colors duration-(--duration-hover) ease-(--ease-standard)",
          "focus-within:border-primary focus-within:ring-3 focus-within:ring-ring/50",
          disabled && "opacity-60"
        )}
      >
        <textarea
          ref={(element) => {
            textareaRef.current = element
            autoGrow(element)
          }}
          rows={1}
          value={value}
          disabled={disabled}
          aria-label={t.inputPlaceholder}
          aria-describedby={disabled && disabledReason ? reasonId : undefined}
          placeholder={t.inputPlaceholder}
          onChange={(event) => {
            setValue(event.target.value)
            autoGrow(event.currentTarget)
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault()
              submit()
            }
          }}
          className="max-h-[200px] flex-1 resize-none bg-transparent px-1 py-1 text-body text-foreground placeholder:text-text-tertiary focus-visible:outline-none disabled:cursor-not-allowed"
        />
        <Button
          type="submit"
          size="icon-sm"
          disabled={!canSend}
          aria-label={t.send}
          className="shrink-0"
        >
          <ArrowUpIcon />
        </Button>
      </form>

      {disabled && disabledReason ? (
        <p
          id={reasonId}
          role="status"
          className="flex items-start gap-1.5 text-caption text-text-secondary"
        >
          <LockIcon aria-hidden="true" className="mt-px size-3 shrink-0" />
          {disabledReason}
        </p>
      ) : (
        <p className="text-caption text-text-tertiary">
          {isApple ? t.sendHintMac : t.sendHintOther}
        </p>
      )}
    </div>
  )
}
