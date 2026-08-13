# Design System — Local RAG Assistant v2

> **Bu doküman bir sözleşmedir, öneri değil.** Faz 4'te beş agent paralel
> çalışacak ve hepsi buradaki token isimlerine bağlı olacak. Token adları
> dondurulmuştur; değişirse tüm agent çıktıları etkilenir.
>
> Kural: **hiçbir bileşende sabit renk (hex) yazılmaz.** Her renk bir CSS
> değişkeninden okunur.

---

## 1. Renk Token'ları

### 1.1 Temel palet

| Token | Light | Dark | Kullanım |
|---|---|---|---|
| `--primary` | `#4F46E5` | `#818CF8` | Ana eylem, aktif durum, odak halkası |
| `--primary-hover` | `#4338CA` | `#A5B4FC` | Hover/active |
| `--primary-fg` | `#FFFFFF` | `#0A0A0B` | Primary zemin üzerindeki metin |
| `--accent` | `#9333EA` | `#C084FC` | AI/üretim göstergesi, vurgu |
| `--background` | `#FFFFFF` | `#0A0A0B` | Sayfa zemini |
| `--surface` | `#F9FAFB` | `#141416` | Kart, sidebar, panel |
| `--surface-raised` | `#FFFFFF` | `#1C1C1F` | Modal, dropdown, popover |
| `--border` | `#E5E7EB` | `#27272A` | Ayırıcı, kart kenarı |
| `--border-strong` | `#D1D5DB` | `#3F3F46` | Girdi kenarı, vurgulu ayırıcı |
| `--text-primary` | `#111827` | `#FAFAFA` | Başlık, gövde |
| `--text-secondary` | `#6B7280` | `#A1A1AA` | Açıklama, ikincil bilgi |
| `--text-tertiary` | `#6B7280` | `#8B8B93` | Metadata, zaman damgası |

> [!warning] `--text-tertiary` neden `--text-secondary` ile aynı (light)?
> Taslakta `#9CA3AF` önerilmişti; ölçtüğümde beyaz üzerinde **2.54:1** çıktı —
> AA eşiği 4.5:1. Görsel hiyerarşiyi renk yerine **boyut ve ağırlıkla** kuruyoruz
> (Caption 12px/500 vs Body 14px/400). Erişilebilirlikten ödün vermek yerine
> hiyerarşi aracını değiştirmek doğru tercih.

### 1.2 Semantik katman — retrieval güven skoru

Bu, ürünün ayırt edici tarafı. Renk burada dekorasyon değil, **güven sinyali**.

Bantlar `rag/config.py`'deki gerçek ölçümlere dayanır: cevabı olan sorular
**0.65–0.84**, olmayanlar **0.43–0.74** aralığında skor alıyor; `MIN_SCORE = 0.45`.

| Bant | Aralık | Anlam | Light | Dark |
|---|---|---|---|---|
| Güçlü | ≥ 0.70 | Yüksek güven, cevaplanabilir aralığın üstü | `#047857` | `#34D399` |
| Orta | 0.55 – 0.70 | Kullanılabilir ama tek başına yeterli olmayabilir | `#B45309` | `#FBBF24` |
| Zayıf | `MIN_SCORE` – 0.55 | Eşiği ancak geçti | `#DC2626` | `#F87171` |
| Elendi | < `MIN_SCORE` | LLM'e hiç gitmedi | `#6B7280` | `#8B8B93` |

> [!danger] Eşik değeri koda gömülmez
> "Elendi" sınırı `MIN_SCORE`'dur ve **backend'den gelir** (`/api/health` veya
> `/api/metrics` yanıtında). Frontend `0.45` sayısını asla literal yazmaz —
> config değişirse UI kendiliğinden takip etmeli.

> [!tip] Renk tek başına bilgi taşımaz
> Renk körlüğü için her `ScoreBadge` **üç sinyali birlikte** verir:
> renk + sayısal skor + ikon (güçlü `●●●`, orta `●●○`, zayıf `●○○`, elendi `○○○`).
> Renk kaldırılsa bile bilgi tam okunur olmalı.

