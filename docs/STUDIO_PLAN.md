# Studio Katmanı — Teknik Plan

> Mind Map, Report Generator ve Quiz Generator'ın mevcut offline RAG motoruna
> eklenmesi. Bu doküman **tasarım kararlarının ve gerekçelerinin** kaydıdır;
> uygulama sırasında spec'e (`docs/FEATURE_SPEC.md`) dönüştürülür.
>
> Referans ürün NotebookLM'dir ama hedef birebir kopya değil: aynı kullanım
> amacını, bu ürünün ölçüm kültürü ve offline kısıtı içinde karşılamak.

## 0. Temel fikir

**Üç modül üç özellik değil, tek bir artefakt hattının üç çıktısıdır.**

```
1. Seçim      chunk'lar hangi stratejiyle gelir          [DETERMİNİSTİK]
2. Yapı       kümeleme / bölüm planı                     [DETERMİNİSTİK]
3. Üretim     etiket / metin / soru                      [TEK LLM ADIMI]
4. Sadakat    her iddia → chunk + ham cosine skor        [KAPI]
5. Render     SVG / HTML / etkileşimli                   [İSTEMCİ]
```

Adım 1, 2, 4, 5 ortaktır. Modül başına değişen yalnızca 3. adım ve payload
şemasıdır. Ayrı ayrı yazılırsa aynı kaynak-bağlama ve sadakat mantığı üç kez,
her seferinde biraz farklı yazılır.

| Modül | Seçim | Yapı | Üretim | Bağ | Render |
|---|---|---|---|---|---|
| Mind Map | tüm korpus | embedding kümeleme | küme etiketi | düğüm→chunk | SVG ağaç |
| Rapor | bölüm başına retrieval | sabit taslak | bölüm metni | cümle→chunk | HTML/MD |
| Quiz | kapsam örnekleme | küme başına kota | soru + çeldirici | cevap→chunk | etkileşimli |

## 1. Planı şekillendiren ölçümler

Bunlar varsayım değil, kod tabanından ve `PROJE_DURUMU.md`'den doğrulanmış:

- **`MAX_ANSWER_TOKENS = 220`** sohbet cevabı için kasıtlı ve doğru, rapor
  bölümü için yetersiz. Ayrı bütçe gerekiyor.
- **Prefill baskın.** İlk token 4.8–5.9 sn, toplam 5.6–7.6 sn. Artefakt üretimi
  çok LLM çağrısı demek → **SSE ilerleme zorunlu**, senkron endpoint kabul
  edilemez. Ayrıca LLM çağrısı sayısı doğrudan gecikme demek.
- **Diller arası ceza −0.077.** Teknik PDF'ler çoğunlukla İngilizce.
- **`store.load_matrix()` L2-normalize matris döndürüyor** → kümeleme için ek
  altyapı gerekmiyor, tek matris çarpımı yeterli.
- **Sağ panel (380px) Inspector'ın** ve yalnızca ≥1280px'te kalıcı. Studio
  onun yerine değil, **yanına sekme** olarak gelir.

## 2. Veritabanı

Mevcut üç tabloya **dokunulmaz**. `_SCHEMA` içine üç tablo eklenir;
`CREATE TABLE IF NOT EXISTS` mevcut veritabanlarını sorunsuz yükseltir.

```sql
CREATE TABLE IF NOT EXISTS artifacts (
    id                 INTEGER PRIMARY KEY,
    kind               TEXT NOT NULL,        -- 'mindmap' | 'report' | 'quiz'
    scope              TEXT NOT NULL,        -- 'corpus' | 'document'
    document_id        INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    title              TEXT NOT NULL,
    params_json        TEXT NOT NULL,
    payload_json       TEXT NOT NULL,        -- ara temsil; render'ın tek girdisi
    corpus_fingerprint TEXT NOT NULL,
    fidelity_score     REAL,
    generation_ms      INTEGER,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind, scope);

CREATE TABLE IF NOT EXISTS artifact_claims (
    id          INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    node_path   TEXT NOT NULL,   -- payload_json'a JSON pointer: /nodes/3
    claim_text  TEXT NOT NULL,
    chunk_id    INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
    score       REAL,            -- HAM COSINE, Hit.score ile aynı ölçek
    verdict     TEXT NOT NULL    -- 'grounded' | 'weak' | 'unsupported'
);
CREATE INDEX IF NOT EXISTS idx_claims_artifact ON artifact_claims(artifact_id);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id           INTEGER PRIMARY KEY,
    artifact_id  INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    score        REAL,
    answers_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_artifact ON quiz_attempts(artifact_id);
```

### `artifact_claims` neden ayrı tablo

