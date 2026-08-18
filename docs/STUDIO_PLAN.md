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

### `score` sözleşmesi — CLAUDE.md §1.1

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

Her biri `rag/config.py`'ye **gerekçesiyle** yazılır (CLAUDE.md §1.3).

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

Artefakt üretimi **iş mantığıdır** → `rag/` altına aittir (CLAUDE.md §1.5).
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
işaretliyor · eval 23/23 ve backend testleri sıfır başarısızlıkla geçiyor ·
offline kanıtı 0 soket.

### Faz 2 — Report Generator — **KAPANDI**

**Başarı:** raporun her cümlesi bir chunk'a bağlı · sadakat skoru ≥0.90
(oran: grounded/toplam — ortalama cosine değil, bkz. FEATURE_SPEC §9.11) ·
bağlanamayan iddia rapordan çıkarılmış ve sayısı gösteriliyor · Markdown ve
yazdırma çıktısı harici kaynak içermiyor.

**Ek kapanma koşulu — entailment boşluğu.** Faz 1'in bıraktığı bilinen sınır:
sadakat kapısı *grounding* ölçüyor, *entailment* değil; ürünle çelişen ama
konuya yakın bir iddia 0.5487 ile `grounded` geçiyor
(`eval/fidelity_trap.py`, PROJE_DURUMU.md "Bilinen sınır"). Faz 2, bu iddianın
üretilen rapordan **düşürüldüğü** ve düşürülen iddia sayısının kullanıcıya
gösterildiği ölçümle kanıtlanmadan kapanmaz. Telafi ikinci bir katmandır —
`FIDELITY_MIN_SCORE` yükseltilerek değil (o alternatif reddedildi, §9.6).

**Ölçüldü ve karşılandı** (`eval/report_trap.py`, eval.db, 7 küme / 9 LLM
çağrısı): 48 iddia · 44'ü rapora girdi · 4'ü düşürüldü · tuzak
`artifact_claims`'te hâlâ **0.5487 / grounded** ama `node_path` `/dropped/1`,
yani `sections` altında değil · rapor gövdesinde "gpt"/"openai" **0 eşleşme** ·
`fidelity_score` **1.0000** · `dropped_count` SSE `complete`'te,
`ArtifactDetail`'de ve arayüzde görünüyor.

> [!warning] Bu planın ikinci katman tarifi ölçümle DÜZELTİLDİ
> Katmanın ilk hâli terimi yalnızca doküman frekansına göre "ayırt edici"
> sayıyordu; gerçek üretilmiş raporda **47 cümlenin 42'sini** düşürdü, çünkü
> 20 chunk'lık korpusta sıradan Türkçe çekim de df=0 alıyor. Kurala ikinci bir
> şart eklendi (terim ayrıca **varlık benzeri** olmalı: rakam / iç tire-nokta /
> cümle başı olmayan büyük harf) ve aynı koşumda 43/47 cümle rapora girdi.
> Tam ölçüm tablosu ve elenen alternatifler: `FEATURE_SPEC §10.6`,
> `PROJE_DURUMU.md` "Faz 2'nin ölçümle çürüttüğü kendi kalibrasyonu".

### Faz 3 — Mind Map — **KAPANDI**

**Başarı:** harita korpustan otomatik · her düğüm kaynağa tıklanabilir ·
SVG'de harici kaynak yok · klavyeyle gezilebilir (WCAG AA) · 12 kümede
okunabilir kalıyor.

**Ölçüldü ve karşılandı** (`eval/mindmap_proof.py`, eval.db, 7 küme / 7 LLM
çağrısı, 13/13 kontrol): 8 düğüm (1 kök + 7 konu) · 20 chunk'ın 20'si bir
düğümde · her düğümün her chunk'ı için atıf · **7/7 etiket modelden** ·
2 kenar (0.6094, 0.5520), ağırlıklar `topic_similarity` ile birebir ·
`fidelity_score` 1.0000 · markdown'da `http(s)://` yok · kümeleme determinist.

> [!warning] `d3-hierarchy` KURULMADI — §7'nin "tek yeni npm bağımlılığı" ifadesi geçersiz
> Bu harita iki seviyelidir (kök → konular); radyal yerleşim `angle = 2π·i/N`,
> yani ~20 satır. d3-hierarchy'nin değeri derin/düzensiz ağaçların düğüm
> ayrıştırmasıdır ve burada hiç kullanılmazdı. `package.json` **değişmedi**.
> Tam gerekçe: `FEATURE_SPEC §11.9`.

> [!warning] Planın "5. düğüm → merkeze en yakın chunk → artifact_claims" adımı DEĞİŞTİ
> İddia olarak bağlanan şey chunk değil, modelin **etiketidir** — hallüsinasyon
> riski taşıyan tek metin odur. Ayrıca kapıdan geçemeyen etiketin düğümü
> **silinmez**: ad korpustan türer (`topics.topic_title`), öneri `dropped`'a
> sebebiyle yazılır (`FEATURE_SPEC §11.5`).

### Faz 4 — Quiz Generator — **KAPANDI**

