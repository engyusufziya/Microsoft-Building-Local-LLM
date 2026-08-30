"use client"

/**
 * ÖNİZLEME — "Ders Masası" Modernist yeniden tasarımı (izole prototip).
 *
 * Bu rota YALNIZCA canlı önizleme içindir. Üretim kabuğuna (app/page.tsx),
 * dondurulmuş tasarım token'larına (globals.css) ve DESIGN_SYSTEM.md
 * sözleşmesine BİLİNÇLİ olarak dokunmaz. Amaç: tasarımı çalışır hâlde görüp
 * "benimse / benimseme" kararını gerçek görüntü üzerinden vermek
 * (AGENTS.md §1.6, §2.4). Karar "benimse" olursa, o zaman token/DESIGN_SYSTEM
 * değişikliği kendi başına, kontrast yeniden doğrulanarak yapılır.
 *
 * Offline (AGENTS.md §1.2): CDN yok. Kaynak mockup'taki Google Fonts (Archivo)
 * ve unpkg lucide yerine — depoya gömülü Inter (--font-inter) ve lucide-react
 * paketi kullanılır. Archivo yerine Inter bir YER TUTUCUDUR; benimsenirse
 * Archivo woff2'si @fontsource'tan çıkarılıp gömülür (fonts.ts'teki desen).
 *
 * Modernist token'ları .dm-root'a scope'lanır; global tema etkilenmez.
 */

import * as React from "react"
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bookmark,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  FilePlus2,
  FileText,
  FolderOpen,
  Languages,
  List,
  ListChecks,
  Network,
  Plus,
  Quote,
  RefreshCw,
  RotateCcw,
  SkipForward,
  Sparkles,
  X,
} from "lucide-react"

// Modernist tasarım sisteminin token + sınıfları — yalnızca .dm-root altında.
const DM_CSS = `
.dm-root {
  --color-bg: #f3f2f2;
  --color-surface: #eae9e9;
  --color-text: #201e1d;
  --color-accent: #ec3013;
  --color-divider: color-mix(in srgb, #201e1d 40%, transparent);
  --color-neutral-100: #f8f4f4;
  --color-neutral-200: #eae7e7;
  --color-neutral-300: #d7d3d3;
  --color-neutral-400: #bab6b6;
  --color-neutral-500: #9b9797;
  --color-neutral-600: #7d7979;
  --color-neutral-700: #605d5d;
  --color-neutral-800: #444141;
  --color-neutral-900: #2d2b2b;
  --color-accent-100: #fff2ef;
  --color-accent-200: #ffe0d9;
  --color-accent-300: #ffc4b8;
  --color-accent-600: #dd2b0f;
  --color-accent-700: #ae1800;
  --font-heading: var(--font-inter), system-ui, sans-serif;
  --font-body: var(--font-inter), system-ui, sans-serif;
  --font-mono: var(--font-mono), ui-monospace, monospace;
  --shadow-lg: 0 12px 32px color-mix(in srgb, #2d2b2b 22%, transparent);
}
.dm-root, .dm-root *, .dm-root *::before, .dm-root *::after { box-sizing: border-box; }
.dm-root { color: var(--color-text); background: var(--color-bg); font-family: var(--font-body); }
.dm-root svg { display: block; }
.dm-stripe { background-image: repeating-linear-gradient(135deg, rgba(32,30,29,.09) 0 6px, transparent 6px 12px); }

@keyframes dm-drawerIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
@keyframes dm-fadeUp { from { transform: translateY(6px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
@keyframes dm-spin { to { transform: rotate(360deg); } }

.dm-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  cursor: pointer; text-decoration: none; font-family: var(--font-heading);
  font-weight: 800; font-size: 14px; line-height: 1.2; color: var(--color-text);
  background: transparent; border: 1px solid transparent; padding: 8px 14px;
}
.dm-btn-primary { background: var(--color-accent); color: var(--color-bg); }
.dm-btn-primary:hover { background: var(--color-accent-600); }
.dm-btn-secondary { border-color: var(--color-divider); }
.dm-btn-secondary:hover { background: color-mix(in srgb, var(--color-text) 7%, transparent); }
.dm-btn-ghost { color: var(--color-accent); padding-inline: 4px; }
.dm-btn-ghost:hover { background: color-mix(in srgb, var(--color-accent) 10%, transparent); }
.dm-btn-block { width: 100%; }

.dm-tag { display: inline-flex; align-items: center; font-size: 11px; padding: 3px 10px; }
.dm-tag-outline { border: 1px solid var(--color-accent); color: var(--color-accent); }

.dm-hover-accent:hover { background: var(--color-accent-100); }
.dm-hover-accentborder:hover { border-color: var(--color-accent); background: var(--color-accent-100); }
.dm-settings-btn:hover { background: var(--color-accent-100); border-color: var(--color-accent); }
.dm-x:hover { color: var(--color-accent); }
`

type Cite = {
  page: number
  chunk: number
  score: string
  before: string
  text: string
  after: string
}

const CITES: Record<number, Cite> = {
  1: {
    page: 1,
    chunk: 4,
    score: "0.68",
    before:
      "Yaz okulu, lisans düzeyindeki katılımcılara yöneliktir ve dört haftaya yayılır.",
    text: "Program, bilgisayar bilimleri öğrencilerinin kendi cihazlarında çalışan bir soru-cevap asistanı kurmasını hedefler.",
    after: "Katılımcıların ön koşulu temel Python bilgisidir.",
  },
  2: {
    page: 2,
    chunk: 12,
    score: "0.71",
    before: "Katılımcılar önce temel kavramları görür, ardından uygulamaya geçer.",
    text: "Programın amacı, küçük bir belge koleksiyonu üzerinde sorulara cevap veren çevrimdışı bir soru-cevap botu oluşturmak için Foundry Local ve Retrieval-Augmented Generation (RAG) desenini kullanmaktır.",
    after:
      "Modüller günlük oturumlar hâlinde ilerler; her oturum sonunda küçük bir teslim beklenir.",
  },
  3: {
    page: 5,
    chunk: 31,
    score: "0.63",
    before: "Haftalık plan dört modüle bölünmüştür.",
    text: "Modüller sırasıyla temel kavramlar, veri embeddinglerinin oluşturulması, soru-cevap sisteminin geliştirilmesi ve test edilmesidir.",
    after: "Son modülde katılımcılar kendi korpuslarıyla bir demo sunar.",
  },
}