"Düğüme tıkla, kaynağa git" özelliği ve sadakat ölçümü **aynı veriye** dayanır.
İkisini ayrı tutmak iki doğruluk kaynağı yaratırdı.

### `score` sözleşmesi — AGENTS.md §1.1

`artifact_claims.score` **ham cosine**dır, tıpkı `Hit.score` gibi. Aynı renk
bantlarıyla (`DESIGN_SYSTEM.md §1.2`) gösterileceği için aynı ölçekte olmak
zorundadır. `verdict` bu skordan türetilir:

- `grounded`   → score ≥ `FIDELITY_MIN_SCORE`
- `weak`       → score ≥ `FIDELITY_MIN_SCORE` − 0.10
- `unsupported`→ altı

Skorun kendisi **asla** yeniden ölçeklenmez.

### `corpus_fingerprint`

`documents` tablosundan deterministik türetilir:
`sha256(sorted(f"{id}:{chunk_count}:{ingested_at}"))`.

Artefakt okunurken mevcut parmak iziyle karşılaştırılır; farklıysa artefakt
**bayat**tır. Silinmez, kullanıcıya "kaynaklar değişti, yeniden üret" olarak
gösterilir. **Sessiz otomatik yeniden üretim yok** — 30–120 sn'lik bir işi
kullanıcının haberi olmadan başlatmak yanlış.

## 3. config sabitleri

Her biri `rag/config.py`'ye **gerekçesiyle** yazılır (AGENTS.md §1.3).

```python
ARTIFACT_SECTION_MAX_TOKENS  = 700   # rapor bölümü; MAX_ANSWER_TOKENS(220) yetmiyor
ARTIFACT_LABEL_MAX_TOKENS    = 40    # mind map düğüm etiketi
ARTIFACT_QUESTION_MAX_TOKENS = 200   # quiz sorusu + çeldiriciler
TOPIC_MIN_CLUSTER_SIZE       = 2     # 20-40 chunk ölçeğinde 2 doğru taban
TOPIC_MAX_CLUSTERS           = 12    # üstü okunamaz harita üretir
FIDELITY_MIN_SCORE           = 0.45  # MIN_SCORE ile AYNI — kasıtlı
```

`FIDELITY_MIN_SCORE`'un `MIN_SCORE`'a eşit olması bilinçlidir: iki ayrı eşik,
iki ayrı kalibrasyon hikâyesi demek olurdu.

## 4. Paket düzeni

```
rag/
  topics.py            # embedding kümeleme (mind map + quiz kapsamı ortak)
  artifacts/
    __init__.py
    base.py            # Artifact protokolü, ortak hat, ilerleme olayları
    fidelity.py        # iddia → chunk bağlama + sadakat skoru (KAPI)
    store.py           # artifacts / artifact_claims / quiz_attempts CRUD
    mindmap.py  report.py  quiz.py
backend/routes/
  artifacts.py         # üretim (SSE), listeleme, okuma, silme, export
  quiz.py              # deneme gönderimi, puanlama, ilerleme
web/components/
  studio/  mindmap/  report/  quiz/
```

Artefakt üretimi **iş mantığıdır** → `rag/` altına aittir (AGENTS.md §1.5).
`backend/routes/artifacts.py` yalnızca SSE yüzeyidir.

## 5. API

Mevcut yedi endpoint'e dokunulmaz.

```
POST   /api/artifacts                 → SSE: stage* → progress* → complete | error
       body: {kind, scope, document_id?, params}
GET    /api/artifacts?kind=&scope=    → ArtifactSummary[]  (payload'sız)
GET    /api/artifacts/{id}            → ArtifactDetail     (payload + claims)
DELETE /api/artifacts/{id}            → DeleteResponse
GET    /api/artifacts/{id}/export?format=md|html
POST   /api/quiz/{artifact_id}/attempt  → AttemptResult
GET    /api/quiz/{artifact_id}/attempts → AttemptSummary[]
```

SSE olayları (çerçeveleme yine `backend/sse.py::sse_event()`):

```
event: stage      {"stage":"clustering","label":"Konular çıkarılıyor"}
event: progress   {"pct":45,"detail":"7/12 küme etiketlendi"}
event: complete   {"artifact_id":3,"fidelity_score":0.91,
                   "generation_ms":48210,"unsupported_count":1}
event: error      {"code":"GENERATION_FAILED","message":"…"}
```

Yeni hata kodları (`FEATURE_SPEC §2.2` ve `web/lib/types.ts::ApiErrorBody`'ye
additive eklenir):

