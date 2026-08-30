"use client"

import * as React from "react"
import Markdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"
import { CodeBlock } from "@/components/chat/code-block"
import { scanCitations } from "@/components/chat/citation"

/**
 * Asistan cevabının markdown gösterimi (tablo/liste/kod).
 *
 * `remark-gfm` tablo ve görev listesi için gerekli. Tipografi
 * DESIGN_SYSTEM.md §2.2 ölçeğine bağlanır; @tailwindcss/typography kurulu
 * DEĞİL, bu yüzden eleman stilleri burada açıkça verilir — ölçek dışına
 * çıkan bir "prose" varsayılanı olmasın diye bu bilinçli.
 *
 * Renkler yalnızca token köprüsünden (`text-foreground`, `border-border`, …)
 * gelir; bu dosyada hiçbir hex yok.
 */

const PROSE_CLASS = cn(
  "text-body text-foreground",
  "[&>*+*]:mt-3",
  "[&_p]:text-body [&_p]:leading-[1.375rem]",
  "[&_strong]:font-semibold",
  "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2",
  "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
  "[&_li+li]:mt-1 [&_li_p]:mt-0",
  "[&_blockquote]:border-l-2 [&_blockquote]:border-border-strong [&_blockquote]:pl-3 [&_blockquote]:text-text-secondary",
  "[&_h1]:text-h1 [&_h2]:text-h2 [&_h3]:text-h3",
  "[&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold",
  "[&_hr]:border-border",
  // Satır içi kod (blok kod CodeBlock'a devredilir, `pre` altına düşmez).
  "[&_code]:rounded-sm [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-mono"
)

/** React ağacındaki metni toplar — fence içeriğini CodeBlock'a vermek için. */
function extractText(node: React.ReactNode): string {
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(extractText).join("")
  if (React.isValidElement<{ children?: React.ReactNode }>(node)) {
    return extractText(node.props.children)
  }
  return ""
}

const LANGUAGE_PATTERN = /language-([\w-]+)/

/**
 * Metin düğümlerindeki atıf işaretçilerini üst simgeye çevirir (§13.4).
 *
 * react-markdown metin düğümlerini düz string olarak veriyor; bileşen
 * eşlemesiyle yakalanamıyorlar. Bu yüzden dönüşüm children ağacında
 * ÖZYİNELİ yapılır — `strong`/`em` gibi iç içe elemanların içindeki
 * atıflar da yakalanır.
 *
 * Alternatif (metni react-markdown'a vermeden önce bir sentinel ile
 * değiştirmek) REDDEDİLDİ: sentinel kod bloklarının içine de girerdi ve
 * orada harfi harfine basılırdı.
 */
function applyCitations(
  node: React.ReactNode,
  render: (citation: string, key: string) => React.ReactNode
): React.ReactNode {
  if (typeof node === "string") {
    const markers = scanCitations(node)
    if (markers.length === 0) return node

    const parts: React.ReactNode[] = []
    let rest = node
    markers.forEach((marker, i) => {
      const at = rest.indexOf(marker)
      if (at < 0) return
      if (at > 0) parts.push(rest.slice(0, at))
      parts.push(render(marker, `c${i}`))
      rest = rest.slice(at + marker.length)
    })
    if (rest) parts.push(rest)
    return parts
  }

  if (Array.isArray(node)) {
    return node.map((child, i) => (
      <React.Fragment key={i}>{applyCitations(child, render)}</React.Fragment>
    ))
  }

  if (React.isValidElement<{ children?: React.ReactNode }>(node)) {
    const { children } = node.props
    if (children === undefined) return node
    return React.cloneElement(node, undefined, applyCitations(children, render))
  }

  return node
}

/** Atıf dönüşümünün uygulandığı elemanlar — düz metin taşıyan her blok. */
const CITATION_HOSTS = ["p", "li", "td", "th", "blockquote", "h1", "h2", "h3"] as const