const mono = { fontFamily: "var(--font-mono)" } as const
const upLabel = {
  fontSize: "11px",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  fontWeight: 600,
  color: "var(--color-neutral-600)",
} as const

type ScreenKey = "empty" | "chat" | "quiz" | "map"
type Doc = { name: string; meta: string; on: boolean; cited: boolean }

export default function Onizleme() {
  const [screen, setScreen] = React.useState<ScreenKey>("chat")
  const [tab, setTab] = React.useState<"sources" | "outputs">("sources")
  const [docs, setDocs] = React.useState<Doc[]>([
    { name: "Summer School Plan.pdf", meta: "13 sayfa · 94 bölüm", on: true, cited: true },
    { name: "Ciftci_2025.pdf", meta: "13 sayfa · 94 bölüm", on: true, cited: false },
  ])
  const [cite, setCite] = React.useState<number | null>(null)
  const [toolsOpen, setToolsOpen] = React.useState(false)
  const [settingsOpen, setSettingsOpen] = React.useState(false)
  const [draft, setDraft] = React.useState("")
  const [sent, setSent] = React.useState<{ text: string }[]>([])
  const [quizPick, setQuizPick] = React.useState(1)

  const selectedCount = docs.filter((d) => d.on).length
  const c = cite ? CITES[cite] : null
  const supBg = (n: number) => (cite === n ? "var(--color-accent)" : "var(--color-text)")

  const goCite = (n: number) => setCite(n)
  const openByPage = (page: number) => {
    const hit = Object.keys(CITES).find((k) => CITES[Number(k)].page === page)
    setCite(hit ? Number(hit) : 2)
  }
  const submit = () => {
    const t = draft.trim()
    if (!t) return
    setSent((s) => [...s, { text: t }])
    setDraft("")
  }
  const toggleDoc = (i: number) =>
    setDocs((s) => s.map((x, j) => (j === i ? { ...x, on: !x.on } : x)))
  const toggleAll = () =>
    setDocs((s) => {
      const all = s.every((d) => d.on)
      return s.map((d) => ({ ...d, on: !all }))
    })

  const screens: { key: ScreenKey; label: string }[] = [
    { key: "empty", label: "Boş durum" },
    { key: "chat", label: "Sohbet" },
    { key: "quiz", label: "Quiz" },
    { key: "map", label: "Zihin haritası" },
  ]

  const quizText = [
    "Korpus yüklenmeden önce, model indirilirken",
    "Belgeler bölümlere ayrıldıktan sonra, sorgudan önce",
    "Her soru sorulduğunda yeniden, tüm belge için",
    "Yalnızca cevap üretildikten sonra doğrulama amacıyla",
  ]

  const mapBranches = [
    {
      no: "01",
      title: "Temel kavramlar",
      note: "RAG nedir, neden yerel çalıştırılır",
      leaves: [
        { text: "Retrieval-Augmented Generation", page: 2 },
        { text: "Foundry Local çalışma zamanı", page: 2 },
        { text: "Çevrimdışı gizlilik gerekçesi", page: 3 },
      ],
    },
    {
      no: "02",
      title: "Embedding üretimi",
      note: "Belgelerin bölümlenmesi ve vektörleştirilmesi",
      leaves: [
        { text: "Bölümleme (chunking)", page: 5 },
        { text: "Gömme modeli seçimi", page: 6 },
        { text: "Vektör indeksi", page: 6 },
      ],
    },
    {
      no: "03",
      title: "Soru-cevap hattı",
      note: "Erişim, bağlam kurgusu, üretim",
      leaves: [
        { text: "Benzerlik eşiği", page: 8 },
        { text: "Bağlam penceresi", page: 8 },
        { text: "Alıntılandırma", page: 9 },
      ],
    },
    {
      no: "04",
      title: "Test ve teslim",
      note: "Değerlendirme ve demo",
      leaves: [
        { text: "Sadakat ölçümü", page: 11 },
        { text: "Örnek soru kümesi", page: 12 },
        { text: "Final demo", page: 13 },
      ],
    },
  ]

  return (
    <div
      className="dm-root"
      style={{
        fontFamily: "var(--font-body)",
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <style dangerouslySetInnerHTML={{ __html: DM_CSS }} />

      {/* ══ ÜST ÇUBUK ══ */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "0 20px",
          height: 60,
          borderBottom: "2px solid var(--color-divider)",
          flexShrink: 0,
        }}
      >
        <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 17, letterSpacing: "-0.01em" }}>
          Yerel Asistan
        </span>
        <span style={{ width: 1, height: 20, background: "var(--color-divider)" }} />
        <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>Bilgisayar Bilimleri · Yaz Okulu</span>
        <span style={{ flex: 1 }} />
        <div style={{ display: "flex", border: "1px solid var(--color-divider)" }}>
          {screens.map((s) => {
            const active = screen === s.key
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => {
                  setScreen(s.key)
                  setCite(null)
                }}
                style={{
                  background: active ? "var(--color-text)" : "transparent",
                  color: active ? "var(--color-bg)" : "var(--color-neutral-700)",
                  border: "none",
                  borderLeft: "1px solid var(--color-divider)",
                  fontFamily: "var(--font-heading)",
                  fontWeight: 800,
                  fontSize: 11.5,
                  letterSpacing: "0.02em",
                  padding: "6px 11px",
                  cursor: "pointer",
                }}
              >
                {s.label}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className="dm-settings-btn"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            border: "1px solid var(--color-divider)",
            background: "transparent",
            padding: "6px 10px",
            cursor: "pointer",
            fontFamily: "var(--font-body)",
            color: "var(--color-text)",
          }}
        >
          <span style={{ width: 7, height: 7, background: "var(--color-accent)", flexShrink: 0 }} />
          <span style={{ fontSize: 12, fontWeight: 600 }}>qwen2.5-7b</span>
          <span style={{ ...mono, fontSize: 11, color: "var(--color-neutral-700)" }}>18 tok/s · 6.2 GB</span>
          <ChevronDown size={13} style={{ color: "var(--color-neutral-700)" }} />
        </button>
        <button type="button" className="dm-btn dm-btn-ghost" style={{ fontSize: 13, gap: 7 }}>
          <Languages size={16} /> TR
        </button>
      </div>

      <div style={{ flex: 1, display: "flex", minHeight: 0, position: "relative" }}>
        {/* ══ SOL: KAYNAKLAR / ÇIKTILAR ══ */}
        <div
          style={{
            width: 272,
            flexShrink: 0,
            borderRight: "2px solid var(--color-divider)",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <div style={{ display: "flex", borderBottom: "2px solid var(--color-divider)", flexShrink: 0 }}>
            {(["sources", "outputs"] as const).map((k) => {
              const on = tab === k
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => setTab(k)}
                  style={{
                    flex: 1,
                    padding: "13px 16px",
                    textAlign: "left",
                    background: "transparent",
                    border: "none",
                    borderLeft: k === "outputs" ? "1px solid var(--color-divider)" : undefined,
                    cursor: "pointer",
                    fontFamily: "var(--font-heading)",
                    fontSize: 12,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: on ? "var(--color-text)" : "var(--color-neutral-600)",
                    fontWeight: on ? 800 : 400,
                    borderBottom: `3px solid ${on ? "var(--color-accent)" : "transparent"}`,
                    marginBottom: -2,
                  }}
                >
                  {k === "sources" ? "Kaynaklar" : "Çıktılar 3"}
                </button>
              )
            })}
          </div>

          {tab === "sources" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "10px 16px",
                  borderBottom: "1px solid var(--color-divider)",
                  fontSize: 12,
                  color: "var(--color-neutral-700)",
                  flexShrink: 0,
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedCount === docs.length}
                  onChange={toggleAll}
                  style={{ width: 14, height: 14, accentColor: "var(--color-accent)", cursor: "pointer" }}
                />
                <span>Tümünü seç</span>
                <span style={{ flex: 1 }} />
                <span style={mono}>{selectedCount}/2</span>
              </div>

              <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
                {docs.map((d, i) => (
                  <div
                    key={d.name}
                    onClick={() => toggleDoc(i)}
                    style={{
                      display: "flex",
                      gap: 11,
                      padding: "14px 16px",
                      borderBottom: "1px solid var(--color-divider)",
                      cursor: "pointer",
                      background: d.cited && d.on ? "var(--color-accent-100)" : "transparent",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={d.on}
                      onChange={() => toggleDoc(i)}
                      onClick={(e) => e.stopPropagation()}
                      style={{ width: 14, height: 14, marginTop: 3, accentColor: "var(--color-accent)", cursor: "pointer", flexShrink: 0 }}
                    />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontFamily: "var(--font-heading)",
                          fontWeight: 800,
                          fontSize: 13,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {d.name}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--color-neutral-700)", marginTop: 3 }}>{d.meta}</div>
                      {d.cited && (
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 5,
                            marginTop: 7,
                            fontSize: 10,
                            letterSpacing: "0.06em",
                            textTransform: "uppercase",
                            fontWeight: 600,
                            color: "var(--color-accent-700)",
                          }}
                        >
                          <Quote size={12} /> bu cevapta 13 alıntı
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                <div style={{ display: "flex", gap: 11, padding: "14px 16px", borderBottom: "1px solid var(--color-divider)", opacity: 0.8 }}>
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      marginTop: 3,
                      border: "2px solid var(--color-neutral-400)",
                      borderTopColor: "var(--color-accent)",
                      flexShrink: 0,
                      animation: "dm-spin 1s linear infinite",
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      Ders_Notlari_2026.pdf
                    </div>
                    <div style={{ fontSize: 11, color: "var(--color-neutral-700)", marginTop: 3 }}>bölümlere ayrılıyor · %62</div>
                    <div style={{ height: 3, background: "var(--color-neutral-300)", marginTop: 7 }}>
                      <div style={{ width: "62%", height: "100%", background: "var(--color-accent)" }} />
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ borderTop: "2px solid var(--color-divider)", padding: "14px 16px", flexShrink: 0 }}>
                <button type="button" className="dm-btn dm-btn-primary dm-btn-block" style={{ justifyContent: "flex-start", gap: 8 }}>
                  <Plus size={16} /> PDF ekle
                </button>
                <div style={{ fontSize: 11, color: "var(--color-neutral-600)", marginTop: 9, lineHeight: 1.5 }}>
                  Dosyalar cihazından çıkmaz.
                </div>
              </div>
            </div>
          )}

          {tab === "outputs" && (
            <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
              <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--color-divider)", background: "var(--color-accent-100)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <FileText size={16} style={{ color: "var(--color-accent-700)" }} />
                  <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 13.5, flex: 1 }}>Korpus Raporu</span>
                  <span style={{ ...mono, fontSize: 10, color: "var(--color-neutral-700)" }}>v3</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, fontSize: 11.5, color: "var(--color-accent-700)", fontWeight: 600 }}>
                  <AlertTriangle size={13} /> Yeni kaynak eklendi
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                  <button type="button" className="dm-btn dm-btn-primary" style={{ fontSize: 12, padding: "5px 10px", gap: 6 }}>
                    <RefreshCw size={13} /> Güncelle
                  </button>
                  <button type="button" className="dm-btn dm-btn-secondary" style={{ fontSize: 12, padding: "5px 10px", gap: 6, background: "var(--color-bg)" }}>
                    <Download size={13} /> .md
                  </button>
                </div>
              </div>
              {[
                { icon: <Network size={16} style={{ color: "var(--color-neutral-700)" }} />, title: "Zihin Haritası", v: "v2", meta: "bugün 13:30" },
                { icon: <ListChecks size={16} style={{ color: "var(--color-neutral-700)" }} />, title: "Quiz", v: "v2", meta: "12 soru · dün" },
              ].map((o) => (
                <div key={o.title} style={{ padding: "14px 16px", borderBottom: "1px solid var(--color-divider)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                    {o.icon}
                    <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 13.5, flex: 1 }}>{o.title}</span>
                    <span style={{ ...mono, fontSize: 10, color: "var(--color-neutral-700)" }}>{o.v}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
                    <span style={{ ...mono, fontSize: 10.5, color: "var(--color-neutral-600)" }}>{o.meta}</span>
                    <span style={{ flex: 1 }} />
                    <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}>
                      Aç <ArrowRight size={13} />
                    </span>
                    <Download size={14} style={{ color: "var(--color-neutral-700)", cursor: "pointer" }} />
                  </div>
                </div>
              ))}
              <div style={{ padding: "14px 16px", fontSize: 11.5, color: "var(--color-neutral-600)", lineHeight: 1.6 }}>
                Çıktılar cihazında <span style={mono}>~/notebook/outputs</span> altında Markdown olarak tutulur.
              </div>
            </div>
          )}
        </div>

        {/* ══ ORTA: SOHBET ══ */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={{ flex: 1, overflowY: "auto", minHeight: 0, padding: "26px 0 10px" }}>
            <div style={{ maxWidth: 760, margin: "0 auto", padding: "0 32px", display: "flex", flexDirection: "column", gap: 22 }}>
              <div
                style={{
                  alignSelf: "flex-end",
                  maxWidth: "78%",
                  background: "var(--color-surface)",
                  borderLeft: "3px solid var(--color-text)",
                  padding: "11px 14px",
                  fontSize: 14,
                  lineHeight: 1.55,
                }}
              >
                Bu belgeler ne hakkında?
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
                <div style={{ fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600, color: "var(--color-neutral-600)" }}>
                  Asistan
                </div>
                <div style={{ fontSize: 15, lineHeight: 1.72, textWrap: "pretty" }}>
                  Belgeler, bilgisayar bilimleri öğrencilerine yönelik bir yaz okulu programını anlatıyor.
                  <sup onClick={() => goCite(1)} style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 10, background: supBg(1), color: "var(--color-bg)", padding: "2px 5px", marginLeft: 3, verticalAlign: 2, cursor: "pointer" }}>1</sup>{" "}
                  Amaç, küçük bir belge koleksiyonu üzerinde soru-cevap yapabilen <strong style={{ fontWeight: 600 }}>çevrimdışı</strong> bir asistan kurmak — Foundry Local ile yerel model, RAG deseniyle erişim.
                  <sup onClick={() => goCite(2)} style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 10, background: supBg(2), color: "var(--color-bg)", padding: "2px 5px", marginLeft: 3, verticalAlign: 2, cursor: "pointer" }}>2</sup>{" "}
                  Program dört modülden ilerler: kavramlar, embedding üretimi, soru-cevap hattı ve test.
                  <sup onClick={() => goCite(3)} style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 10, background: supBg(3), color: "var(--color-bg)", padding: "2px 5px", marginLeft: 3, verticalAlign: 2, cursor: "pointer" }}>3</sup>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 11, color: "var(--color-neutral-600)", borderTop: "1px solid var(--color-divider)", paddingTop: 10 }}>
                  <span style={mono}>13 alıntı · 1 belge · 23.6 sn</span>
                  <span style={{ flex: 1 }} />
                  <span onClick={() => goCite(2)} style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer" }}>
                    <List size={13} /> alıntılar
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer" }}>
                    <Download size={13} /> .md
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer" }}>
                    <RotateCcw size={13} /> yeniden
                  </span>
                </div>
              </div>

              {sent.map((m, i) => (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 18, animation: "dm-fadeUp .3s ease both" }}>
                  <div style={{ alignSelf: "flex-end", maxWidth: "78%", background: "var(--color-surface)", borderLeft: "3px solid var(--color-text)", padding: "11px 14px", fontSize: 14, lineHeight: 1.55 }}>
                    {m.text}
                  </div>
                  <div style={{ border: "1px solid var(--color-divider)", padding: "12px 14px", maxWidth: 330, display: "flex", flexDirection: "column", gap: 7 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--color-neutral-700)" }}>
                      <Check size={13} style={{ color: "var(--color-accent)" }} /> Seçili kaynaklar tarandı
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--color-neutral-700)" }}>
                      <Check size={13} style={{ color: "var(--color-accent)" }} /> 4 ilgili bölüm seçildi
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 600 }}>
                      <span style={{ width: 11, height: 11, border: "2px solid var(--color-neutral-400)", borderTopColor: "var(--color-accent)", animation: "dm-spin 1s linear infinite" }} /> Yanıt yazılıyor…
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* katlanabilir çalışma araçları + yazma alanı */}
          <div style={{ borderTop: "2px solid var(--color-divider)", flexShrink: 0 }}>
            <div style={{ maxWidth: 760, margin: "0 auto", padding: "0 32px" }}>
              <div style={{ borderBottom: "1px solid var(--color-divider)" }}>
                <button
                  type="button"
                  onClick={() => setToolsOpen((v) => !v)}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 0",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "var(--font-body)",
                    color: "var(--color-text)",
                    textAlign: "left",
                  }}
                >
                  {toolsOpen ? (
                    <ChevronDown size={14} style={{ color: "var(--color-neutral-700)" }} />
                  ) : (
                    <ChevronRight size={14} style={{ color: "var(--color-neutral-700)" }} />
                  )}
                  <span style={{ fontSize: 11.5, letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600, color: "var(--color-neutral-600)" }}>
                    Çalışma araçları
                  </span>
                  <span style={{ flex: 1 }} />
                  <span style={{ display: "flex", gap: 6 }}>
                    {["Rapor", "Zihin haritası", "Quiz"].map((t) => (
                      <span key={t} className="dm-tag dm-tag-outline" style={{ fontSize: 11 }}>
                        {t}
                      </span>
                    ))}
                  </span>
                </button>
                {toolsOpen && (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", border: "2px solid var(--color-text)", marginBottom: 12 }}>
                    {[
                      { icon: <FileText size={19} style={{ color: "var(--color-accent)" }} />, title: "Rapor oluştur", desc: "Seçili kaynakların yapılandırılmış özeti" },
                      { icon: <Network size={19} style={{ color: "var(--color-accent)" }} />, title: "Zihin haritası", desc: "Kavramlar ve aralarındaki bağlar" },
                      { icon: <ListChecks size={19} style={{ color: "var(--color-accent)" }} />, title: "Quiz oluştur", desc: "12 soru, cevap anahtarıyla" },
                    ].map((t, i) => (
                      <div
                        key={t.title}
                        className="dm-hover-accent"
                        style={{ padding: 14, borderRight: i < 2 ? "2px solid var(--color-text)" : undefined, cursor: "pointer" }}
                      >
                        {t.icon}
                        <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 13.5, marginTop: 10 }}>{t.title}</div>
                        <div style={{ fontSize: 11, color: "var(--color-neutral-700)", marginTop: 4, lineHeight: 1.45 }}>{t.desc}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ padding: "14px 0 18px" }}>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 12, border: "2px solid var(--color-text)", padding: "10px 10px 10px 14px" }}>
                  <textarea
                    rows={1}
                    placeholder="Seçili kaynaklara bir soru sor…"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit()
                    }}
                    style={{
                      flex: 1,
                      border: "none",
                      outline: "none",
                      resize: "none",
                      background: "transparent",
                      fontFamily: "var(--font-body)",
                      fontSize: 14.5,
                      lineHeight: 1.5,
                      color: "var(--color-text)",
                      padding: "5px 0",
                    }}
                  />
                  <button type="button" onClick={submit} className="dm-btn dm-btn-primary" style={{ gap: 7, flexShrink: 0 }}>
                    <ArrowUp size={16} /> Sor
                  </button>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 9, ...mono, fontSize: 10.5, color: "var(--color-neutral-600)" }}>
                  <span>⌘ + Enter ile gönder</span>
                  <span style={{ flex: 1 }} />
                  <span>{selectedCount} kaynak seçili · yerel</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ══ KAYNAK ÇEKMECESİ ══ */}
        {c && (
          <div
            style={{
              position: "absolute",
              top: 0,
              right: 0,
              bottom: 0,
              width: 400,
              background: "var(--color-neutral-100)",
              borderLeft: "2px solid var(--color-text)",
              boxShadow: "var(--shadow-lg)",
              display: "flex",
              flexDirection: "column",
              zIndex: 6,
              animation: "dm-drawerIn .2s ease both",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "14px 16px", borderBottom: "2px solid var(--color-divider)", flexShrink: 0 }}>
              <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 11, background: "var(--color-accent)", color: "var(--color-bg)", padding: "2px 6px", marginTop: 2 }}>
                {cite}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  Summer School Plan.pdf
                </div>
                <div style={{ ...mono, fontSize: 10.5, color: "var(--color-neutral-700)", marginTop: 3 }}>
                  s.{c.page} · bölüm {c.chunk}/94 · benzerlik {c.score}
                </div>
              </div>
              <button type="button" onClick={() => setCite(null)} className="dm-x" style={{ background: "transparent", border: "none", padding: 2, cursor: "pointer", color: "var(--color-neutral-700)", flexShrink: 0, display: "flex" }}>
                <X size={16} />
              </button>
            </div>

            <div style={{ padding: 16, borderBottom: "1px solid var(--color-divider)", flexShrink: 0 }}>
              <div className="dm-stripe" style={{ height: 176, border: "1px solid var(--color-divider)", backgroundColor: "var(--color-neutral-200)", position: "relative" }}>
                <div style={{ position: "absolute", left: "12%", right: "12%", top: "42%", height: "22%", background: "var(--color-accent-300)", border: "2px solid var(--color-accent)", mixBlendMode: "multiply" }} />
                <div style={{ position: "absolute", bottom: 6, left: 8, ...mono, fontSize: 9.5, color: "var(--color-neutral-700)", background: "var(--color-neutral-100)", padding: "1px 4px" }}>
                  sayfa görüntüsü · s.{c.page}
                </div>
              </div>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: 16, minHeight: 0 }}>
              <div style={{ ...upLabel, marginBottom: 10 }}>Alıntılanan bölüm</div>
              <div style={{ fontSize: 13, lineHeight: 1.75, color: "var(--color-neutral-800)" }}>
                {c.before}{" "}
                <mark style={{ background: "var(--color-accent-200)", color: "var(--color-text)", borderBottom: "2px solid var(--color-accent)", padding: "1px 0" }}>
                  {c.text}
                </mark>{" "}
                {c.after}
              </div>
            </div>

            <div style={{ borderTop: "2px solid var(--color-divider)", padding: "12px 16px", display: "flex", gap: 8, flexShrink: 0 }}>
              <button type="button" className="dm-btn dm-btn-secondary" style={{ flex: 1, justifyContent: "flex-start", gap: 7, background: "var(--color-bg)" }}>
                <ExternalLink size={16} /> PDF&apos;te aç
              </button>
              <button type="button" className="dm-btn dm-btn-secondary" style={{ justifyContent: "flex-start", gap: 7, background: "var(--color-bg)" }}>
                <Bookmark size={16} /> Nota al
              </button>
            </div>

            <div style={{ borderTop: "1px solid var(--color-divider)", padding: "11px 16px", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
              <span style={{ fontSize: 11, color: "var(--color-neutral-700)", flexShrink: 0 }}>Diğer alıntılar</span>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {[1, 2, 3, 5, 6, 7, 8, 9].map((n) => {
                  const on = c.page === n
                  return (
                    <span
                      key={n}
                      onClick={() => openByPage(n)}
                      style={{
                        ...mono,
                        fontSize: 10,
                        border: `1px solid ${on ? "var(--color-accent)" : "var(--color-divider)"}`,
                        background: on ? "var(--color-accent)" : "transparent",
                        color: on ? "var(--color-bg)" : "var(--color-text)",
                        padding: "2px 6px",
                        cursor: "pointer",
                      }}
                    >
                      {n}
                    </span>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* ══ BOŞ DURUM ══ */}
        {screen === "empty" && (
          <div style={{ position: "absolute", inset: 0, background: "var(--color-bg)", zIndex: 8, overflowY: "auto", display: "flex", justifyContent: "center" }}>
            <div style={{ width: 860, padding: "56px 0 40px" }}>
              <div style={{ fontSize: 11.5, letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, color: "var(--color-accent-700)" }}>Yeni defter</div>
              <h1 style={{ margin: "12px 0 0", fontSize: 46, lineHeight: 1.05, fontFamily: "var(--font-heading)", fontWeight: 800 }}>Kaynaklarını ekle.</h1>
              <p style={{ margin: "14px 0 0", fontSize: 16, lineHeight: 1.6, color: "var(--color-neutral-700)", maxWidth: "52ch", textWrap: "pretty" }}>
                PDF&apos;lerini bırak; asistan yalnızca onların içinden cevap verir. Hiçbir dosya cihazından çıkmaz, internet gerekmez.
              </p>

              <div style={{ marginTop: 32, border: "2px solid var(--color-text)", padding: "40px 32px", display: "flex", alignItems: "center", gap: 28 }}>
                <div className="dm-stripe" style={{ width: 116, height: 146, border: "1px solid var(--color-divider)", backgroundColor: "var(--color-neutral-200)", flexShrink: 0, position: "relative" }}>
                  <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <FilePlus2 size={26} style={{ color: "var(--color-neutral-700)" }} />
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 22 }}>Dosyaları buraya bırak</div>
                  <div style={{ fontSize: 13.5, color: "var(--color-neutral-700)", marginTop: 7, lineHeight: 1.55 }}>PDF · en fazla 50 MB · taranmış belgeler için OCR açık</div>
                  <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
                    <button type="button" onClick={() => setScreen("chat")} className="dm-btn dm-btn-primary" style={{ gap: 8 }}>
                      <FolderOpen size={16} /> Dosya seç
                    </button>
                    <button type="button" onClick={() => setScreen("chat")} className="dm-btn dm-btn-secondary" style={{ gap: 8 }}>
                      <Sparkles size={16} /> Örnek defteri aç
                    </button>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 40, borderTop: "2px solid var(--color-divider)", paddingTop: 20 }}>
                <div style={upLabel}>Sonra ne olur</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", marginTop: 16, border: "2px solid var(--color-text)" }}>
                  {[
                    { n: "01", t: "Soru sor", d: "Her cevap, hangi sayfadan geldiğini numarayla gösterir." },
                    { n: "02", t: "Kaynağı doğrula", d: "Numaraya bas, alıntılanan bölüm sayfa görüntüsüyle açılır." },
                    { n: "03", t: "Çalışmaya dök", d: "Rapor, zihin haritası ve quiz üret; Markdown olarak dışa aktar." },
                  ].map((s, i) => (
                    <div key={s.n} style={{ padding: 20, borderRight: i < 2 ? "2px solid var(--color-text)" : undefined }}>
                      <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 32, color: "var(--color-accent)" }}>{s.n}</div>
                      <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 15, marginTop: 12 }}>{s.t}</div>
                      <div style={{ fontSize: 12.5, color: "var(--color-neutral-700)", marginTop: 6, lineHeight: 1.5 }}>{s.d}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 24, ...mono, fontSize: 11, color: "var(--color-neutral-600)" }}>
                <span style={{ width: 7, height: 7, background: "var(--color-accent)" }} />
                <span>qwen2.5-7b hazır · 6.2 GB RAM · çevrimdışı</span>
              </div>
            </div>
          </div>
        )}

        {/* ══ QUIZ ══ */}
        {screen === "quiz" && (
          <div style={{ position: "absolute", inset: 0, background: "var(--color-bg)", zIndex: 4, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "0 24px", height: 52, borderBottom: "2px solid var(--color-divider)", flexShrink: 0 }}>
              <button type="button" onClick={() => setScreen("chat")} className="dm-btn dm-btn-ghost" style={{ fontSize: 13, gap: 7, paddingLeft: 0 }}>
                <ArrowLeft size={16} /> Sohbete dön
              </button>
              <span style={{ width: 1, height: 18, background: "var(--color-divider)" }} />
              <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 14 }}>Quiz — Summer School Plan.pdf</span>
              <span style={{ ...mono, fontSize: 11, color: "var(--color-neutral-700)" }}>12 soru · v2</span>
              <span style={{ flex: 1 }} />
              <button type="button" className="dm-btn dm-btn-secondary" style={{ fontSize: 12.5, gap: 7 }}>
                <RefreshCw size={13} /> Yeniden üret
              </button>
              <button type="button" className="dm-btn dm-btn-secondary" style={{ fontSize: 12.5, gap: 7 }}>
                <Download size={13} /> .md
              </button>
            </div>

            <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
              <div style={{ flex: 1, overflowY: "auto", minHeight: 0, display: "flex", justifyContent: "center", padding: "30px 0 40px" }}>
                <div style={{ width: 660, display: "flex", flexDirection: "column", gap: 26 }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                      <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 11.5, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-neutral-600)" }}>Soru 03 / 12</span>
                      <span style={{ flex: 1, height: 2, background: "var(--color-neutral-300)" }}>
                        <span style={{ display: "block", width: "25%", height: "100%", background: "var(--color-accent)" }} />
                      </span>
                    </div>
                    <h3 style={{ margin: "14px 0 0", fontSize: 24, lineHeight: 1.25, fontFamily: "var(--font-heading)", fontWeight: 800 }}>
                      RAG deseninde embedding üretimi hangi aşamada yapılır?
                    </h3>
                  </div>

                  <div style={{ border: "2px solid var(--color-text)" }}>
                    {quizText.map((text, i) => {
                      const on = quizPick === i
                      return (
                        <div
                          key={i}
                          onClick={() => setQuizPick(i)}
                          className="dm-hover-accent"
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 12,
                            padding: "15px 16px",
                            borderBottom: i < 3 ? "1px solid var(--color-divider)" : undefined,
                            cursor: "pointer",
                            background: on ? "var(--color-accent-100)" : "transparent",
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "var(--font-heading)",
                              fontWeight: 800,
                              fontSize: 12,
                              width: 22,
                              height: 22,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              border: `2px solid ${on ? "var(--color-accent)" : "var(--color-divider)"}`,
                              background: on ? "var(--color-accent)" : "transparent",
                              color: on ? "var(--color-bg)" : "var(--color-text)",
                              flexShrink: 0,
                            }}
                          >
                            {["A", "B", "C", "D"][i]}
                          </span>
                          <span style={{ fontSize: 14.5, lineHeight: 1.5 }}>{text}</span>
                        </div>
                      )
                    })}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <button type="button" className="dm-btn dm-btn-primary" style={{ gap: 8 }}>
                      <Check size={16} /> Cevapla
                    </button>
                    <button type="button" className="dm-btn dm-btn-ghost" style={{ gap: 8, fontSize: 13 }}>
                      <SkipForward size={14} /> Atla
                    </button>
                    <span style={{ flex: 1 }} />
                    <button type="button" onClick={() => goCite(3)} className="dm-btn dm-btn-ghost" style={{ gap: 7, fontSize: 13, color: "var(--color-accent-700)" }}>
                      <Quote size={14} /> Kaynağı göster
                    </button>
                  </div>

                  <div style={{ borderTop: "2px solid var(--color-divider)", paddingTop: 22 }}>
                    <div style={upLabel}>Önceki soru</div>
                    <div style={{ border: "2px solid var(--color-accent)", marginTop: 12 }}>
                      <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--color-accent-300)", background: "var(--color-accent-100)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                          <Check size={15} style={{ color: "var(--color-accent-700)" }} />
                          <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 13, color: "var(--color-accent-700)" }}>Doğru</span>
                          <span style={{ flex: 1 }} />
                          <span style={{ ...mono, fontSize: 10.5, color: "var(--color-accent-700)" }}>soru 02</span>
                        </div>
                        <div style={{ fontSize: 14, marginTop: 9, lineHeight: 1.5 }}>
                          Programın hedeflediği çalışma biçimi nedir? — <strong style={{ fontWeight: 600 }}>Çevrimdışı, cihaz üzerinde soru-cevap</strong>
                        </div>
                      </div>
                      <div style={{ padding: "13px 16px", display: "flex", alignItems: "flex-start", gap: 11 }}>
                        <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 10, background: "var(--color-accent)", color: "var(--color-bg)", padding: "2px 5px", marginTop: 3, flexShrink: 0 }}>2</span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-800)" }}>
                            &ldquo;…çevrimdışı bir soru-cevap botu oluşturmak için Foundry Local ve RAG desenini kullanmaktır.&rdquo;
                          </div>
                          <button type="button" onClick={() => goCite(2)} className="dm-btn dm-btn-ghost" style={{ fontSize: 12, gap: 6, padding: "6px 0", marginTop: 4 }}>
                            <ExternalLink size={13} /> s.2 · bölüm 12&apos;yi aç
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ width: 240, flexShrink: 0, borderLeft: "2px solid var(--color-divider)", padding: "24px 20px", display: "flex", flexDirection: "column", gap: 22 }}>
                <div>
                  <div style={{ ...upLabel, marginBottom: 12 }}>İlerleme</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", borderTop: "1px solid var(--color-divider)", borderLeft: "1px solid var(--color-divider)" }}>
                    {Array.from({ length: 12 }, (_, i) => {
                      const n = i + 1
                      const done = n < 3
                      const now = n === 3
                      return (
                        <div
                          key={n}
                          style={{
                            aspectRatio: "1",
                            borderRight: "1px solid var(--color-divider)",
                            borderBottom: "1px solid var(--color-divider)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            ...mono,
                            fontSize: 11,
                            background: now ? "var(--color-accent)" : done ? "var(--color-neutral-200)" : "transparent",
                            color: now ? "var(--color-bg)" : done ? "var(--color-text)" : "var(--color-neutral-600)",
                          }}
                        >
                          {n}
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div style={{ borderTop: "2px solid var(--color-divider)", paddingTop: 16 }}>
                  <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 30 }}>2/2</div>
                  <div style={{ fontSize: 12, color: "var(--color-neutral-700)", marginTop: 3 }}>şu ana kadar doğru</div>
                </div>
                <div style={{ fontSize: 11.5, color: "var(--color-neutral-600)", lineHeight: 1.6 }}>
                  Sorular yalnızca seçili kaynaklardan üretildi. Her cevabın altında geldiği bölüm gösterilir.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══ ZİHİN HARİTASI ══ */}
        {screen === "map" && (
          <div style={{ position: "absolute", inset: 0, background: "var(--color-bg)", zIndex: 4, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "0 24px", height: 52, borderBottom: "2px solid var(--color-divider)", flexShrink: 0 }}>
              <button type="button" onClick={() => setScreen("chat")} className="dm-btn dm-btn-ghost" style={{ fontSize: 13, gap: 7, paddingLeft: 0 }}>
                <ArrowLeft size={16} /> Sohbete dön
              </button>
              <span style={{ width: 1, height: 18, background: "var(--color-divider)" }} />
              <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 14 }}>Zihin Haritası — 2 kaynak</span>
              <span style={{ ...mono, fontSize: 11, color: "var(--color-neutral-700)" }}>v2 · 4 dal · 12 kavram</span>
              <span style={{ flex: 1 }} />
              <button type="button" className="dm-btn dm-btn-secondary" style={{ fontSize: 12.5, gap: 7 }}>
                <RefreshCw size={13} /> Yeniden üret
              </button>
              <button type="button" className="dm-btn dm-btn-secondary" style={{ fontSize: 12.5, gap: 7 }}>
                <Download size={13} /> .md
              </button>
            </div>

            <div style={{ flex: 1, overflow: "auto", minHeight: 0, padding: "28px 32px" }}>
              <div style={{ display: "flex", alignItems: "stretch", gap: 0, minWidth: 1100 }}>
                <div style={{ width: 260, flexShrink: 0, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <div style={{ border: "2px solid var(--color-text)", background: "var(--color-accent)", color: "var(--color-bg)", padding: 18 }}>
                    <div style={{ fontSize: 10.5, letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, opacity: 0.85 }}>Kök</div>
                    <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 21, lineHeight: 1.15, marginTop: 8 }}>Yerel RAG Yaz Okulu</div>
                    <div style={{ fontSize: 12, lineHeight: 1.5, marginTop: 10, opacity: 0.9 }}>Çevrimdışı soru-cevap asistanı kurma programı</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, ...mono, fontSize: 10.5, color: "var(--color-neutral-600)" }}>
                    <span>2 kaynak · 26 sayfa</span>
                  </div>
                </div>

                <div style={{ width: 44, flexShrink: 0, position: "relative" }}>
                  <div style={{ position: "absolute", left: 0, right: "50%", top: "50%", height: 2, background: "var(--color-text)" }} />
                  <div style={{ position: "absolute", left: "50%", top: "12%", bottom: "12%", width: 2, background: "var(--color-text)" }} />
                </div>

                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>
                  {mapBranches.map((b) => (
                    <div key={b.no} style={{ display: "flex", alignItems: "stretch" }}>
                      <div style={{ width: 22, flexShrink: 0, position: "relative" }}>
                        <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 2, background: "var(--color-text)" }} />
                      </div>
                      <div style={{ width: 250, flexShrink: 0, border: "2px solid var(--color-text)", padding: "13px 14px", background: "var(--color-bg)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ ...mono, fontSize: 10, color: "var(--color-accent-700)" }}>{b.no}</span>
                          <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 14.5 }}>{b.title}</span>
                        </div>
                        <div style={{ fontSize: 11.5, color: "var(--color-neutral-700)", marginTop: 5, lineHeight: 1.45 }}>{b.note}</div>
                      </div>
                      <div style={{ width: 34, flexShrink: 0, position: "relative" }}>
                        <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 2, background: "var(--color-neutral-400)" }} />
                      </div>
                      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 6, borderLeft: "2px solid var(--color-neutral-400)", paddingLeft: 14 }}>
                        {b.leaves.map((l) => (
                          <div
                            key={l.text}
                            onClick={() => openByPage(l.page)}
                            className="dm-hover-accentborder"
                            style={{ display: "flex", alignItems: "center", gap: 9, border: "1px solid var(--color-divider)", padding: "7px 10px", cursor: "pointer", background: "var(--color-neutral-100)" }}
                          >
                            <span style={{ fontSize: 12.5, flex: 1 }}>{l.text}</span>
                            <span style={{ ...mono, fontSize: 9.5, color: "var(--color-neutral-600)", border: "1px solid var(--color-divider)", padding: "1px 4px" }}>s.{l.page}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ marginTop: 26, borderTop: "2px solid var(--color-divider)", paddingTop: 14, display: "flex", gap: 24, maxWidth: 1100 }}>
                <p style={{ margin: 0, fontSize: 12, color: "var(--color-neutral-700)", lineHeight: 1.6, flex: 1 }}>
                  Her kavram, geldiği sayfayla etiketli — kutuya bas, alıntı çekmecesi açılır. Harita seçili kaynaklardan üretilir; kaynak eklendiğinde &ldquo;yeniden üret&rdquo; gerekir.
                </p>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="dm-tag dm-tag-outline" style={{ fontSize: 11 }}>Summer School Plan.pdf</span>
                  <span className="dm-tag dm-tag-outline" style={{ fontSize: 11 }}>Ciftci_2025.pdf</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══ AYARLAR ══ */}
        {settingsOpen && (
          <div onClick={() => setSettingsOpen(false)} style={{ position: "absolute", inset: 0, background: "rgba(32,30,29,.45)", zIndex: 10, display: "flex", justifyContent: "flex-end" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ width: 400, background: "var(--color-bg)", borderLeft: "2px solid var(--color-text)", display: "flex", flexDirection: "column", animation: "dm-drawerIn .2s ease both" }}>
              <div style={{ display: "flex", alignItems: "center", padding: "16px 18px", borderBottom: "2px solid var(--color-divider)", flexShrink: 0 }}>
                <span style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 16, flex: 1 }}>Motor ve cihaz</span>
                <button type="button" onClick={() => setSettingsOpen(false)} className="dm-x" style={{ background: "transparent", border: "none", padding: 2, cursor: "pointer", color: "var(--color-neutral-700)", display: "flex" }}>
                  <X size={16} />
                </button>
              </div>
              <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
                <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--color-divider)" }}>
                  <div style={{ ...upLabel, marginBottom: 12 }}>Cihaz</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", border: "1px solid var(--color-divider)" }}>
                    {[
                      { v: "18", l: "tok/s" },
                      { v: "6.2 GB", l: "RAM" },
                      { v: "%41", l: "GPU" },
                    ].map((s, i) => (
                      <div key={s.l} style={{ padding: 11, borderRight: i < 2 ? "1px solid var(--color-divider)" : undefined }}>
                        <div style={{ fontFamily: "var(--font-heading)", fontWeight: 800, fontSize: 17 }}>{s.v}</div>
                        <div style={{ fontSize: 10.5, color: "var(--color-neutral-700)", marginTop: 2 }}>{s.l}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--color-divider)" }}>
                  <div style={{ ...upLabel, marginBottom: 12 }}>Modeller</div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingBottom: 9, borderBottom: "1px solid var(--color-divider)" }}>
                    <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>Sohbet</span>
                    <span style={{ ...mono, fontSize: 12 }}>qwen2.5-7b</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingTop: 9 }}>
                    <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>Gömme</span>
                    <span style={{ ...mono, fontSize: 12 }}>qwen3-embedding-0.6b</span>
                  </div>
                </div>
                <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--color-divider)", display: "flex", flexDirection: "column", gap: 16 }}>
                  <div style={upLabel}>Erişim</div>
                  {[
                    { t: "Getirilen bölüm", v: "4", d: "Daha fazlası = daha zengin cevap, daha yavaş yanıt.", w: "32%" },
                    { t: "Benzerlik eşiği", v: "0.45", d: "Yüksek eşik alakasız alıntıları keser, “bilmiyorum” cevabını artırır.", w: "45%" },
                  ].map((r) => (
                    <div key={r.t}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                        <span style={{ fontSize: 13.5, fontWeight: 600 }}>{r.t}</span>
                        <span style={{ ...mono, fontSize: 12, color: "var(--color-accent-700)" }}>{r.v}</span>
                      </div>
                      <div style={{ fontSize: 11.5, color: "var(--color-neutral-700)", marginTop: 4, lineHeight: 1.5 }}>{r.d}</div>
                      <div style={{ height: 4, background: "var(--color-neutral-300)", marginTop: 9 }}>
                        <div style={{ width: r.w, height: "100%", background: "var(--color-accent)" }} />
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ padding: "16px 18px" }}>
                  <div style={{ ...upLabel, marginBottom: 12 }}>Belge işleme</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 600 }}>OCR</div>
                      <div style={{ fontSize: 11.5, color: "var(--color-neutral-700)", marginTop: 3 }}>Taranmış PDF&apos;ler için</div>
                    </div>
                    <div style={{ width: 38, height: 20, background: "var(--color-accent)", position: "relative", cursor: "pointer", flexShrink: 0 }}>
                      <div style={{ position: "absolute", top: 3, right: 3, width: 14, height: 14, background: "var(--color-bg)" }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