| Kod | HTTP | Ne zaman |
|---|---|---|
| `ARTIFACT_NOT_FOUND` | 404 | id yok |
| `ARTIFACT_STALE` | 409 | Bayat artefakt üzerinde işlem |
| `INSUFFICIENT_CORPUS` | 422 | Kümeleme/quiz için yeterli chunk yok |
| `GENERATION_FAILED` | SSE | Üretim ortada kırıldı |

## 6. Modül tasarımları

### 6.1 Mind Map

**Haritayı LLM'e çizdirmiyoruz.** Yapı embedding'lerden deterministik çıkar;
LLM yalnızca kümelere isim verir.

```
1. store.load_matrix()                   → (N×1024 L2-normalize, meta)
2. agglomerative clustering (cosine)     → küme ağacı        [DETERMİNİSTİK]
   kesme: TOPIC_MAX_CLUSTERS veya mesafe eşiği
3. küme başına merkeze en yakın 3 chunk → LLM: "ortak konu, ≤5 kelime"
4. kenar: küme merkezleri arası cosine > eşik → "ilişkili"
5. düğüm → merkeze en yakın chunk → artifact_claims
6. payload_json: {nodes[], edges[]}
```

Gerekçe: LLM'e "korpusu haritala" demek, düğümlerin belgede gerçekten olup
olmadığını doğrulanamaz kılar. Küme yaklaşımında **her düğüm zaten bir chunk
kümesidir** — hallüsinasyon yapısal olarak imkânsız, yalnızca etiket yanlış
olabilir ve o da tıklanarak doğrulanır. Ayrıca 12 küçük çağrı tek dev çağrıdan
hızlıdır (prefill baskın).

payload şeması:

```json
{ "nodes": [{"id":"n0","label":"Chunking stratejisi","kind":"topic",
             "parent":"root","chunk_ids":[12,15,19],"size":3}],
  "edges": [{"from":"n1","to":"n4","relation":"related","weight":0.71}] }
```

Frontend: **`d3-hierarchy`** (~10 KB, MIT, yalnızca layout matematiği) + elle
yazılmış SVG + pan/zoom hook. React Flow **değil**: 100 KB+ runtime ve kendi
stil sistemi dondurulmuş tasarım sistemiyle çakışır; elle SVG tema token'larını
doğrudan kullanmayı ve kontrast kontrolünü elde tutmayı sağlar.

### 6.2 Report Generator

```
1. taslak SABİT (LLM değil): Executive Summary · Key Findings ·
   Detailed Analysis (küme başına alt bölüm) · Tables · Citations
2. bölüm başına retrieval:
   Key Findings → küme merkezlerinin en yüksek skorlu chunk'ları
   Detailed §k  → küme k'nın chunk'ları
   Exec Summary → EN SON; girdisi diğer bölümlerin çıktısı
3. bölüm metni: ARTIFACT_SECTION_MAX_TOKENS ile ayrı çağrı
4. atıf: her cümle → en yakın chunk (cosine) → artifact_claims
5. tablolar: korpus metadatası (belge × konu kapsama) [DETERMİNİSTİK]
```

**Charts kapsamı — dürüst sınır.** NotebookLM'in grafikleri sayısal veri
tablolarından gelir; bu korpus düz metindir. Prozadan sayı uydurup grafik
çizmek sadakat ilkesinin doğrudan ihlalidir. Çizilecek olan, gerçekten elimizde
olan veri: belge × konu kapsama matrisi, konu başına chunk dağılımı, sadakat
skoru dağılımı. Belgedeki sayısal tabloları çıkarmak **ayrı bir modüldür**
(Data Table, sonraki faz).

**Export.** Markdown: `payload_json`'dan doğrudan, atıflar mevcut
`[Kaynak: dosya.pdf s.4]` biçiminde. PDF: yerel headless tarayıcı yok ve
eklenmeyecek → `@media print` CSS + tarayıcının kendi "PDF olarak kaydet"i.
Sıfır bağımlılık, tam offline.

### 6.3 Quiz Generator

En zor kısım soru üretimi değil, **çeldirici** üretimidir.

```
1. kapsam: konu kümesi başına kota (sorular tek chunk'a sıkışmasın)
2. chunk seçimi: küme içinden skoru yüksek, birbirine uzak chunk'lar
3. soru üretimi (tip başına ayrı prompt):
   multiple_choice | true_false | fill_blank | short_answer
4. ÇELDİRİCİ (hibrit — kilit nokta):
   - aday havuzu: embedding uzayında doğru cevaba YAKIN ama FARKLI
     chunk'lardan çıkarılan ifadeler → makul görünür
   - LLM yalnızca dilbilgisel uyum için düzenler, sıfırdan uydurmaz
   - kontrol: çeldirici kaynak chunk'ta doğru cevap olarak geçiyorsa ELENİR
5. cevap anahtarı → kaynak chunk → artifact_claims (verdict zorunlu 'grounded')
```

