"use client"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { sidebar as sidebarText } from "@/lib/i18n/sidebar"
import { Skeleton } from "@/components/ui/skeleton"

export interface CorpusStatsProps {
  /** `null` = sayı henüz bilinmiyor (iskelet gösterilir). */
  documentCount: number | null
  chunkCount: number | null
  pageCount: number | null
  className?: string
}

function Stat({ value, label }: { value: number | null; label: string }) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-0.5">
      {value === null ? (
        <Skeleton className="h-4 w-8" />
      ) : (
        <span className="font-mono text-body font-medium tabular-nums text-foreground">
          {value}
        </span>
      )}
      <span className="truncate text-caption text-text-secondary">{label}</span>
    </div>
  )
}

/**
 * Korpusun büyüklüğü: belge / bölüm (chunk) / sayfa.
 *
 * Sayılar belge listesinden TÜRETİLİR, `/api/health`'ten değil: liste her
 * yükleme ve silme sonrası tazeleniyor, health ise yoklamayla geliyor —
 * iki kaynak arasında geçici bir tutarsızlık kullanıcıya "sayı yanlış"
 * hissi verirdi. `page_count`/`chunk_count` zaten `DocumentInfo` içinde.
 */
function CorpusStats({
  documentCount,
  chunkCount,
  pageCount,
  className,
}: CorpusStatsProps) {
  const t = useT(sidebarText)

  return (
    <section
      aria-label={t.corpusTitle}
      className={cn(
        "grid grid-cols-3 gap-2 rounded-lg border border-border bg-surface-raised px-2 py-2.5",
        className
      )}
    >
      <Stat value={documentCount} label={t.corpusDocuments} />
      <Stat value={pageCount} label={t.corpusPages} />
      <Stat value={chunkCount} label={t.corpusChunks} />
    </section>
  )
}

export { CorpusStats }
