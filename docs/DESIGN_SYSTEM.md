# Design System — Local RAG Assistant v2

> **Bu doküman bir sözleşmedir, öneri değil.** Faz 4'te beş agent paralel
> çalışacak ve hepsi buradaki token isimlerine bağlı olacak. Token adları
> dondurulmuştur; değişirse tüm agent çıktıları etkilenir.
>
> Kural: **hiçbir bileşende sabit renk (hex) yazılmaz.** Her renk bir CSS
> değişkeninden okunur.
>
> **Modernist v3 (Faz 1, `FEATURE_SPEC §13`):** token **adları** aynı kaldı;
> **değerleri** Modernist palete yeniden ayarlandı (sıcak-gri zemin, kırmızı
> marka, radius=0, tek aile Archivo). Açık **ve** koyu tema korunur; tüm
> çiftler `docs/check_contrast.py` ile yeniden doğrulandı (§1.4).

---

## 1. Renk Token'ları

### 1.1 Temel palet

| Token | Light | Dark | Kullanım |
|---|---|---|---|
| `--primary` | `#C02D18` | `#FF9783` | Ana eylem, aktif durum, odak halkası, buton dolgusu |
| `--primary-hover` | `#AE1800` | `#FFC4B8` | Hover/active |
| `--primary-fg` | `#FFFFFF` | `#1A1918` | Primary zemin üzerindeki metin |
| `--accent` | `#AE1800` | `#FF9783` | AI/üretim göstergesi, vurgu (metin olarak) |
| `--background` | `#F3F2F2` | `#1A1918` | Sayfa zemini |
| `--surface` | `#EAE9E9` | `#232120` | Kart, sidebar, panel |
| `--surface-raised` | `#F8F4F4` | `#2D2B2B` | Modal, dropdown, popover |
| `--border` | `#D7D3D3` | `#3A3736` | Ayırıcı, kart kenarı |
| `--border-strong` | `#7D7979` | `#605D5D` | Girdi kenarı, vurgulu ayırıcı |
| `--text-primary` | `#201E1D` | `#F8F4F4` | Başlık, gövde |
| `--text-secondary` | `#605D5D` | `#BAB6B6` | Açıklama, ikincil bilgi |
| `--text-tertiary` | `#605D5D` | `#9B9797` | Metadata, zaman damgası |

> [!note] Marka kırmızısı: `--primary` neden `#C02D18`, canlı `#EC3013` değil?
> Mockup'ın canlı kırmızısı (`#EC3013`) beyaz metinle yalnızca **4.20:1** verir
> (AA altı). `--primary` etkileşimli dolgu olarak beyaz metinle **5.79:1**, zemin
> üstünde metin olarak **min 4.77:1** okunur; bu yüzden bir basamak koyu tuğla
> (`#C02D18`) seçildi — göze hâlâ canlı marka kırmızısı. `--accent` (metin olarak
> vurgu) daha da koyu `#AE1800`, çünkü metnin zemin üstünde geçmesi gerekir.

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
| Orta | 0.55 – 0.70 | Kullanılabilir ama tek başına yeterli olmayabilir | `#8F5600` | `#FBBF24` |
| Zayıf | `MIN_SCORE` – 0.55 | Eşiği ancak geçti | `#9E2F17` | `#F87171` |
| Elendi | < `MIN_SCORE` | LLM'e hiç gitmedi | `#605D5D` | `#9B9797` |