Puanlama:

| Tip | Puanlama | Güvenilirlik |
|---|---|---|
| `multiple_choice` | Tam eşleşme | Deterministik |
| `true_false` | Tam eşleşme | Deterministik |
| `fill_blank` | Normalize eşleşme + eşanlamlı listesi | Deterministik |
| `short_answer` | Referans cevapla embedding benzerliği | **Yaklaşık** |

`short_answer` zayıf halkadır ve gizlenmez: puan bir eşik değil **benzerlik
skoru** olarak gösterilir, yanına kaynak chunk konur, kullanıcı kendi
doğrulamasını yapar. LLM-hakem kullanılmaz — her soru için ek çağrı demek
(prefill baskın) ve hakem aynı modelin yanlılığını taşır.

## 7. Frontend yerleşimi

Mevcut üç kolonlu kabuk (`AppShell`) **korunur**. NotebookLM'de sağ panel
yalnızca Studio'dur; bizde Inspector zaten oradadır ve ürünün ayırt edici
özelliğidir. Çözüm: sağ panel **sekmeli** olur.

```
Sources (mevcut) | Chat / Artefakt görüntüleyici | [Inspector | Studio]
```

Artefakt açıkken `<main>` onu gösterir (MindMapCanvas | ReportView |
QuizRunner), Inspector ise **o artefaktın** düğüm/iddia kaynaklarını gösterir —
aynı `ChunkCard` bileşeni, yeni bağlam.

Yeni bileşenler mevcut primitive'leri yeniden kullanır: `Card`, `Badge`,
`ScoreBadge`, `Progress`, `Dialog`, `ScrollArea`, `ChunkCard`,
`MarkdownContent`, `SourceChips`, `metrics/scale.ts`.

Tek yeni npm bağımlılığı: `d3-hierarchy`. Her yeni metin
`web/lib/i18n/studio.ts`'e TR/EN olarak eklenir.

## 8. Kapsam dışı — ve nedeni

**Audio / Video Overview.** Kaliteli TTS yerel model gerektirir; Foundry Local
kataloğunda yok. Bulut TTS eklemek ürünün tek satış argümanını siler. Bu bir
eksiklik değil, kısıta sadakattir.

**Slide Deck / Infographic / Data Table.** Aynı hattın farklı render'ları veya
farklı şemaları. Faz 1–4 tamamlanıp hat kanıtlandıktan sonra değerlendirilir.

## 9. Fazlar

Sıra keyfi değildir: Faz 1 diğerlerinin üzerine kurulduğu hattır; Faz 2 hattı
en basit artefakt tipiyle doğrular.

### Faz 1 — Artefakt hattı ve kümeleme temeli

3 tablo + `corpus_fingerprint` · `rag/topics.py` · `rag/artifacts/base.py` ·
`fidelity.py` · `rag/artifacts/store.py` · `backend/routes/artifacts.py`
iskelet · config sabitleri · 4 hata kodu · `studio-panel` boş durumu.

**Başarı:** kümeleme 7 belgelik korpusta anlamlı konu veriyor (elle
doğrulanır) · sadakat kapısı bilinçli bozuk bir iddiayı `unsupported`
işaretliyor · eval 23/23 ve backend 91/91 bozulmadı · offline kanıtı 0 soket.

### Faz 2 — Report Generator

**Başarı:** raporun her cümlesi bir chunk'a bağlı · sadakat skoru ≥0.90 ·
bağlanamayan iddia rapordan çıkarılmış ve sayısı gösteriliyor · Markdown ve
yazdırma çıktısı harici kaynak içermiyor.

### Faz 3 — Mind Map

**Başarı:** harita korpustan otomatik · her düğüm kaynağa tıklanabilir ·
SVG'de harici kaynak yok · klavyeyle gezilebilir (WCAG AA) · 12 kümede
okunabilir kalıyor.

### Faz 4 — Quiz Generator

**Başarı:** her sorunun cevabı korpusta doğrulanabilir · çeldiriciler makul
ama yanlış (rastgele değil) · sorular kümelere dağılmış · quiz üretimi eval
setine kendi kategorisi olarak eklendi.

## 10. Her fazda değişmeyen kapı

Hiçbir faz şunlar korunmadan kapanmaz:

```bash
.venv/bin/python eval/run_eval.py                 # 23/23
.venv/bin/python -m pytest backend/tests -q       # 123/123 (Faz 1 sonrası)
.venv/bin/python eval/offline_proof.py            # 0 soket
```