### 1.3 Durum renkleri

| Token | Light | Dark | Kullanım |
|---|---|---|---|
| `--success` | `#047857` | `#34D399` | Yükleme tamamlandı |
| `--warning` | `#B45309` | `#FBBF24` | Atlanan sayfa, OCR uyarısı |
| `--danger` | `#DC2626` | `#F87171` | Hata, silme eylemi |
| `--info` | `#4F46E5` | `#818CF8` | Bilgilendirme |
| `--ocr-badge` | `#B45309` | `#FBBF24` | OCR'dan gelen chunk işareti |

`--ocr-badge` ayrı bir token: OCR metni tanım gereği daha az güvenilir,
kullanıcı bunu skordan bağımsız görmeli.

### 1.4 Kontrast doğrulaması (ölçüldü, iddia değil)

Tüm metin/zemin çiftleri WCAG AA (≥ 4.5:1) üstünde:

| Token | Light | Dark |
|---|---|---|
| `--text-primary` | 17.74:1 | 18.96:1 |
| `--text-secondary` | 4.83:1 | 7.72:1 |
| `--text-tertiary` | 4.83:1 | 5.85:1 |
| `--primary` | 6.29:1 | 6.63:1 |
| `--accent` | 5.38:1 | 7.49:1 |
| Skor · güçlü | 5.48:1 | 10.29:1 |
| Skor · orta | 5.02:1 | 11.85:1 |
| Skor · zayıf | 4.83:1 | 7.15:1 |
| Skor · elendi | 4.83:1 | 5.85:1 |

Yeni bir renk eklenirse aynı hesap tekrarlanmalı — `docs/` altındaki kontrast
script'i ile.

---

## 2. Tipografi

### 2.1 Font ailesi

| Rol | Font | Neden |
|---|---|---|
| UI | **Inter** | Yüksek x-height, dar alanda okunaklı; Linear/Notion'ın da tercihi |
| Mono | **JetBrains Mono** | Skor, chunk metni, kod; rakamları ayırt edici |

> [!danger] CDN kullanılmaz
> Google Fonts CDN offline iddiasını **bozar**. Fontlar `.woff2` olarak
> `web/app/fonts/` altına indirilir ve `next/font/local` ile bundle'a gömülür.
> Faz 4.1.4'ün kabul kriteri: build çıktısında hiçbir dış font isteği olmaması.
> Yalnızca kullanılan ağırlıklar (400/500/600) paketlenir.

### 2.2 Ölçek

| Rol | Boyut / satır | Ağırlık | Kullanım |
|---|---|---|---|
| Display | 30 / 36 | 600 | Metrics sayfası başlığı |
| H1 | 24 / 32 | 600 | Sayfa başlığı |
| H2 | 18 / 28 | 600 | Panel başlığı |
| H3 | 15 / 22 | 600 | Kart başlığı |
| Body | 14 / 22 | 400 | Gövde, mesaj metni |
| Body small | 13 / 20 | 400 | Chunk önizleme |
| Caption | 12 / 16 | 500 | Metadata, rozet |
| Mono | 12 / 16 | 500 | Skor değeri |

14px gövde bilinçli: Linear/Notion yoğunluğu buradan gelir. 16px "tüketici
uygulaması" hissi verir ve üç kolonlu düzende yer kaybettirir.

---

## 3. Spacing, Radius, Shadow

**Spacing** — 4px tabanlı: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`
Kart/panel iç boşluğu 24, bölüm arası 32, sıkışık liste öğesi 8–12.

**Radius**

| Token | Değer | Kullanım |
|---|---|---|
| `--radius-sm` | 6px | Rozet, chip |
| `--radius-md` | 8px | Buton, girdi |
| `--radius-lg` | 12px | Kart, panel |
| `--radius-xl` | 16px | Modal |

**Shadow** — yalnızca light mode'da anlamlıdır.

| Token | Light | Dark |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgb(0 0 0 / .05)` | `none` |
| `--shadow-md` | `0 4px 12px rgb(0 0 0 / .08)` | `none` |
| `--shadow-lg` | `0 12px 32px rgb(0 0 0 / .12)` | `none` |