function buildComponents(highlightCode: boolean): Components {
  return {
    // Blok kod: `pre` seviyesinde yakalanır, çocuk `code` elemanı hiç
    // render edilmez -- böylece iç içe <pre><code> ve çift stil oluşmaz.
    pre({ children }) {
      const child = React.Children.toArray(children)[0]
      if (
        React.isValidElement<{ className?: string; children?: React.ReactNode }>(
          child
        )
      ) {
        const language = LANGUAGE_PATTERN.exec(child.props.className ?? "")?.[1]
        return (
          <CodeBlock
            code={extractText(child.props.children).replace(/\n$/, "")}
            language={language}
            highlight={highlightCode}
          />
        )
      }
      return <pre>{children}</pre>
    },

    // Geniş tablolar yatayda KENDİ kabında kayar; panel taşmaz.
    table({ children }) {
      return (
        <div className="overflow-x-auto rounded-md border border-border">
          {/* Son satırın alt çizgisi kabın kenarlığıyla çakışmasın diye
              tr:last-child üzerinden kapatılır — td'ye `last:` vermek
              satırın SON HÜCRESİNİ hedefler, son satırı değil. */}
          <table className="w-full border-collapse text-body-sm [&_tr:last-child_td]:border-b-0">
            {children}
          </table>
        </div>
      )
    },
    th({ children }) {
      return (
        <th className="border-b border-border bg-muted px-3 py-2 text-left text-caption font-medium text-text-secondary">
          {children}
        </th>
      )
    },
    td({ children }) {
      return (
        <td className="border-b border-border px-3 py-2 align-top">{children}</td>
      )
    },

    a({ children, href }) {
      return (
        <a href={href} target="_blank" rel="noreferrer noopener">
          {children}
        </a>
      )
    },
  }
}

/**
 * Atıf dönüşümünü metin taşıyan elemanların üzerine SARAR.
 *
 * Var olan özel renderer'lar (td/th gibi) korunur: sarmalayıcı yalnızca
 * children'ı dönüştürüp asıl bileşene devreder.
 */
function withCitations(
  base: Components,
  render: (citation: string, key: string) => React.ReactNode
): Components {
  const wrapped: Record<string, unknown> = { ...base }
  for (const tag of CITATION_HOSTS) {
    const Base = (base as Record<string, unknown>)[tag] as
      | React.ComponentType<Record<string, unknown>>
      | undefined
    wrapped[tag] = ({
      children,
      ...props
    }: {
      children?: React.ReactNode
    } & Record<string, unknown>) => {
      const content = applyCitations(children, render)
      return Base
        ? <Base {...props}>{content}</Base>
        : React.createElement(tag, props, content)
    }
  }
  return wrapped as Components
}

const COMPONENTS_HIGHLIGHTED = buildComponents(true)
const COMPONENTS_PLAIN = buildComponents(false)
const REMARK_PLUGINS = [remarkGfm]

export interface MarkdownContentProps {
  children: string
  /** Akış sürerken kod vurgulaması yapılmaz (her token'da yeniden hesap boşuna). */
  highlightCode?: boolean
  /**
   * Atıf işaretçisini (`[Kaynak: dosya.pdf s.4]`) neye çevireceği — §13.4'ün
   * numaralı üst simgesi. Verilmezse işaretçiler metinde OLDUĞU GİBİ kalır
   * (mevcut davranış; artefakt görünümleri ve önizleme bunu kullanır).
   */
  renderCitation?: (citation: string, key: string) => React.ReactNode
  className?: string
}

export function MarkdownContent({
  children,
  highlightCode = true,
  renderCitation,
  className,
}: MarkdownContentProps) {
  const base = highlightCode ? COMPONENTS_HIGHLIGHTED : COMPONENTS_PLAIN
  // Sarmalama her render'da değil, yalnızca renderCitation değiştiğinde.
  const components = React.useMemo(
    () => (renderCitation ? withCitations(base, renderCitation) : base),
    [base, renderCitation]
  )

  return (
    <div className={cn(PROSE_CLASS, className)}>
      <Markdown remarkPlugins={REMARK_PLUGINS} components={components}>
        {children}
      </Markdown>
    </div>
  )
}