> [!warning] §13.3 — "Zayıf" bandı marka kırmızısından AYRIK olmalı
> Modernist marka vurgusu kırmızı (`--primary`); "zayıf" bandı da kırmızı
> ailesinde. Karışmasınlar diye zayıf **koyu tuğla** seçildi (light `#9E2F17`,
> markadan 1.26× kontrastla; dark `#F87171`, salmon marka `#FF9783`'ten 1.32×).
> Bantlar `MIN_SCORE`'a bağlı kalır, üç-sinyal kuralı (renk+sayı+ikon) korunur;
> renk kaldırılsa bilgi hâlâ okunur.

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
| `--warning` | `#8F5600` | `#FBBF24` | Atlanan sayfa, OCR uyarısı |
| `--danger` | `#9E2F17` | `#F87171` | Hata, silme eylemi |
| `--info` | `#C02D18` | `#FF9783` | Bilgilendirme |
| `--ocr-badge` | `#8F5600` | `#FBBF24` | OCR'dan gelen chunk işareti |

Durum renkleri skor bantlarıyla aynı ölçülmüş değerleri paylaşır (success=güçlü,
warning=orta, danger=zayıf); Modernist'te ayrı bir renk kararı değil, §1.2'nin
kontrastı doğrulanmış tonlarının yeniden kullanımı. `--info` markayla (`--primary`)
aynıdır — Modernist palette ayrı bir bilgi mavisi yoktur.

`--ocr-badge` ayrı bir token: OCR metni tanım gereği daha az güvenilir,
kullanıcı bunu skordan bağımsız görmeli.

### 1.4 Kontrast doğrulaması (ölçüldü, iddia değil)

Tüm metin/zemin çiftleri WCAG AA (≥ 4.5:1) üstünde. Aşağıdaki değerler
`--background` üzerinedir; `check_contrast.py` ayrıca `--surface` ve
`--surface-raised` üzerinde de doğrular ve **en düşük** çift bile AA üstündedir
(light'ta en sıkı: `--primary` on `--surface` = 4.77:1):

| Token | Light | Dark |
|---|---|---|
| `--text-primary` | 14.86:1 | 16.08:1 |
| `--text-secondary` | 5.83:1 | 8.74:1 |
| `--text-tertiary` | 5.83:1 | 6.08:1 |
| `--primary` | 5.18:1 | 8.37:1 |
| `--accent` | 6.41:1 | 8.37:1 |
| Skor · güçlü | 4.91:1 | 9.13:1 |
| Skor · orta | 5.37:1 | 10.52:1 |
| Skor · zayıf | 6.54:1 | 6.35:1 |
| Skor · elendi | 5.83:1 | 6.08:1 |

Yeni bir renk eklenirse aynı hesap tekrarlanmalı — `docs/check_contrast.py` ile
(değerler iddia değil, tekrar üretilebilir ölçüm).

### 1.5 Yazdırma paleti (Studio Faz 2)

Rapor artefaktı tarayıcının kendi yazdırma yolundan PDF'e çıkıyor
(`FEATURE_SPEC §10.12`). `web/app/globals.css`'teki `@media print` bloğu,
**karanlık temada** `.dark` altındaki değerleri geçici olarak §1.1'in **açık**
sütunuyla değiştirir:

| Token | Yazdırmada kullanılan değer | Kaynak |
|---|---|---|
| `--background` | `#F3F2F2` | §1.1 light |
| `--surface` · `--surface-raised` | `#EAE9E9` · `#F8F4F4` | §1.1 light |
| `--border` · `--border-strong` | `#D7D3D3` · `#7D7979` | §1.1 light |
| `--text-primary` · `--text-secondary` · `--text-tertiary` | `#201E1D` · `#605D5D` · `#605D5D` | §1.1 light |
| `--primary` | `#C02D18` | §1.1 light |
| `--warning` | `#8F5600` | §1.3 light |

> [!warning] Bu tablo §1.1/§1.3'ün **kopyasıdır** — ikisi birlikte değişmeli
> Yeni bir renk kararı değil: kâğıt beyazdır, karanlık temanın açık metni
> basıldığında sessizce görünmez olurdu. Değerler `globals.css`'te literal
> yazılıdır çünkü `.dark` bloğu `:root`'un light değerlerini zaten ezmiştir ve
> CSS'te "ezilmiş değeri geri getir" diye bir başvuru yoktur. §1.1 veya §1.3
> değişirse `@media print` bloğu **elle** güncellenmeli; kontrast oranları
> §1.4'ten aynen geçerlidir (birebir aynı çiftler).

Yazdırma seçicileri **ikidir** ve bileşen iç yapısına bağlanmaz:
`[data-print="root"]` (basılacak kök — `ReportView`) ve `[data-print="hide"]`
(kabuk denetimleri — `AppShell`'in header'ı, iki `aside`'ı, iki drawer'ı).

---

## 2. Tipografi

### 2.1 Font ailesi

| Rol | Font | Neden |
|---|---|---|
| UI (gövde + başlık) | **Archivo** | Modernist v3 (§13) ailesi; grotesk karakter, 800'de güçlü başlık |
| Mono | **JetBrains Mono** | Skor, chunk metni, kod; rakamları ayırt edici |

> [!danger] CDN kullanılmaz
> Google Fonts CDN offline iddiasını **bozar**. Fontlar `.woff2` olarak
> `web/app/fonts/` altına indirilir ve `next/font/local` ile bundle'a gömülür.
> Faz 4.1.4'ün kabul kriteri: build çıktısında hiçbir dış font isteği olmaması.
> Archivo için `@fontsource/archivo`'nun `latin` + `latin-ext` altkümeleri
> ağırlık başına (400/600/800) TEK woff2'de birleştirildi; Türkçe glifleri
> (ş ğ ı İ …) tek dosyada tam kapsanıyor. (Önceki Inter dosyaları depoda kalıyor;
> yalnızca geçici `/onizleme` prototipi kullanıyor, Faz 6'da kaldırılacak.)

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

**Radius** — Modernist v3 (§13): **keskin köşe, hepsi 0**.

| Token | Değer | Kullanım |
|---|---|---|
| `--radius-sm` | 0px | Rozet, chip |
| `--radius-md` | 0px | Buton, girdi |
| `--radius-lg` | 0px | Kart, panel |
| `--radius-xl` | 0px | Modal |

> [!note] Ad basamakları neden duruyor?
> Değerler 0'a çekildi ama `sm/md/lg/xl` adları korundu: Tailwind köprüsü
> (`rounded-*`) ve mevcut bileşenler bu adlara bağlı; yalnızca değer değişti,
> yapı kırılmadı.

**Shadow** — yalnızca light mode'da anlamlıdır; Modernist ink-tinted tonlar.

| Token | Light | Dark |
|---|---|---|
| `--shadow-sm` | `0 1px 2px color-mix(in srgb, #2d2b2b 14%, transparent)` | `none` |
| `--shadow-md` | `0 3px 10px color-mix(in srgb, #2d2b2b 16%, transparent)` | `none` |
| `--shadow-lg` | `0 12px 32px color-mix(in srgb, #2d2b2b 22%, transparent)` | `none` |

> [!info] Dark mode'da katman gölgeyle değil, yüzey açıklığıyla kurulur
> `--background` → `--surface` → `--surface-raised` giderek açılır. Gölge
> koyu zeminde görünmez; dark'ta `--border` taşıyıcı rol alır.

---

## 4. Breakpoint ve Layout Davranışı

| | Genişlik | Sol panel | Chat | Alıntı çekmecesi |
|---|---|---|---|---|
| Mobile | < 768px | Drawer (`Sheet`) | Tam genişlik | Drawer (`Sheet`) |
| Tablet | 768–1279px | Kalıcı, 272px | Esnek | Drawer (`Sheet`) |
| Desktop | ≥ 1280px | Kalıcı, 272px | Esnek (min 480px) | Drawer (`Sheet`), 400px |

Sol panel iki sekme taşır — **Kaynaklar** (belgeler) ve **Çıktılar**
(artefaktlar); genişliği bu yüzden 240/260px'ten tek bir 272px'e çıktı
(`FEATURE_SPEC §13.2`).

> [!important] Inspector masaüstünde artık neden kalıcı DEĞİL?
> Bu bir **geri alınan karardır**, kaydı duruyor. v2'nin gerekçesi şuydu:
> "açıklanabilirlik bu ürünün farkıdır; gizlenmiş panel opsiyonel özellik
> okunur, kalıcı kolon ürünün kendisi okunur." Modernist yeniden tasarım
> (§13.2) bunu şu nedenle tersine çevirdi: v3'te açıklanabilirlik **kalıcı
> bir kolonda değil, cümlenin İÇİNDE** duruyor — her iddianın yanındaki
> numaralı üst simge. Kaynak, okurken göz önündedir; çekmece ise o
> numaraya basılınca o alıntıyı açar. Yani sinyal zayıflamadı, taşındı:
> kalıcı kolon "her zaman görünür ama hangi cümleye ait olduğu belirsiz"
> bir listeydi. Kazanç, sohbete geri verilen genişlik.
>
> Kalıcı kolonu korumak §13.6'da değerlendirilmedi çünkü §13.2 yerleşimiyle
> bağdaşmıyor: aynı anda hem kalıcı kolon hem bağlama duyarlı çekmece iki
> ayrı kaynak görünümü demek olurdu.

Çekmeceye erişim: başlık çubuğundaki "Kaynak panelini aç" düğmesi ve her
asistan mesajının altındaki "Kaynakları incele" butonu — her kırılımda.

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