> [!info] Dark mode'da katman gölgeyle değil, yüzey açıklığıyla kurulur
> `--background` → `--surface` → `--surface-raised` giderek açılır. Gölge
> koyu zeminde görünmez; dark'ta `--border` taşıyıcı rol alır.

---

## 4. Breakpoint ve Layout Davranışı

| | Genişlik | Sidebar | Chat | Inspector |
|---|---|---|---|---|
| Mobile | < 768px | Drawer (`Sheet`) | Tam genişlik | Drawer (`Sheet`) |
| Tablet | 768–1279px | Kalıcı, 240px | Esnek | Overlay drawer |
| Desktop | ≥ 1280px | Kalıcı, 260px | Esnek (min 480px) | **Kalıcı, 380px** |

> [!important] Inspector masaüstünde neden kalıcı?
> Açıklanabilirlik bu ürünün farkıdır. Gizlenmiş bir panel "opsiyonel özellik"
> okunur; kalıcı kolon "ürünün kendisi" okunur. Sohbet alanını daraltma
> bedeline değer.

Mobilde Inspector'a erişim: her asistan mesajının altındaki "Kaynakları
incele" butonu drawer'ı açar.

---

## 5. Hareket

| Etkileşim | Süre | Easing |
|---|---|---|
| Hover/focus | 120ms | `ease-out` |
| Panel/drawer açılış | 200ms | `cubic-bezier(.32,.72,0,1)` |
| Token akışı | animasyonsuz | — |
| İskelet (skeleton) | 1.5s döngü | `ease-in-out` |

Token akışında animasyon **yok**: metin zaten hareket ediyor, üzerine
animasyon eklemek okunabilirliği bozar. Yalnızca yanıp sönen imleç.

`prefers-reduced-motion: reduce` altında tüm süreler 0'a iner.

---

## 6. Bileşen Ağacı ve Dosya Sahipliği

> Her agent **yalnızca** kendi satırındaki dosyaları yazar. Dışına çıkmak
> paralel çalışmayı bozar.

| Bileşen | Dosya | Sahip |
|---|---|---|
| **Token katmanı** | `web/app/globals.css` | `design-system` |
| shadcn primitives | `web/components/ui/**` | `design-system` |
| `ScoreBadge` | `web/components/ui/score-badge.tsx` | `design-system` |
| `RelevanceBar` | `web/components/ui/relevance-bar.tsx` | `design-system` |
| `OcrBadge` | `web/components/ui/ocr-badge.tsx` | `design-system` |
| `ThemeProvider` / toggle | `web/components/theme-*.tsx` | `design-system` |
| i18n altyapı + ortak metinler | `web/lib/i18n/index.ts`, `common.ts` | `design-system` |
| — | — | — |
| `AppShell` | `web/components/shell/app-shell.tsx` | `frontend-kb` |
| `DocumentUploader` | `web/components/sidebar/document-uploader.tsx` | `frontend-kb` |
| `DocumentList` / `DocumentCard` | `web/components/sidebar/document-*.tsx` | `frontend-kb` |
| `SystemStatus` / `CorpusStats` | `web/components/sidebar/*.tsx` | `frontend-kb` |
| Sidebar metinleri | `web/lib/i18n/sidebar.ts` | `frontend-kb` |
| — | — | — |
| `ChatPanel` / `MessageList` | `web/components/chat/chat-panel.tsx` | `frontend-chat` |
| `StreamingText` | `web/components/chat/streaming-text.tsx` | `frontend-chat` |
| `ChatInput` / `ThinkingIndicator` | `web/components/chat/*.tsx` | `frontend-chat` |
| `SourceChips` | `web/components/chat/source-chips.tsx` | `frontend-chat` |
| `RetrievalInspector` / `ChunkCard` | `web/components/inspector/**` | `frontend-chat` |
| Chat metinleri | `web/lib/i18n/chat.ts` | `frontend-chat` |
| — | — | — |
| Metrics sayfası ve grafikleri | `web/components/metrics/**` | `metrics-ui` |
| Metrics metinleri | `web/lib/i18n/metrics.ts` | `metrics-ui` |
| — | — | — |
| API istemcisi + tipler | `web/lib/api.ts`, `web/lib/types.ts` | **entegrasyon (ben)** |
| SSE ayrıştırıcı | `web/lib/sse.ts` | **entegrasyon (ben)** |
| Sayfa/layout | `web/app/layout.tsx`, `web/app/page.tsx` | **entegrasyon (ben)** |