**Başarı:** her sorunun cevabı korpusta doğrulanabilir · çeldiriciler makul
ama yanlış (rastgele değil) · sorular kümelere dağılmış · quiz üretimi ~~eval
setine kendi kategorisi olarak eklendi~~ **kendi koşucusuyla ölçüldü** (aşağı
bkz.).

**Ölçüldü ve karşılandı** (`eval/quiz_proof.py`, eval.db, 7 küme, 16/16
kontrol): 7 soru (3 true_false · 3 short_answer · 1 fill_blank) · her sorunun
cevabı korpustan doğrulanabilir · çeldiriciler soru chunk'ında geçmiyor ·
cevap anahtarıyla deneme **1.0 (4/4)**, alakasız cevapla **0.0** ·
`short_answer` hiçbir eşiğe indirgenmiyor (`correct=None`) · `--trap`
koşumunda tuzaklı soru quiz'e **alınmadı**, gövdede "gpt"/"openai" **0
eşleşme**.

> [!warning] §6.3'ün "LLM yalnızca dilbilgisel uyum için düzenler" adımı KALDIRILDI
> Çeldiricilere LLM **hiç dokunmuyor**: havuz başka kümelerin gerçek korpus
> terimleri, yanlışlıkları soru chunk'ında geçmedikleri kontrol edilerek
> **kanıtlanıyor**. LLM'e "makul ama yanlış bir şık yaz" demek, yanlışlığı
> ölçülemeyen bir metni cevap anahtarına koymaktır — kapı grounding ölçüyor,
> entailment değil (§9.6'nın bilinen sınırı). Bedeli de sıfır: soru başına bir
> çağrı eksiliyor.

> [!warning] §6.3'ün `true_false` kurgusu ve eşanlamlı listesi DEĞİŞTİ
> `true_false` **kaynak atfı** üzerinden kurulur ("bu bilgi X belgesinde
> geçiyor") — doğruluk değeri metadata'dan kesindir. Denenen sayısal-mutasyon
> kurgusu ölçümle elendi (eval.db'de 1/7 kapsama). `fill_blank`'in "eşanlamlı
> listesi" reddedildi: dışarıdan sözlük getirmek ikinci bir bakım yüzeyi
> açardı (§10.15'in aynı gerekçesi). Tam ölçümler: `FEATURE_SPEC §12.4`.

> [!warning] Quiz `eval_set.json`'a EKLENMEDİ — Faz 4 kriteri düzeltildi
> Gerekçe §10.1.1'in birebir aynısı: `eval_set.json` tek bir hattı
> (`query_router → retrieve → answer`) ölçüyor; quiz üretimini o şekle sokmak
> "23/23"ün ne ölçtüğünü **sessizce** genişletirdi ve her teslime dakikalar +
> bir 7B yüklemesi bindirirdi. Ölçüm `eval/quiz_proof.py` ile, `report_trap.py`
> ile aynı sınıfta yapılır. **Eval seti 23 soruda kaldı.**

## 10. Her fazda değişmeyen kapı

Hiçbir faz şunlar korunmadan kapanmaz:

```bash
.venv/bin/python eval/run_eval.py                 # 23/23
.venv/bin/python -m pytest backend/tests -q       # sıfır başarısızlık
.venv/bin/python eval/offline_proof.py            # 0 soket
.venv/bin/python eval/fidelity_trap.py            # PASS, 0.5487 / grounded
cd web && npm run build && npm run lint           # temiz
```

Backend testinin sayısı kapıya **yazılmaz** (Faz 1'de "91/91" bayat kalıp
regresyonu yeşil göstermişti; gerçek taban 93'tü, Faz 2 sonrası 151, Faz 4
sonrası **201**). Kapı "sıfır başarısızlık"tır; sayı yalnızca teslim kaydında
anılır.

Faz kapanma ölçümleri bu listede **yoktur** ve kasıtlıdır — her biri bir kerelik
ölçümdür, dakikalar sürer ve rutin kapıya eklenmesi her teslime bir 7B
yüklemesi bindirirdi:

| Koşucu | Faz | Ne gösterir |
|---|---|---|
| `eval/report_trap.py` | 2 | Ürün, entailment'ı geçemeyen cümleyi **yayımlamıyor** (§10.13) |
| `eval/mindmap_proof.py` | 3 | Yapı modelden **gelmiyor**, etiket denetleniyor (§11.10) |
| `eval/quiz_proof.py` | 4 | Cevap anahtarı korpustan **doğrulanıyor** (§12.12) |
| `eval/ui_proof.py` | 2–4 | React katmanı gerçek Chromium'da çalışıyor (42 kontrol) |

`ui_proof.py` diğer üçünden bir yönüyle ayrılır: **model yüklemez** (üreticiler
sahtelenir) ve tek bir fazın değil, üç görünümün tamamının ölçümüdür. Yine de
rutin kapıda değildir -- `playwright` + Chromium ister ve bunlar
`requirements-dev.txt`'tedir (ürün yolunda tarayıcı yok, CLAUDE.md §1.2).
