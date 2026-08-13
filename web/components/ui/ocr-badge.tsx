import * as React from "react"
import { ScanTextIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export interface OcrBadgeProps
  extends Omit<React.ComponentProps<"span">, "children"> {
  /** Rozet metni; i18n'den geçirilir (örn. t.chat.ocrBadge). Verilmezse "OCR". */
  label?: string
}

/**
 * DESIGN_SYSTEM.md §1.3 — `--ocr-badge` skordan BAĞIMSIZ bir token: OCR
 * kaynaklı metin tanım gereği daha az güvenilir, kullanıcı bunu retrieval
 * skorundan ayrı görmeli. Bu yüzden bu bileşen `ScoreBadge`'in bant
 * renklerini asla kullanmaz — sabit `--ocr-badge` rengiyle çalışır.
 */
function OcrBadge({ label = "OCR", className, ...props }: OcrBadgeProps) {
  return (
    <span
      data-slot="ocr-badge"
      className={cn(
        "inline-flex h-5 w-fit shrink-0 items-center gap-1 rounded-sm border border-transparent bg-ocr-badge/10 px-1.5 py-0.5 text-caption leading-none font-medium text-ocr-badge",
        className
      )}
      {...props}
    >
      <ScanTextIcon aria-hidden="true" className="size-3" />
      {label}
    </span>
  )
}

export { OcrBadge }