`lib/api.ts` ve `lib/types.ts`'i bilinçli olarak kimseye vermiyorum: üç
frontend agent'ı da bunları okuyacak, ortak dosyayı paralel yazmak en yüksek
çakışma riski.

> [!note] `lib/sse.ts` sahipliği değişti (Wave 2 öncesi)
> Bu dosya ilk taslakta `frontend-chat`'e verilmişti. Wave 2 başlamadan
> entegrasyona alındı: sohbet akışı (`POST /api/chat`) ve belge yükleme
> ilerlemesi (`POST /api/documents`) **aynı** wire format'ı kullanıyor
> (`backend/sse.py`). İki agent'ın aynı düşük seviye ayrıştırıcıyı ayrı ayrı
> yazması hem tekrar hem tutarsızlık riskiydi. `frontend-chat` ve
> `frontend-kb` bunun üzerine kendi özelliğe özgü tüketim mantıklarını kurar.

---

## 7. i18n Şeması

**Namespace başına bir dosya** — çakışmayı yapısal olarak imkânsız kılar.

```
web/lib/i18n/
├── index.ts        # LanguageProvider, useT() hook, tip birleştirme
├── common.ts       # buton, hata, ortak eylemler       [design-system]
├── sidebar.ts      # belge yönetimi                    [frontend-kb]
├── chat.ts         # sohbet + inspector                [frontend-chat]
└── metrics.ts      # metrics sayfası                   [metrics-ui]
```

**Kayıt biçimi** — anahtar başına iki dil yan yana; eksik çeviri derleme
hatası verir:

```ts
export const sidebar = {
  uploadTitle:   { tr: "PDF yükleyin",        en: "Upload PDF" },
  emptyState:    { tr: "Henüz belge yok",     en: "No documents yet" },
  pagesSkipped:  {
    tr: (n: number) => `${n} sayfa okunamadı`,
    en: (n: number) => `${n} page(s) could not be read`,
  },
} as const;
```

**Adlandırma kuralı:** `camelCase`, alan öneki yok (namespace zaten ayırıyor).
Çoğul/sayı içeren metinler fonksiyon olarak yazılır — string birleştirme ile
dil kurgulanmaz.

> [!warning] Motor dili değişmiyor
> `NO_ANSWER_TEXT` ("Bu bilgi yüklediğiniz belgelerde yok.") **backend'den
> Türkçe gelir** çünkü LLM'in system prompt'una gömülüdür ve modelin çıktısıdır.
> UI dili İngilizce iken bu metin geldiğinde frontend onu tanıyıp
> `chat.noAnswer` anahtarıyla **değiştirir**. Backend'den gelen ham metin
> doğrudan basılmaz.

---

## 8. Faz 2 Tamamlanma Kriterleri

- [x] Light + dark için eksiksiz token tablosu (renk, tipografi, spacing, radius, shadow)
- [x] Skor semantiği eşik değerleriyle tanımlı ve `config.MIN_SCORE`'a bağlı
- [x] Üç breakpoint için layout davranışı yazılı
- [x] Bileşen ağacı, her bileşen sahibi agent ile eşleşmiş
- [x] i18n namespace şeması tanımlı (çakışma önleyici)
- [x] **Kontrast oranları ölçüldü** — tümü AA üstünde; taslakta AA'da kalan
      altı değer düzeltildi

**Dondurulan:** token adları, skor bant sınırları, dosya sahipliği matrisi,
i18n namespace deseni.
