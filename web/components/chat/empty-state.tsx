"use client"

import { FileUpIcon, MessageSquareTextIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import { Button } from "@/components/ui/button"

/**
 * Sohbetin iki boş durumu — FEATURE_SPEC §5 durum matrisi.
 *
 * "Belge yok" ile "belge var, soru yok" AYRI durumlardır ve farklı şey
 * söylerler: birincisi bir eylem ister (yükle), ikincisi ürünün nasıl
 * çalıştığını anlatır ve örnek soru önerir. Tek bir jenerik boş durum
 * kullanmak, ilk kullanımda kullanıcıyı ne yapacağını bilmez halde bırakırdı.
 */

export interface ChatEmptyStateProps {
  variant: "noDocuments" | "noQuestion"
  /** Örnek sorular; tıklanınca doğrudan sorulur. */
  suggestions?: string[]
  onSelectSuggestion?: (question: string) => void
  className?: string
}

export function ChatEmptyState({
  variant,
  suggestions,
  onSelectSuggestion,
  className,
}: ChatEmptyStateProps) {
  const t = useT(chat)
  const noDocuments = variant === "noDocuments"
  const Icon = noDocuments ? FileUpIcon : MessageSquareTextIcon
  const items = suggestions ?? [t.suggestion1, t.suggestion2, t.suggestion3]

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-6 py-10",
        className
      )}
    >
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <span className="flex size-10 items-center justify-center rounded-lg bg-muted text-text-secondary">
          <Icon aria-hidden="true" className="size-5" />
        </span>

        <div className="flex flex-col gap-1.5">
          <h2 className="text-h2 font-semibold text-foreground">
            {noDocuments ? t.emptyNoDocumentsTitle : t.emptyNoQuestionTitle}
          </h2>
          <p className="text-body text-text-secondary">
            {noDocuments ? t.emptyNoDocumentsBody : t.emptyNoQuestionBody}
          </p>
        </div>

        {!noDocuments && onSelectSuggestion && items.length > 0 && (
          <div className="flex flex-col items-center gap-2">
            <span className="text-caption font-medium text-text-tertiary">
              {t.suggestionsLabel}
            </span>
            <ul className="flex flex-wrap justify-center gap-2">
              {items.map((question) => (
                <li key={question}>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onSelectSuggestion(question)}
                  >
                    {question}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
