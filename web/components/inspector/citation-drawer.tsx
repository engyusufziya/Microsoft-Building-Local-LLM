"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { chat } from "@/lib/i18n/chat"
import { pageImageUrl } from "@/lib/api"
import type { DocumentInfo } from "@/lib/types"
import {
  chatActions,
  selectedAssistant,
  useChatState,
} from "@/components/chat/chat-store"
import { middleTruncate } from "@/components/chat/citation"
import { useKnowledge } from "@/components/sidebar"
import { RetrievalInspector } from "./retrieval-inspector"

/**
 * Bağlama duyarlı alıntı çekmecesi — FEATURE_SPEC §13.2 · §13.4.
 *
 * Üç şey gösterir: (a) sayfa görüntüsü, (b) alıntılanan bölüm, (c) künye
 * `s.4 · bölüm 12/94 · benzerlik 0.71`.
 *
 * ÖNEMLİ — "benzerlik" HAM COSINE'dır (`ChunkHit.score`, AGENTS.md §1.1).
 * Yeniden ölçeklenmez, yüzdeye çevrilmez, güven bandından geri türetilmez.
 *
 * SPEC DÜZELTMESİ (§13.4'ün "önce/vurgu/sonra"sı): veri modelinde chunk'ın
 * İÇİNDE bir alt-aralık yok -- retrieval'ın birimi chunk'ın kendisi. Bu
 * yüzden bölümün TAMAMI alıntı olarak gösterilir; yapay bir "vurgulu cümle"
 * uydurmak, sahte sayı göstermemenin metinsel karşılığı olurdu. Önce/sonra
 * bağlamı komşu chunk'ları gerektirirdi (yeni bir veri yolu) -- görsel
 * kazancı bu turda karşılamıyor.
 *
 * `RetrievalInspector` ALTTA KALIR: §13.2 "davranış korunur, yalnızca yer
 * değişir" diyor. Yalnızca tek alıntıyı göstermek §4.3'ün eşik çizgisini ve
 * "neyin neden elendiğini" kaybettirirdi -- açıklanabilirlik bu ürünün farkı.
 */
export interface CitationDrawerProps {
  className?: string
}

/**
 * Belgenin kaynak PDF'i saklı mı — API'nin `has_page_images` alanı (§13.4).
 *
 * Liste henüz yüklenmediyse (`null`) istek YAPILMAZ: bilmeden istemek,
 * kaçınmak istediğimiz 404'ü geri getirirdi.
 */
function hasPageImages(
  documents: DocumentInfo[] | null,
  source: string
): boolean {
  return documents?.some((d) => d.filename === source && d.has_page_images) ?? false
}

export function CitationDrawer({ className }: CitationDrawerProps) {
  const t = useT(chat)
  const state = useChatState()
  // Aynı store örneği (ek istek yok): belgenin sayfa görüntüsü kaynağı var mı?
  const { documents } = useKnowledge()
  const message = selectedAssistant(state)
  const hits = message?.retrieval?.hits ?? []

  // Odak yoksa ilk alıntı gösterilir: çekmece açıldığında boş durmaz.
  const focused = state.focusedChunk
  const focusedIndex =
    focused !== null && focused.messageId === message?.id
      ? focused.chunkIndex
      : hits.length > 0
        ? 0
        : -1
  const hit = focusedIndex >= 0 ? hits[focusedIndex] : undefined

  return (
    <div
      data-slot="citation-drawer"
      className={cn("flex h-full min-h-0 flex-col overflow-y-auto", className)}
    >
      {hit === undefined ? (
        <p className="p-4 text-body-sm text-text-secondary">{t.noCitationSelected}</p>
      ) : (
        <>
          <div className="flex shrink-0 items-start gap-2.5 border-b-2 border-border p-4">
            <span className="mt-0.5 shrink-0 bg-primary px-1.5 font-semibold text-mono text-primary-foreground tabular-nums">
              {focusedIndex + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-body-sm font-semibold text-text-primary">
                {middleTruncate(hit.source, 34)}
              </p>
              <p
                data-slot="citation-meta"
                className="mt-0.5 font-mono text-mono text-text-secondary tabular-nums"
              >
                {hit.page > 0 && hit.chunk_index !== null && hit.chunk_total !== null
                  ? t.citationMeta(
                      hit.page,
                      hit.chunk_index,
                      hit.chunk_total,
                      hit.score
                    )
                  : t.citationMetaScoreOnly(hit.score)}
              </p>
            </div>
          </div>

          {hit.page > 0 && hasPageImages(documents, hit.source) && (
            <PageImage
              // `key` ile remount: alıntı değişince "yüklenemedi" durumu
              // effect'le sıfırlanmak yerine bileşenle birlikte düşer.
              key={`${hit.source}#${hit.page}`}
              source={hit.source}
              page={hit.page}
              label={t.pageImageLabel(hit.page)}
              missing={t.pageImageMissing}
            />
          )}

          <div className="border-b border-border p-4">
            <p className="mb-2.5 text-caption font-medium tracking-[0.08em] text-text-secondary uppercase">
              {t.citedPassage}
            </p>
            <p className="border-b-2 border-primary bg-primary/15 p-2 text-body-sm leading-relaxed text-text-primary">
              {hit.content}
            </p>
          </div>

          {hits.length > 1 && (
            <div className="flex shrink-0 items-center gap-2.5 border-b border-border p-3">
              <span className="shrink-0 text-caption text-text-secondary">
                {t.otherCitations}
              </span>
              <div className="flex flex-wrap gap-1">
                {hits.map((other, index) => (
                  <button
                    key={other.citation + index}
                    type="button"
                    aria-label={t.openCitation(index + 1)}
                    aria-current={index === focusedIndex}
                    onClick={() =>
                      message && chatActions.focusSource(message.id, other.citation)
                    }
                    className={cn(
                      "cursor-pointer border px-1.5 font-mono text-mono tabular-nums",
                      "transition-colors duration-(--duration-hover) ease-(--ease-standard)",
                      "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                      index === focusedIndex
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border text-text-secondary hover:border-primary hover:text-text-primary"
                    )}
                  >
                    {index + 1}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Eşik çizgisi, elenen chunk'lar ve skor bantları BURADA yaşamaya
          devam eder (§4.3) -- çekmece tek alıntıyı öne çıkarır, ama
          açıklanabilirliği yerine koymaz. */}
      <RetrievalInspector className="min-h-0 flex-1" />
    </div>
  )
}

/**
 * Sayfa görüntüsü. `<img>` ile yüklenir (fetch değil): tarayıcı önbelleği ve
 * ilerlemeli çözümleme bedava gelir. 404 -- belge bu özellikten ÖNCE
 * yüklenmişse olur -- sessizce yutulmaz, açıklanır (§13.4 geriye dönük sınır).
 */
function PageImage({
  source,
  page,
  label,
  missing,
}: {
  source: string
  page: number
  label: string
  missing: string
}) {
  // Görüntü `<img src>` ile DEĞİL `fetch` ile alınır.
  //
  // Gerekçe ölçüldü: kaynağı saklanmamış bir belgede uç 404 döner (§13.4
  // geriye dönük sınır) ve `<img>` bunu KONSOLA HATA olarak yazar. Bu normal
  // bir durum, hata değil -- `ui_proof`'un "konsol hatası yok" kapısını
  // gereksiz yere kırıyordu. `fetch` 404'ü sessizce çözer, biz de açıklayıcı
  // metni gösteririz. Blob URL unmount'ta serbest bırakılır.
  const [src, setSrc] = React.useState<string | null>(null)
  const [failed, setFailed] = React.useState(false)

  React.useEffect(() => {
    let url: string | null = null
    let cancelled = false

    void fetch(pageImageUrl(source, page))
      .then((response) => (response.ok ? response.blob() : null))
      .then((blob) => {
        if (cancelled) return
        if (blob === null) {
          setFailed(true)
          return
        }
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })

    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [source, page])

  if (failed) {
    return (
      <p className="border-b border-border p-4 text-body-sm text-text-secondary">
        {missing}
      </p>
    )
  }

  return (
    <figure className="border-b border-border p-4">
      {/* `next/image` bu projede KULLANILAMAZ: `output: "export"` altında
          optimizasyon zaten devre dışı, ve kaynak çalışma anında üretilen bir
          blob URL -- statik bir varlık değil. */}
      {src !== null && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          data-slot="page-image"
          src={src}
          alt={label}
          className="w-full border border-border bg-surface"
        />
      )}
      <figcaption className="mt-1.5 font-mono text-mono text-text-tertiary">
        {label}
      </figcaption>
    </figure>
  )
}
