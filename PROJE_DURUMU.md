# Proje Durumu

> Bu dosya projenin güncel teknik durumunu, alınan kararları ve gerekçelerini
> özetler. Aşağıdaki her sonuç koddan veya ölçümden doğrulanmıştır; hiçbiri
> varsayım değildir.

## Proje

Microsoft Türkiye AI Innovators programı kapsamında geliştirilen, Foundry
Local üzerinde **tamamen offline çalışan Türkçe bir PDF belge Q&A asistanı**.
Kullanıcı PDF yükler, sistem belgeyi parçalayıp embed eder; sorular yalnızca
yüklenen belgelerden, kaynak atıflı olarak cevaplanır.

Motor (RAG çekirdeği) tamamlanmış ve ölçülmüş durumda. Streamlit/CLI
prototipinden, portföy niteliğinde bir SaaS ürününe dönüşüm (FastAPI
backend + Next.js frontend) Faz 4 itibarıyla tamamlandı (bkz. "v2
Dönüşümü" bölümü). Faz 4'ten sonra, ürünleşme sonrası ölçülen bir üretim
hatasından (bkz. "Sorgu yönlendirme" bölümü) başlayan altı maddelik bir
sağlamlaştırma turu da tamamlandı; offline kanıtı dahil hiçbir açık iş
kalmadı. Ardından **Studio katmanının dört fazı** eklendi: artefakt hattı
(Faz 1), Rapor (Faz 2), Zihin Haritası (Faz 3) ve Quiz (Faz 4) — üçü de aynı
hattan geçiyor ve her biri kendi kapanma ölçümüyle teslim edildi.

## Ortam

Apple M4 MacBook Air, 16 GB RAM, macOS 26.5. Foundry Local 0.8.119,
`foundry-local-sdk` 1.2.4, Python venv.

## Mimari (v1 — motor)

```
PDF yükleme  ──> pdf_loader (sayfa bazlı metin, OCR yedek yolu)
             ──> chunking (130 kelime pencere + 30 overlap, sayfa sınırı korunur)
             ──> embedding (qwen3-embedding-0.6b, 1024 boyut)
             ──> store (SQLite, float32 BLOB, L2-normalize matris önbelleği)

Soru ──> retrieve (cosine benzerlik + eşik)
     ──> answer (system prompt + qwen2.5-7b)
     ──> cevap + [Kaynak: dosya.pdf s.4]
```

Modül haritası: `rag/config.py` (tüm sabitler ve gerekçeleri), `rag/models.py`
(Foundry Local istemcisi), `rag/pdf_loader.py`, `rag/chunking.py`,
`rag/store.py`, `rag/ingest.py`, `rag/retrieve.py`, `rag/answer.py`,
`rag/ocr.py`. Arayüzler: `cli.py`, `streamlit_app.py`. Değerlendirme:
`eval/eval_set.json`, `eval/run_eval.py`.

## Model seçimi ve gerekçesi

- **Embedding:** `qwen3-embedding-0.6b` (id `qwen3-embedding-0.6b-generic-gpu:1`,
  vektör boyutu 1024, context 32768).
- **Chat:** `qwen2.5-7b` (id `qwen2.5-7b-instruct-generic-gpu:4`, 5.2 GB).

`phi-4-mini` (3.7 GB) denendi ve **grounded (bağlam verilmiş) testte elendi**:
bağlamın ilk cümlesinde açıkça duran "Retrieval-Augmented Generation"
açılımını bulamayıp "belgelerde yok" dedi, "Recurrent Attention Generation"
diye uydurma bir açılım üretti ve 118 kelimelik anlamsız bir tekrar döngüsüne
girdi. Aynı koşulda `qwen2.5-7b` bağlama sadık kaldı ve tekrar döngüsüne
girmedi.

## Kritik teknik bulgu: sampling parametreleri işlemiyor

`ChatClientSettings` içindeki `temperature`, `top_p`, `frequency_penalty`,
`presence_penalty`, `random_seed` alanları SDK tarafından istek gövdesine
konuyor (`_serialize()` çıktısında görünüyorlar) ama Foundry Local runtime'ı
bunları **yok sayıyor**. Ölçüm: `temperature=0.0` ile `temperature=1.5`
birebir aynı çıktıyı, farklı `random_seed` değerleri birebir aynı çıktıyı
üretti. Pratikte yalnızca `max_tokens` etkili. Sonuç: üretim kalitesi
sampling ile değil, yalnızca **prompt ve model seçimiyle** kontrol
edilebiliyor. (Bkz. `rag/config.py` içindeki `TEMPERATURE`/`TOP_P` yorumları.)

## Retrieval eşiği (MIN_SCORE) — kalibrasyon hikâyesi

Kalibrasyon: cevabı olan sorular 0.65–0.84 aralığında, olmayanlar 0.43–0.74
aralığında skor alıyor. **Gruplar örtüşüyor** — tek bir eşik ikisini kesin
ayıramaz, çünkü anlamsal benzerlik cevabın var olduğu anlamına gelmiyor
("Foundry Local'da fine-tuning nasıl yapılır?" sorusu 0.74 alıyor çünkü konu
aynı, ama cevap belgede yok).

Bu yüzden savunma iki katmanlı: (1) eşik konu dışı soruyu LLM'e hiç
göndermeden eler, (2) "konu yakın ama cevap yok" kararını system prompt ile
LLM verir.

Eşik ilk olarak 0.55 seçildi (eval setine bakarak). Sonra set **dışından**
sorulan "Pencere boyu ve örtüşme kaç kelimedir?" sorusu — cevabı
`belge_06_chunking_stratejisi.md`'de açıkça yazan bir soru — 0.49 alıp
reddedildi. Eşik, eval setinin ifade biçimlerine aşırı uydurulmuştu; 10
örnek gerçek skor tabanını temsil etmiyordu. **0.45'e indirildi**, eval
sonucu değişmedi (hâlâ 15/15).

## Chunking

PDF için 130 kelime pencere + 30 kelime overlap; chunk'lar **sayfa sınırını
aşmaz** (kaynak atıfında "s.4" diyebilmek için). `data/*.md` test
belgeleri için ayrı ve daha küçük pencere (60 kelime) kullanılıyor — belgeler
~130 kelime olduğundan büyük pencereyle her belge tek chunk'a düşüyor ve
top-k=4 korpusun yarısını döndürüyordu (7 chunk → 60 kelimelik pencereyle
17 chunk).

## Depolama

SQLite, embedding'ler **float32 BLOB** olarak saklanıyor (JSON değil — 1024
boyutlu vektör JSON'da ~20 KB, BLOB'da 4 KB). Matris L2-normalize edilmiş
tutuluyor, böylece cosine benzerlik tek bir `matrix @ query_vector`
çarpımına iniyor. `PRAGMA foreign_keys = ON` zorunlu (SQLite'ta varsayılan
kapalı, yoksa `ON DELETE CASCADE` sessizce çalışmaz).

## OCR (taranmış sayfa yedek yolu)

macOS Vision (`pyobjc-framework-Vision`) kullanılıyor. `tr-TR` desteği
**çalışma anında doğrulandı**, varsayılmadı (30 dil destekleniyor).
Foundry Local katalogundaki görüntü alabilen modeller (`qwen3-vl-*`)
yalnızca CPU varyantına sahip ve — daha önemlisi — bir görüntü-dil modeli
metni okumaz, **üretir**; okuyamadığı kelimeyi makul görünen başkasıyla
doldurabilir. RAG korpusunda bu, alıntı yapılan cümlede sessizce sadakat
kaybına yol açar. Görüntüler `pypdf`'in `page.images`'ı ile alınıyor (ek
bağımlılık yok). OCR'dan gelen chunk'lar `via_ocr=True` ile işaretleniyor.
Uçtan uca test edildi: sentetik taranmış bir PDF üretilip OCR'sız
atlandığı, OCR'lı okunduğu doğrulandı.

## Değerlendirme sonuçları

23 soruluk set (10 cevaplanabilir + 3 cevaplanamaz "yakın tuzak" + 2 kenar
durum + 3 meta/özetleme + 2 korpus + 3 diller arası — son üç kategori
"Sorgu yönlendirme" bölümündeki sağlamlaştırma turunda eklendi):
**23/23 geçiyor**. Retrieval **10/10** doğru kaynak belgeyi buluyor.
Eşik kısa devresinde (konu dışı soru, LLM hiç çağrılmıyor) 0.1 sn.

Streaming ölçümü (v2 backend üzerinden, gerçek RAG koşulunda, HTTP ile):
`retrieval` olayı **0.04–0.07 sn**, ilk token **4.8–5.9 sn**, toplam
5.6–7.6 sn.

Erken bir ölçümde TTFT 0.74 sn çıkmıştı ve bu rakam bir süre dokümanlarda
kaldı; **yanıltıcıydı**, çünkü bağlamsız kısa bir prompt'la alınmıştı.
Gerçek RAG'de system prompt 4 chunk'lık bağlam taşıyor ve prefill baskın
hale geliyor. Sonuç: streaming'in kazancı sanıldığından küçük (~1.3 sn erken
görüntü); asıl kazanç Inspector'ın 0.05 sn'de dolması — kullanıcı LLM'i
beklerken hangi kaynakların bulunduğunu anında görüyor.

Akışta ara sıra boş `chunk.choices` geldiği doğrulandı; tüketen kod bunu
kontrol etmeden erişirse `IndexError` verir.

**Bilinen sınır:** eval'deki `expected_keywords` metriği bazen gevşek
raporluyor (tam metin doğruyken anahtar kelime tam eşleşmediği için "eksik"
görünebiliyor). Metrik kasıtlı olarak gevşetilmedi. Ayrıca `qwen2.5-7b`'nin
Türkçe dilbilgisi kusursuz değil, ara sıra bozuk çekim üretebiliyor.

## Arayüzler (v1)

- `streamlit_app.py` — PDF yükleme, sohbet, Retrieval Inspector (expander
  içinde). Çalışıyor, `st.testing.v1.AppTest` ile doğrulandı.
- `cli.py` — REPL, `--show-chunks` ile getirilen bağlamı gösterir.

## v2 Dönüşümü — SaaS ürünü

Hedef: motoru değiştirmeden, arayüzü Linear/Notion AI seviyesinde bir ürüne
dönüştürmek.

**Faz 1 (Mimari denetim) — kapandı.** Karar: **FastAPI backend + Next.js
(statik export) frontend**. Next.js build'i (`output: 'export'`) FastAPI
tarafından servis edilir; çalışma anında tek süreç, sıfır ağ — offline
garantisi korunur. `rag/` paketine dokunulmuyor; tek eklenecek şey
`rag/answer.py`'ye bir streaming varyantı.

**Faz 2 (Design System) — kapandı.** Renk paleti Indigo/Purple + retrieval
güven skoru için semantik renk katmanı (≥0.70 güçlü, 0.55–0.70 orta,
0.45–0.55 zayıf, <0.45 elendi). Tipografi Inter + JetBrains Mono (yerel
paketlenmiş, CDN yok). Bileşen kütüphanesi shadcn/ui. Üç kolonlu masaüstü
düzeni: Sidebar (260px) · Chat (esnek) · Retrieval Inspector (380px,
kalıcı). Kontrast oranları ölçülüp doğrulandı — bkz. `docs/DESIGN_SYSTEM.md`
§8.

**Faz 3 (Core Features & Explainability spec) — kapandı.** Beş user flow,
endpoint istek/yanıt şemaları, SSE olay tipleri ve hata kodları dondurulmuş
— bkz. `docs/FEATURE_SPEC.md` §8.

**Faz 4 (kodlama) — tamamlandı.** Sırasıyla: v2 iskeleti (4.1: Next.js +
shadcn/ui + FastAPI bağımlılığı) → backend (FastAPI, 29/29 test) +
design-system frontend, token katmanı/tema/i18n (Dalga 1) → streaming
`answer_query_stream()` eklendi (4.7.1, mevcut `answer_query` dokunulmadı)
→ eval sonuçları kalıcılaştırıldı, model kıyası ölçümle kanıtlandı (M1–M4:
`qwen2.5-7b` 15/15, `phi-4-mini` 12/15) → AppShell + sidebar + sohbet/
Inspector + Metrics sayfası, üç paralel agent (Dalga 2) → entegrasyon
(4.7): provider zinciri, sayfa bağlantıları, `/metrics` 404 düzeltmesi,
eşzamanlılık iki paralel istekle doğrulandı, geçici `dev-*` önizleme
rotaları kaldırıldı. Regresyon: eval 15/15, backend 29/29.

## Faz 4 sonrası sağlamlaştırma turu

Üretimde ölçülen gerçek bir hatayla başladı: "İlgili dökümanı bana özetle"
sorgusu 0.28–0.30 skor alıp eşiğin (0.45) altında kaldı, sistem "bilgi
belgelerde yok" dedi — oysa belge yüklüydü. Kök neden: meta sorgu hiçbir
içerik terimi taşımıyor, dense retrieval'ın yapısal olarak karşılayamadığı
bir sorgu sınıfı. Altı görev, öncelik sırasıyla:

**1. Sorgu yönlendirme** (`rag/query_router.py`, yeni). Retrieval'dan ÖNCE
kural tabanlı sınıflandırma (LLM çağrısı yok — gecikme eklemez, offline
kalır): `search` (mevcut yol, davranış değişmedi) / `summarize` (chunk'lar
benzerlikle değil doğrudan belge kimliğinden gelir — `rag/answer.py`'de
ayrı `SUMMARY_PROMPT`, `rag/store.py::get_document_chunks` eşit aralıklı
örnekler) / `corpus` (LLM hiç çağrılmaz, cevap `store.list_documents`'tan —
`rag/answer.py::_corpus_answer`). Birden fazla belge yüklüyken hedef
belirsizse TAHMİN ETMEZ, kullanıcıya sorar. **Eşik DÜŞÜRÜLMEDİ** — hâlâ
0.45; çözüm sorgu sınıfını retrieval'a hiç göndermemek.

**2. Eval seti genişletildi** (15 → 23 soru): 3 meta, 2 corpus, 3 diller
arası (yeni İngilizce fixture `data/belge_07_ann_search_en.md` — ANN/HNSW
konusu, projeye özgü ayrıntı içeriyor). `web/lib/types.ts` ve
`components/metrics/categories.ts`'deki kategori birleşimi buna göre
genişletildi (additive, Metrics UI zaten bilinmeyen kategorileri
zarifçe gösteriyordu).

**3. Hibrit retrieval** (BM25 + dense, `rag/store.py::bm25_candidates` +
SQLite FTS5, `rag/retrieve.py`'de Reciprocal Rank Fusion). **DİKKAT:**
yalnızca aday HAVUZUNU genişletir; `Hit.score` HER ZAMAN ham cosine'dır —
MIN_SCORE/Inspector/DESIGN_SYSTEM §1.2 sözleşmesi bozulmuyor. ÖLÇÜLDÜ: 23
soruluk sette hibrit KAPALI 23/23, AÇIK 22/23 (bir soru iki gerçek konunun
kesiştiği kasıtlı belirsiz bir örnekte düşüyor — bkz. `rag/config.py`
yorumu). Bu ölçekte (20–40 chunk) getirisi maliyetini karşılamıyor;
**varsayılan KAPALI** (`config.HYBRID_RETRIEVAL_ENABLED = False`), özellik
tam çalışır ve test edilmiş durumda, korpus büyüdükçe açılabilir.

**4. Reddetme tespiti sağlamlaştırıldı** (`rag/answer.py::is_refusal`).
Eski birebir alt dize eşleşmesi KIRILGANDI (ölçüldü: phi-4-mini Q13,
"yüklediğiniz" → "yüklendiğiniz" tek harf farkı tespiti kaçırdı). Artık
`difflib.SequenceMatcher` ile bulanık eşleşme (kalibre edilmiş eşik: 0.85).
`eval/run_eval.py` artık AYNI fonksiyona delege ediyor — eval ve production
farklı reddetme tanımı kullanmıyor.

**5. UX kurtarma yolu** (`web/components/chat/message-list.tsx`).
`below_threshold` artık ölü bir duvar değil: 1. maddedeki özetleme yoluna
giden sabit bir soruyu ("Yüklü belgeyi özetle") aynı sohbet akışından
gönderen bir buton. Uçtan uca curl ile doğrulandı — orijinal ekran
görüntüsündeki senaryo artık gerçek, doğru kaynaklı bir özet üretiyor.

**6. Offline kanıtı** (`eval/offline_proof.py`, yeni). Wi-Fi fiziksel
olarak kapatılmadı (bu makinenin ağ durumunu değiştirmek script'in yetki
alanı dışında bir yan etki); bunun yerine `socket.socket.connect` tüm eval
koşumu boyunca sarılıp her bağlantı denemesi kaydedildi — "ağ kapalıyken
çalıştı" gözleminden daha güçlü bir iddia: **açık bir ağ varken bile
dışarıya hiç istek denenmedi**. BEKLENMEYEN BULGU: 0 socket çağrısı —
Foundry Local Python SDK'sı (`foundry_local_sdk/detail/core_interop.py`)
model çağrılarını `ctypes` ile yerel bir ikiliye (`foundry_local_core`)
doğrudan FFI çağrısı olarak gönderiyor, network stack'ine (loopback dahil)
hiç girmiyor. Kayıt: `eval/OFFLINE_PROOF.md` (23/23, otomatik üretilir).

Regresyon: backend 91/91 test, frontend build/lint temiz, eval 23/23.

## Studio Katmanı — Faz 1

`docs/STUDIO_PLAN.md`'de tasarlanan üç modüllü artefakt hattının (Mind Map /
Rapor / Quiz) ortak temeli kuruldu — spec `docs/FEATURE_SPEC.md` §9. Üç
implementer paralel çalıştı: `rag/`'a `topics.py` (saf numpy agglomerative
kümeleme) ve `artifacts/{__init__,base,fidelity,store}.py`, `store.py`'ye 3
tablo (`artifacts`, `artifact_claims`, `quiz_attempts`) + `corpus_fingerprint()`,
`config.py`'ye 6 sabit; `backend/`'e `routes/artifacts.py` (4 endpoint) ve
`schemas.py`'ye 4 şema; `web/`'e `components/studio/{studio-panel,
right-panel-tabs}.tsx`, `lib/i18n/studio.ts`, 4 yeni hata kodu ve artefakt
tipleri. Yeni kod ~1730 satır. Motor yolu — `answer.py`, `retrieve.py`,
`models.py`, `query_router.py`, `chunking.py`, `ingest.py` — **byte-identical
değişmedi**, doğrulandı.

**Kapı sayıları (Faz 1 sonrası):** eval **23/23** (212 sn, ortalama 9.2
sn/soru) · backend **123 passed** (93 taban + Faz 1'in 30 yeni testi) ·
offline kanıtı **23/23, 0 soket** · `web` build + lint temiz (5/5 statik
sayfa).

**Başarı kriteri 1 — kümeleme.** 7 belgelik / 20 chunk'lık korpusta
(`data/*.md`, atılık bir kopya üzerinde ölçüldü — üretim `rag.db`'sine
dokunulmadı) `cluster_corpus()` **7 küme** üretti ve her küme **tam olarak
bir kaynak belgeye** karşılık geldi, belgeler arası karışma yok
(belge_01/03/04/05/06/07 → 3'er chunk, belge_02 → 2 chunk). Etkin tavan
`min(TOPIC_MAX_CLUSTERS=12, N//TOPIC_MIN_CLUSTER_SIZE=10)=10`; emilim adımı
bunu 7'ye indirdi. İki ardışık çağrı birebir aynı sonucu verdi
(determinizm).

**Başarı kriteri 2 — sadakat kapısı.** `FIDELITY_MIN_SCORE=0.45`:
korpustan birebir alınmış bir cümle `grounded` işaretlendi, ham cosine
**0.9240**; bilinçli bozuk bir iddia ("İstanbul'un nüfusu 16 milyondur…")
`unsupported` işaretlendi, ham cosine **0.3293**.

**Bilinen sınır (yeni, gizlenmiyor).** Üçüncü bir iddia denendi: "Bu sistem
varsayılan olarak GPT-4 kullanır ve verileri OpenAI sunucularına gönderir."
— bu ürün için **yanlış** bir iddia (ürün tamamen offline) ama konuya yakın
metinle örtüştüğü için **0.5487** aldı ve `grounded` işaretlendi. Kapı
*grounding* ölçüyor, *entailment* değil: ham cosine "bu konuda chunk var mı"
sorusunu cevaplar, "bu chunk bu iddiayı destekliyor mu" sorusunu değil. Bu,
`MIN_SCORE` kalibrasyonundaki örtüşme probleminin (yukarıda, "Retrieval
eşiği" bölümü) birebir aynısı. **Eşik değiştirilmedi**: 0.5487'yi elemek için
`FIDELITY_MIN_SCORE`'u 0.55'e çekmek, `MIN_SCORE`'un 0.55→0.45 indirilme
gerekçesini (gerçek bir sorunun 0.494 alıp reddedilmesi) tersine çevirir ve
`FIDELITY_MIN_SCORE == MIN_SCORE` kararını bozardı. Telafi Faz 2'ye
bırakıldı ve Faz 2'nin kapanma koşuluna yazıldı (eval'e trap girişi + bu
iddianın rapordan çıkarılması).

**Reddedilen alternatifler.**
- `scipy`/`scikit-learn` ile kümeleme → **reddedildi**: ikisi de kurulu
  değil; 20–40 chunk ölçeğinde naive agglomerative saf numpy ile birkaç
  düzine satır. İki büyük paketi offline garantinin içine sokmanın gerekçesi
  yok.
- `d3-hierarchy`'yi Faz 1'de kurmak → **reddedildi**: Faz 1'de çizilecek
  düğüm yok, saf spekülasyon. Faz 3'e bırakıldı; `package.json` Faz 1'de
  dondurulmuş kaldı.
- `web/components/ui/tabs.tsx` primitifi → **reddedildi**: iki sekme için
  tek kullanımlık soyutlama. Mevcut `Button` ile elle segment kontrolü
  (`role="tablist"`, ok tuşu gezinmesi).
- `studio-panel`'e "Üret" düğmesi → **reddedildi**: arkasında çalışan
  üretici yokken basılamayan düğme, "sahte sayı göstermeme" ilkesinin aynı
  ihlali.
- `fidelity_score`'u ortalama cosine olarak yorumlamak → **reddedildi ve
  ölçümle çürütüldü**: `STUDIO_PLAN.md`'deki `0.91` örneği ve Faz 2'nin
  `≥0.90` kriteri, ortalama cosine olarak bu korpusta **imkânsız** (skorlar
  0.84 tavanında kalıyor). `fidelity_score` bunun yerine **oran** olarak
  tanımlandı (grounded / toplam iddia); `DESIGN_SYSTEM.md §1.2`'nin güven
  bantlarıyla renklendirilmesi açıkça yasaklandı — o bantlar ham cosine için
  kalibre edildi, bir oran için değil.
- Sadakat eşiğini yükselterek yanlış-ama-yakın iddiayı elemek →
  **reddedildi** (yukarıda, "Bilinen sınır").

**Doküman kayması düzeltildi.** `AGENTS.md §3` ve `docs/STUDIO_PLAN.md §10`
"backend 91/91" diyordu; Faz 1 öncesi ölçülen gerçek taban **93**'tü (aradaki
2 test, sağlamlaştırma turunda eklenmiş ama hızlı komut listelerine
yansımamıştı). `docs/STUDIO_PLAN.md §10` **93/93**'e düzeltildi.

## Studio Katmanı — Faz 2 (Rapor Üreteci)

Faz 1 hattı kurdu; Faz 2 hattan geçen **ilk gerçek artefaktı** üretti ve
böylece hattı doğruladı — spec `docs/FEATURE_SPEC.md` §10.

`rag/artifacts/report.py` (üretici): bölüm planı SABİT, LLM seçmez —
Yönetici Özeti (en son üretilir, diziye index 0 yazılır) + Temel Bulgular +
küme başına Detaylı Analiz + deterministik Tablolar/Kaynaklar. Bölüm bağlamı
sorgudan değil KÜMEDEN gelir (`retrieve.get_top_chunks` çağrılmaz);
`SUMMARY_MAX_CHUNKS` üst sınırı aşıldığında eşit aralıklı örneklenir, yeni
sabit eklenmedi. `rag/models.py::get_chat_client` artık `(alias, max_tokens)`
ile önbelleklenir — `ARTIFACT_SECTION_MAX_TOKENS=700` Faz 1'de config'te
yazılıydı ama **ulaşılamazdı** (SDK çağrı başına ayar almıyor, ayar client'a
gömülüyor); mevcut çağıranların davranışı birebir korundu.
`backend/` ince kaldı: `GET /api/artifacts/{id}/export?format=md` (markdown'ı
`report.to_markdown` üretir, rota yalnızca başlık kurar) + `dropped_count`
türetmesi (SSE `complete` ve `ArtifactDetail`, additive).
`web/components/studio/report/` rapor görünümü: her cümle kaynak numarasıyla,
tablolar, kaynaklar, ayrı "çıkarılan iddialar" paneli, markdown indirme ve
`@media print` ile tarayıcının kendi PDF'i. Yeni npm/pip bağımlılığı yok.

**Kapı sayıları:** eval **23/23** (237 sn, 10.3 sn/soru) · backend
**151 passed** (Faz 1 tabanı 123 + Faz 2'nin 28 yeni testi) · offline kanıtı
**23/23, 0 soket** · `eval/fidelity_trap.py` **PASS (0.5487 / grounded)** ·
`web` build + lint temiz (5/5 statik sayfa).

**Kapanma ölçümü (§10.13, `eval/report_trap.py`).** Tuzak cümlesi bir bölümün
LLM çıktısına **bilerek enjekte edildi** (organik hallüsinasyon değil; koşum
bunu açıkça yazar), hattın geri kalanı gerçekten çalıştı. eval.db üzerinde,
7 küme / 9 LLM çağrısı: **48 iddia, 44'ü rapora girdi, 4'ü düşürüldü**
(hepsi `unverified_terms`). Tuzak `artifact_claims`'te **0.5487 / grounded**
(pin birebir aynı) ama `node_path` `/dropped/1` — yani `sections` altında
DEĞİL; rapor gövdesinde "gpt"/"openai" **0 eşleşme**; `fidelity_score`
**1.0000** (oran). Faz 2'nin iddiası "kapı artık entailment ölçüyor" değil,
"ürün artık entailment'ı geçemeyen cümleyi **yayımlamıyor**".

### Faz 2'nin ölçümle çürüttüğü kendi kalibrasyonu

İlk kapanma koşumu PASS verdi ama sayılar ürünün kullanılamaz olduğunu
gösterdi: **47 cümlenin 42'si düşüyordu.** Kök neden ikinci katmanın
(`fidelity.unverified_terms`) ilk hâlindeydi: bir terim yalnızca doküman
frekansına göre "ayırt edici" sayılıyordu ve 20 chunk'lık bir korpusta
sıradan Türkçe çekim de (`dayanır`, `olanak`, `yanıt`, `indirilmesi`) df=0
alıyor — df sinyali hallüsinasyonu normal sözcükten **ayıramıyor**.

Kalibrasyonun kendisi yanıltıcıydı: `rag/config.py`'deki (b) ölçümü
korpustan **birebir alınmış** 399 cümleyle yapılmış ve "0/399 toplu düşme"
demişti. Birebir cümle kendi bağlamında her zaman alt dize olarak bulunur;
LLM nesri ise aynı bilgiyi **başka sözcüklerle** yazar. Ölçüm gerçek üretilmiş
nesri temsil etmiyordu ve bu, config yorumuna açıkça yazıldı.

Düzeltme eşik oynatarak değil, kurala **ikinci bir şart** ekleyerek yapıldı
(§10.6 kural 4b): terim ayrıca **varlık benzeri** olmalı — rakam içermeli
(`gpt-4`, `200-400`), içinde `-`/`.` bulunmalı (model kimlikleri) ya da
**cümle başı olmayan** bir konumda büyük harf taşımalı (`OpenAI`, `SQLite`).
Sözlük ya da durak-kelime listesi yok; işaret metnin kendi yazımından türüyor
ve §10.6'nın kendi gerekçesine ("cosine özel adları/model kimliklerini
kaçırır") sadık kalıyor.

| Kural | Rapora giren | Düşen | Tuzağın terimleri |
|---|---|---|---|
| yalnız df | **5**/47 | 42 | `varsayılan, gpt-4, kullanır, verileri, openaı, sunucularına, gönderir` |
| df + varlık | **43**/47 | 4 | `gpt-4, openaı` |

Varlık şartıyla düşen 4 cümlenin 3'ü tuzak dışı ve hepsi **doğru** düşüş: iki
bozuk `YAZMA:` başlığı ve modelin **uydurduğu bir sayı** (`200-400 kelime`;
korpus 130+30 diyor). Yani katman, cosine'ın `grounded` saydığı gerçek bir
hallüsinasyonu da yakaladı.

`FIDELITY_MIN_SCORE` **değişmedi**, `bind_claims`/`verdict_for`/
`fidelity_score` **değişmedi** — 4b `bind_claims`'in dışında, ondan sonra
çalışıyor, bu yüzden `fidelity_trap.py`'nin pini aynen duruyor.

**Reddedilen alternatifler (aynı koşum üzerinde ölçüldü).**
- `FIDELITY_TERM_MIN_LENGTH`'i yükseltmek → **reddedildi**: Türkçe çekimli
  sözcükler (`eşleşmelerine`, 13 harf) tuzaktan (`gpt-4`, 5 harf) daha uzun;
  uzunluk iki sınıfı ayırmıyor.
- `FIDELITY_TERM_DF_MAX_RATIO`'yu değiştirmek → **reddedildi**: her iki sınıf
  da df=0; oran hangi yöne çekilirse çekilsin ayrım üretmiyor.
- Kök/önek eşleşmesi (ilk K harf alt dize) → **ölçüldü ve reddedildi**:
  K=7/6'da 5/47, K=5/4'te 7/47 — 42 düşüşün yalnızca ikisini kurtarıyor,
  çünkü düşen sözcükler korpusta hiçbir biçimde yok.
- "En az N doğrulanamayan terim" şartı → **reddedildi**: tuzakta 7 terim var,
  gerçek cümlelerde de 7/12/14/17/20; sayı ayrım üretmiyor.
- Varlık işaretine **rakamsız tire/nokta** kolu → **eklendi, sonra ölçümle
  kaldırıldı**: ilk hâlinde "içinde `-`/`.` olan token model kimliğidir"
  deniyordu. Üretim korpusundaki uçtan uca koşumda 13 düşüşün 4'ü yalnız bu
  koldan geldi ve **hepsi yanlış pozitifti** (`soru-cevap` — Türkçe birleşik
  sözcük). Kol hiçbir gerçek yakalama üretmedi; bu alandaki model kimlikleri
  (`gpt-4`, `qwen2.5-7b`, `phi-4-mini`) zaten rakam taşıyor. Kaldırıldıktan
  sonra aynı korpusta rapora giren cümle 59 → **63**, düşen 13 → **9** oldu;
  tuzak yine `['gpt-4', 'openaı']` ile düştü.
- Tuzağı `eval_set.json`'a eklemek → **reddedildi** (§10.1.1): "23/23"ün ne
  ölçtüğünü sessizce genişletirdi. Eval seti **23 soruda kaldı**.
- `format=html` export → **reddedildi**: yazdırma CSS'i PDF ihtiyacını zaten
  karşılıyor; ikinci bir HTML render yolu rapor yerleşimi için ikinci bir
  doğruluk kaynağı olurdu.
- Önbellekli chat client'ın `settings`'ini geçici değiştirmek →
  **reddedildi**: paylaşılan global durum; geri alma kaçarsa (istisna, iptal
  edilen SSE akışı) sohbet cevapları sessizce 700 token tavanıyla çalışır ve
  bunu hiçbir test yakalamaz.

### Uçtan uca doğrulama (gerçek backend + gerçek model)

Kapılar ve kapanma ölçümü kütüphane seviyesinde koşuyor; ürünün HTTP yüzeyi
ayrıca **çalışan bir backend üzerinde** doğrulandı. Üretim `rag.db`'sine
dokunulmadı: bir **kopya** üzerinde `RAG_BACKEND_DB_PATH` ile ayrı bir uvicorn
açıldı (8 belge / 61 chunk / 10 küme / 12 LLM çağrısı, 267 sn).

30 kontrolün tamamı geçti; öne çıkanlar: `stage` sırası
`selection → clustering → generation → fidelity` · **12 `progress` olayı**,
`pct` 8'den 100'e **tam sayı** · `complete` hem `unsupported_count` hem
`dropped_count` taşıyor · **63 cümlenin 63'ünün** `artifact_claims` satırı ve
bağlı chunk'ı var · `score` ham cosine aralığında (min 0.4559, max 0.8968) ·
`fidelity_score` **0.9306** (üretim korpusunda da ≥0.90) · export `200` +
`text/markdown; charset=utf-8` + `attachment` başlığı, **8433 karakter**,
içinde **hiç `http(s)://` yok**, düşürülen 9 iddianın metni gövdede yok ama
sayısı dipnotta · `format=html|pdf|` üçü de **422** · bilinmeyen id **404
ARTIFACT_NOT_FOUND** · statik export aynı süreçten servis ediliyor, HTML'de
harici host referansı yok, bundle yeni bileşenleri (`Rapor üret`,
`Rapordan çıkarılan iddialar`, `Markdown indir`, `data-print`) taşıyor.

### Arayüz kanıtı (gerçek tarayıcı) — `eval/ui_proof.py`

HTTP yüzeyi doğrulandıktan sonra geriye tek katman kalmıştı: React
etkileşimi. Playwright + Chromium ile ölçüldü (**28/28 kontrol**): sekme
gezinmesi ok tuşlarıyla çalışıyor (WCAG AA, §9.9.3), artefakt listesi ve
sadakat oranı görünüyor, rapor açılıyor, **63 cümlenin 63'ü** `data-node-path`
ve atıf üst simgesi taşıyor, düşürülen **9 iddia** ayrı panelde sebebi ve ham
cosine skoruyla duruyor, metinleri gövdeye sızmıyor, export bağlantısı aynı
origin'de doğru endpoint'e gidiyor, `@media print` kabuğu gizleyip raporu tam
boy bırakıyor, karanlık temada yazdırma açık palete düşüyor, üretim akışında
ilerleme çubuğu 0–100 tam sayı gösteriyor ve bitince rapor otomatik açılıyor.
**Sıfır konsol hatası, sıfır harici ağ isteği.**

İki şey kasıtlı olarak sahtelendi ve script çıktısında açıkça yazılıyor:
warmup atlanır (`model_status` elle "ready") ve `report` üreticisi LLM
çağırmayan bir sahteyle değiştirilir — doğrulanan şey ÜRETİM değil (o zaten
gerçek modelle ölçüldü), tarayıcıdaki davranış. Veritabanı yine `rag.db`
kopyasıdır.

`playwright` **`requirements.txt`'e girmedi**: ürün yolunda hiç import
edilmiyor, yalnızca bu doğrulama script'i kullanıyor. Ayrı bir
`requirements-dev.txt` açıldı; `eval/offline_proof.py`'nin 0-soket iddiası bu
ayrım sayesinde bozulmuyor.

**Görülen kozmetik kusur (düzeltilmedi, kayda geçti).** Model, prompt'un
yasaklamasına rağmen ara sıra markdown vurgusu üretiyor (`**Yazım**`,
`**Bir-Ay Proje Planı**`) ve rapor görünümü cümleleri düz metin bastığı için
yıldızlar ekranda görünüyor. Bunların çoğu zaten `weak` bağ ile düşüyor ama
hepsi değil. Çözüm `_strip_citations`'ın yanına bir vurgu temizleyicisi
eklemek olurdu; üretici çıktısını değiştirdiği için kapanma ölçümünün
yeniden koşulmasını gerektirir, o yüzden ayrı bir karara bırakıldı.

**Bilinen sınır (Faz 2 sonrası).** Varlık şartı, korpusta hiç geçmeyen ama
özel ad gibi yazılmamış **yanlış bir sayısal olmayan iddiayı** hâlâ
yakalamaz — sözcüksel katman entailment ölçmüyor, yalnızca ikinci ve bağımsız
bir sinyal veriyor. Kapının bilinen entailment boşluğu (yukarıdaki Faz 1
bölümü) kapanmadı; kapatılmadığı için de gizlenmedi. İkinci bir sınır:
modelin ara sıra ürettiği **başlık satırları** (`**Yerel Veri Saklama ve
Embedding Kullanımı**`) Title Case olduğu için varlık şartına takılıp
düşürülüyor — prompt zaten başlık yazmayı yasaklıyor, yani düşmeleri yanlış
değil, ama sebep olarak `unverified_terms` görünüyor.

## Studio Katmanı — Faz 3 (Zihin Haritası)

Faz 2 hattan ilk artefaktı geçirdi; Faz 3 **ikinci tipi** geçirerek hattın
gerçekten tip-bağımsız olduğunu gösterdi — spec `docs/FEATURE_SPEC.md §11`.
`base.generate_artifact` **değişmedi**, yalnızca yeni bir üretici kaydedildi.

`rag/artifacts/mindmap.py`: yapı embedding kümelemesinden DETERMİNİSTİK çıkar,
LLM yalnızca kümelere isim verir. Gerekçe Faz 2'nin sadakat mantığının aynısı:
LLM'e "korpusu haritala" demek düğümlerin belgede olup olmadığını doğrulanamaz
kılar; küme yaklaşımında her düğüm ZATEN bir chunk kümesidir — hallüsinasyon
yapısal olarak imkânsız, yalnızca etiket yanlış olabilir. Bu ölçülebilir bir
iddiadır ve testle kilitlendi: etiketler tamamen değişse bile düğüm kimlikleri,
chunk üyelikleri ve kenarlar **birebir aynı** kalıyor.

`topics.topic_title` eklendi: kümenin deterministik adı (baskın belge + katkı
sayısı). Raporun "Detaylı Analiz" başlığı buraya **delege edildi** (davranış
birebir korundu) — harita yedek etiketi ile rapor başlığının aynı adı üretmesi
zorunlu, iki kopya iki doğruluk kaynağı olurdu.

**Faz 3'ün rapordan ayrıldığı nokta.** Raporda bağlanamayan cümle çıkarılır;
haritada bağlanamayan etiketin DÜĞÜMÜ çıkarılamaz — düğüm korpusun gerçek bir
parçasıdır, silmek `rag/topics.py`'nin "artık kümeyi atma, emil" kuralının
(korpusu sessizce yok etmeme) aynı ihlali olurdu. Bunun yerine etiket
`topic_title`'a düşer, `label_source="fallback"` yazılır ve arayüz bunu
GÖSTERİR; modelin önerisi `payload["dropped"]`'a sebebi ve ham cosine skoruyla
gider. Yedek etiket **iddia sayılmaz**: korpustan deterministik türüyor, sadakat
oranına katmak ölçülmemişi ölçülmüş göstermek olurdu.

**Kenar eşiği `MIN_SCORE`'a EŞİTLENMEDİ** ve gerekçesi ölçüldü (model yüklemez,
yalnızca kayıtlı embedding'ler): küme merkezleri arası cosine medyanı eval.db'de
0.4366, rag.db'de 0.4707 — yani 0.45 uygulanırsa çiftlerin yarısı kenar olur ve
kenarın taşıdığı bilgi sıfırlanır. 0.50'de rag.db'de 10 düğüme 20 kenar düşüyor
(ortalama derece 4.0, hairball); 0.65'te küçük korpus tamamen kenarsız kalıyor.
**0.55** iki korpusta da okunabilir: 2 kenar (eval.db) / 11 kenar (rag.db).
Kenar yokluğu HATA DEĞİLDİR — kümeler uzaksa harita yıldız çizilir.

### Faz 3'ün ölçümle çürüttüğü iki şey

**1. Model, biçim kuralını yok sayabiliyor.** İlk kapanma koşumunda 7 etiketin
3'ü sadakat kapısından düştü ve ÜÇÜ DE YANLIŞ POZİTİFTİ: "Retrieval-Augmented
Generation Anlatımı" (0.7430), "Yakın Komşu Arama Teknikleri" (0.5167),
"Embedding ve Benzerlik Analizi" (0.8027). Kök neden kapıda değil YAZIMDAYDI:
model başlıkları Başlık Düzeninde yazıyor, `fidelity._entity_like` ise "cümle
başı olmayan büyük harf"i özel ad kanıtı sayıyor — Başlık Düzeninde bu işaret
hiçbir bilgi taşımaz, çünkü HER sözcük büyük.

Önce prompt'a "CÜMLE DÜZENİ kullan, Her Kelimeyi Büyük Harfle Başlatma" maddesi
eklendi ve aynı korpusta yeniden koşuldu. **Model kuralı yok saydı**; üstelik
bir etiketi "Embedding ve Benzerlik Analizi"nden "Embedding **Ve** Benzerlik
Analizi"ne çevirerek daha da Başlık Düzenine soktu. Düşen etiket 3/7'de kaldı.
Madde geri alındı — işlemeyen bir kuralı prompt'ta tutmak çalıştığını ima eder.
Bu, projenin "üretim kalitesi yalnızca prompt ve model seçimiyle kontrol
edilir" varsayımının ÖLÇÜLMÜŞ SINIRIDIR: prompt bazen yetmiyor.

**2. Çözüm kapıyı gevşetmek değil, çağıranı ayırmaktı.** `unverified_terms`e
`is_title` parametresi eklendi: büyük harf kolu kapanır, **rakam kolu çalışmaya
devam eder** (uydurma model kimliği "GPT-4" hâlâ yakalanır, testle kilitli).
Cümle veren çağıranlar (rapor, quiz) varsayılanı kullanır ve davranışları
DEĞİŞMEZ. Doğrulandı: `eval/report_trap.py` yeniden koşuldu ve Faz 2'nin
sayıları **birebir aynı** çıktı (48 iddia / 44 giren / 4 düşen, tuzak
`/dropped/1`, 0.5487 / grounded, `fidelity_score` 1.0000). Eşik ya da oran
eklenmedi: "başlık mı" sorusunu metinden TAHMİN etmiyoruz, çağıran zaten
biliyor. Düzeltmeden sonra aynı koşumda **7/7 etiket modelden**, 0 düşüş.

**Kapanma ölçümü** (`eval/mindmap_proof.py`, eval.db, 7 küme / 7 LLM çağrısı,
**13/13 kontrol PASS**): 8 düğüm (1 kök + 7 konu) · 20 chunk'ın **20'si** bir
düğümde · her düğümün her chunk'ı için `[Kaynak: ...]` · 7/7 etiket modelden ·
2 kenar (0.6094, 0.5520), ağırlıklar `topic_similarity` ile **birebir**
(yeniden ölçeklenmemiş) · `fidelity_score` 1.0000 · markdown'da `http(s)://`
yok · kümeleme iki ardışık çağrıda aynı.

**Reddedilen alternatifler.**
- `d3-hierarchy` kurmak → **reddedildi.** `STUDIO_PLAN §7` "tek yeni npm
  bağımlılığı" diyordu ve Faz 1 kararı onu Faz 3'e ertelemişti; Faz 3 kararı
  KURMAMAK. Bu harita iki seviyelidir (kök → konular), radyal yerleşim
  `angle = 2π·i/N` — ~20 satır. d3-hierarchy'nin değeri derin/düzensiz
  ağaçların düğüm ayrıştırmasıdır ve burada hiç kullanılmazdı. `package.json`
  **değişmedi**.
- Kapıdan geçemeyen etiketin düğümünü silmek → **reddedildi** (yukarıda).
- `_entity_like`'ın büyük harf kolunu tamamen kaldırmak → **reddedildi**:
  tuzağın "OpenAI"sı yalnızca o koldan yakalanıyor, Faz 2'nin ölçülmüş
  savunması silinirdi.
- Başlık olup olmadığını büyük harf ORANIYLA tahmin etmek → **reddedildi**:
  yeni bir kalibrasyon eşiği doğururdu.
- Kenar ağırlığını `DESIGN_SYSTEM §1.2` bantlarıyla renklendirmek →
  **reddedildi**: o bantlar sorgu→chunk için kalibre edildi; ağırlık çizgi
  KALINLIĞIYLA gösteriliyor.

## Studio Katmanı — Faz 4 (Quiz Üreteci)

Hattan geçen ÜÇÜNCÜ artefakt tipi; ayrıca hattın **okuma sonrası** yüzeyini
açtı (`quiz_attempts`, `/api/quiz/*`) — spec `docs/FEATURE_SPEC.md §12`.

**Çeldiriciyi de LLM yazmıyor.** `STUDIO_PLAN §6.3` "hibrit" öneriyordu (havuz
korpustan, LLM dilbilgisi düzeltir). Faz 4 bir adım ileri gitti: LLM çeldiriciye
HİÇ dokunmuyor. Gerekçe kapının bilinen sınırıdır — kapı grounding ölçüyor,
entailment değil; LLM'e "makul ama YANLIŞ bir şık yaz" demek, yanlışlığı
ölçemediğimiz bir metni cevap anahtarına koymaktır. Korpustan gelen bir terim
ise hem gerçek hem de yanlışlığı KANITLANABİLİR (soru chunk'ında geçmediği
kontrol edilir). Bedeli de sıfır: soru başına bir LLM çağrısı eksiliyor.

Sonuç: dört tipin ÜÇÜ tamamen deterministik (`multiple_choice`, `fill_blank`,
`true_false`), LLM yalnızca `short_answer` için çağrılıyor.

`true_false` **kaynak atfı** üzerinden kuruldu ("«cümle» — bu bilgi X belgesinde
geçiyor"): doğruluk değeri METADATA'dan kesindir, entailment yargısı değil.
Denenen sayısal-mutasyon kurgusu ("130"u "260" yap, korpusta ara) **ölçümle
elendi**: eval.db'de 7 kümenin yalnızca 1'inde soru üretebiliyordu ve rag.db'de
ürettiği tek şey bir URL kimliğinin ("4501968" → "9003936") mutasyonuydu.
Kaynak atfı aynı korpuslarda **7/7 ve 10/10** kapsıyor — üstelik bu ürünün asıl
iddiasını ("hangi belge ne diyor") sınıyor.

**Sadakat kapısına giden metin tip başına DEĞİŞİR** ve bu kasıtlıdır: kapı
modelin UYDURMUŞ olabileceği metni korumalı. `short_answer`da bu referans
cevaptır (`/questions/{i}/answer`), diğer üçünde korpustan birebir alınan
cümledir (`/questions/{i}/evidence`) — orada bağlama bir TUTARLILIK kontrolüdür
ve neredeyse her zaman grounded çıkar. Yani bir quiz'in `fidelity_score`'u
YAPISI GEREĞİ yüksektir ve asıl oynayan bileşen `short_answer` iddialarıdır;
bu, skorun zayıflığı değil tasarımın sonucudur ve gizlenmiyor.

`short_answer` **bir eşiğe indirgenmiyor**: `correct` her zaman `null`,
benzerlik toplam skora KATILMIYOR, `score` yalnızca deterministik sorulardan
hesaplanıyor (hiç yoksa `null` — 0.0 yazmak "hepsini yanlış yaptı" demek
olurdu). Gösterilen sayı iki CEVAP arasındaki simetrik ham cosine'dır ve
`Hit.score` DEĞİLDİR (o sorgu→chunk asimetrik); `DESIGN_SYSTEM §1.2`
bantlarıyla renklendirilmesi açıkça yasaklandı.

### Faz 4'ün ölçümle şekillenen iki kararı

**1. Tip dağılımı tek satırlık rotasyonla dengelenmiyor.** Dört tipin
kurulabilirliği çok farklı: MC/fill_blank cümlede AYIRT EDİCİ terim istiyor
(eval.db'de 7 kümenin 2'sinde, rag.db'de 10 kümenin 6'sında var), `true_false`
yalnızca düzgün bir cümle istiyor, `short_answer` her zaman kuruluyor. Son ikisi
"her zaman kurulabilir" sınıfında olduğu için tek rotasyonda hangisi önce
gelirse MC/FB'nin kurulamadığı HER kümeyi o kapıyor. ÖLÇÜLDÜ: `true_false` önde
→ 7 sorunun **5'i** true_false; `short_answer` önde → 7 sorunun **6'sı**
short_answer. Çözüm, küme index'ine göre ikisinin YEDEKLİK SIRASINI değiştiren
bir tablo oldu (eval.db: 3 TF / 3 SA / 1 FB).

**2. Alfabetik sıralama çeldiricileri ele veriyor.** Havuz `(df, alfabetik)` ile
sıralanınca df=1 olan onlarca terim arasından ilk üç HEP "A" ile başlıyordu:
şıklar `['After', 'Apple', 'Approach', 'Internet']` çıktı ve doğru cevap tek
başına göze battı. Sıralama sha256 tabanlı bir dağıtım anahtarına çevrildi.
`hash()` KULLANILMADI: `PYTHONHASHSEED` süreç başına rastgeledir ve aynı korpus
farklı koşumlarda farklı quiz üretirdi — determinizm sözleşmesi bozulurdu.

Ayrıca soru gövdesi seçiminde dört eleme var, dördü de ölçülmüş bir sorunu
çözüyor: (1) cümle noktalama ile BİTMELİ (başlık satırları "Saklama" gibi
anlamsız boşluklar üretiyordu), (2) büyük harf/rakamla BAŞLAMALI (chunking
kelime penceresiyle çalıştığı için bir chunk'ın ilk "cümlesi" neredeyse her
zaman önceki chunk'tan taşan yarım cümle — kuru koşumda üretilen soru buydu:
«belgeleri aramasını ve bulduğu bilgiyi cevaba dahil etmesini sağlar.»),
(3) 8–40 kelime, (4) `http(s)://` içeren cümle ELENİR — hem anlamsız soru
üretiyordu hem de markdown export'una harici bağlantı sızdırırdı; bu,
AGENTS.md §1.2'nin grep kontrolünü kırabilecek tek yoldu.

**Kapanma ölçümü** (`eval/quiz_proof.py`, eval.db, 7 küme, **16/16 kontrol
PASS**): tuzaksız koşumda 7 soru (3 true_false · 3 short_answer · 1 fill_blank),
0 düşüş; her sorunun cevabı korpusta doğrulanabilir; çeldiriciler soru
chunk'ında geçmiyor; cevap anahtarıyla deneme **1.0 (4/4)**, alakasız cevapla
**0.0**; `short_answer` hepsinde `correct=None`. `--trap` koşumunda tuzak
cümlesi ilk `short_answer`ın REFERANS CEVABINA bilerek enjekte edildi
(enjeksiyon çıktıda açıkça yazılıyor): tuzaklı soru quiz'e **alınmadı**, tuzak
`artifact_claims`'te `/dropped/0` altında duruyor (`unverified_terms`,
`['gpt-4','openaı']`, 0.8496) ve quiz gövdesinde "gpt"/"openai" **0 eşleşme**.

**Reddedilen alternatifler.**
- Çeldiricileri LLM'e yazdırmak → **reddedildi** (yukarıda).
- LLM-hakem ile `short_answer` puanlamak → **reddedildi**: soru başına ek çağrı
  (prefill baskın) ve hakem aynı modelin yanlılığını taşır — `STUDIO_PLAN §6.3`
  bunu zaten reddetmişti.
- `short_answer` için benzerlik eşiği koymak → **reddedildi**: ölçülmemiş bir
  kararı ölçülmüş gibi sunardı.
- `fill_blank` için eşanlamlı sözlüğü (`STUDIO_PLAN §6.3` öneriyordu) →
  **reddedildi**: dışarıdan liste ikinci bir bakım yüzeyi açardı (durak-kelime
  sözlüğünün Faz 2'de reddedilme gerekçesinin aynısı). Boşluk terimi zaten
  ayırt edici bir özel ad/kimlik olduğu için eşanlamlısı pratikte yok.
- Boşluk terimi için ayrı bir "ayırt edicilik" kuralı yazmak → **reddedildi**:
  `fidelity.distinctive_terms` tek doğruluk kaynağı olarak paylaşıldı. Bilinen
  sonucu kaydedildi: `FIDELITY_TERM_MIN_LENGTH=4` yüzünden kısa sayılar ("130",
  "30") boşluk olarak seçilemiyor.
- Quiz'i `eval_set.json`'a kategori olarak eklemek → **reddedildi**;
  `STUDIO_PLAN §9`'un Faz 4 kriteri bunu istiyordu ama gerekçe §10.1.1'in
  birebir aynısı: `eval_set.json` tek bir hattı (`query_router → retrieve →
  answer`) ölçüyor, quiz üretimini o şekle sokmak "23/23"ün ne ölçtüğünü
  SESSİZCE genişletirdi ve her teslime dakikalar + bir 7B yüklemesi bindirirdi.
  Ölçüm kendi koşucusuyla yapıldı. **Eval seti 23 soruda kaldı.**
- `score_attempt`e veritabanı bağlantısı vermek → **reddedildi**: cevap
  anahtarı, atıf ve gerekçe zaten `payload_json`'da ("payload render'ın tek
  girdisidir" kuralının aynısı); parametre hiç kullanılmıyordu, kaldırıldı.
- Puanlama sonucunu `quiz_attempts`e yazmak → **reddedildi**: payload
  değişmediği sürece aynı girdiden aynı sonuç çıkar, ikinci bir doğruluk
  kaynağı olurdu. Yalnızca ham cevaplar saklanıyor.

## Faz 3–4 ortak düzeltme: export sessizce boş dosya döndürüyordu

`GET /api/artifacts/{id}/export` Faz 2'de koşulsuz `report.to_markdown`
çağırıyordu. Mindmap/quiz üretilebilir olduğu ANDA bu yol **200 + boş gövde**
döndürürdü — "sahte sayı göstermeme" ilkesinin aynı ihlali, üstelik hiçbir test
yakalamazdı. Rota artık `kind → to_markdown` sözlüğünden seçiyor; sözlük üç
`kind` üzerinde TAM olduğu için eksik-kind savunma kodu ve yeni hata kodu
yazılmadı. Regresyon testi eklendi.

## Kapı sayıları (Faz 4 sonrası)

eval **23/23** (172 sn, ortalama 7.5 sn/soru) · backend **201 passed** (Faz 2
tabanı 151 + Faz 3–4'ün 50 yeni testi) · offline kanıtı **23/23, 0 soket** ·
`eval/fidelity_trap.py` **PASS (0.5487 / grounded)** · `eval/report_trap.py`
**PASS (48/44/4, birebir aynı)** · `eval/mindmap_proof.py` **PASS 13/13** ·
`eval/quiz_proof.py --trap` **PASS 16/16** · `eval/ui_proof.py` **42/42** ·
`web` build + lint temiz (5/5 statik sayfa) · `package.json` ve
`requirements.txt` **değişmedi**.

### Arayüz kanıtı — teslimde atlanan, sonradan kapatılan boşluk

Faz 3/4 ilk teslim edildiğinde `eval/ui_proof.py` yalnızca RAPOR görünümünü
ölçüyordu (27 kontrol, `?kind=report`). Buna rağmen `FEATURE_SPEC §11.11`'de
"klavyeyle gezilebilir (WCAG AA)" maddesi işaretlenmişti — dayanağı KOD
İNCELEMESİYDİ, ölçüm değil. Oysa Faz 2 tam bu konuda emsal koymuştu: React
etkileşimi gerçek Chromium'da ölçülür.

Boşluk kapatıldı: `ui_proof.py` iki yeni görünümü kapsayacak şekilde
genişletildi (sahte mindmap/quiz üreticileri eklendi, model yine YÜKLENMEZ) ve
**42/42** kontrolle geçti. Yeni ölçülenler: SVG `role="tree"` + düğüm başına
`treeitem` + `aria-level`, roving `tabindex`, `ArrowRight`/`Home`/`End`
gezinmesi, seçili düğümün kaynak listesi, yedek etiketin "korpustan türetildi"
uyarısı; quiz tarafında dört tipin render'ı, `true_false` şıklarının
yerelleşmesi, üç deterministik soruda skorun **3/3** çıkması, `short_answer`
kartında **"Doğru"/"Yanlış" ibaresinin BULUNMAMASI** (§12.8'in görünür kanıtı)
ve denemenin sunucuya kaydedilmesi. Sıfır konsol hatası, sıfır harici istek.

Ölçüm sırasında bulunan teknik ayrıntı: Playwright'ta SVG düğümünde
`inner_text()` çalışmıyor ("Node is not an HTMLElement"); SVG metni
`text_content()` ile okunur.

> Ölçüm sırasında yaşanan gerçek bir olay, kayda geçiriliyor: `run_eval.py` iki
> kez `exit 137` (SIGKILL) aldı. Sebep kodda değildi — `report_trap.py` biter
> bitmez ikinci bir 7B yüklemesi başlatılmıştı ve 16 GB makinede bellek
> yetmedi. AGENTS.md'nin "bir model koşumu ve başka bir iş üst üste binmesin"
> kuralı bu koşumda pratikte doğrulandı. Model koşumları tek tek, araya bellek
> boşalması bırakılarak tekrarlandı ve ikisi de temiz geçti.

## Kapıların model yüklemeyen yarısı CI'a devredildi

`.github/workflows/gates.yml` (yeni). Her push ve PR'da iki iş koşuyor:
`pytest backend/tests -q` ve `web` tarafında `npm ci && npm run build &&
npm run lint`. Üçü de **model yüklemiyor**, toplam maliyet saniyeler.

Gerekçe kayıtta zaten duruyordu: kapı listesi doğruydu ama uygulanması
**insan hafızasına** bağlıydı. Bu bir kez pratikte de patladı — kapıya
"91/91" yazılmıştı, gerçek taban 93'tü ve bayat sayı kaybolan bir testi
yeşil gösterirdi (bkz. AGENTS.md §3). CI, o listeyi yazılı kuraldan
**uygulanan** kurala çeviriyor. Test sayısı yine hiçbir yere yazılmadı;
kapı "sıfır başarısızlık".

**Model yükleyen kapılar CI'a KONMADI** ve bu kasıtlı. Foundry Local yerel
bir runtime; barındırılan runner'da yok, olsaydı bile 7B'yi her push'ta
indirmek gerekirdi. Asıl gerekçe ikincisi: bu projenin ölçüm kuralı "tek
koşum, tek koşucu, teslimde kim koştuysa adı geçer" (AGENTS.md §5).
Gözetimsiz otomatik bir eval koşumu o kaydı bozardı. eval, offline kanıtı
ve faz kapanma ölçümleri elle koşulmaya ve `eval/baselines/`'a
damgalanmaya devam ediyor.

### Denenen ve elenen alternatif: `macos-latest` runner

İlk tasarım `macos-latest`'ti — ölçülmüş tek platform macOS/M4 olduğu için
"koştuğumuz yerde test edelim" savunulabilir görünüyordu. Ölçümle gerek
kalmadığı görüldü: `foundry-local-core` 1.2.4'ün PyPI'da
`manylinux_2_28_x86_64` wheel'i **var** (26 MB, indirilip doğrulandı) ve
`foundry_local_sdk` saf Python (`py3-none-any`) — native ikiliyi import
anında değil, `core_interop.py` içinde çağrı anında `ctypes` ile yüklüyor.
Testler modeli hiç yüklemediği için (`conftest.py`,
`RAG_BACKEND_SKIP_WARMUP=1`) `ubuntu-latest` yetiyor.

Bu, "Linux'ta da çalışır" iddiası DEĞİL. Kanıtlanan tek şey paketin
kurulup **import edilebildiği**; ürünün Linux/Windows'ta çalıştığı hâlâ
ölçülmedi ve README'nin bilinen sınırı olarak duruyor.

Reddedilen ikinci alternatif: `rag/models.py`'deki SDK import'unu tembel
hale getirmek. CI'ı kolaylaştırırdı ama motoru altyapı uğruna değiştirmek
olurdu (AGENTS.md §2.3) ve offline yüzeyine dokunurdu.

`pytest` bu turda `requirements-dev.txt`'e eklendi; daha önce yalnızca
yerel `.venv`'de kuruluydu ve hiçbir dosyada anılmıyordu. `requirements.txt`
ve `package.json` **değişmedi** (`npm ci` lock dosyasına birebir uyar).

## `scope="document"` arayüze bağlandı — ve bağlanırken sessiz bir sapma bulundu

Amaç küçüktü: Studio paneline bir kapsam seçici koymak. `scope="document"`
API'de vardı, testliydi ve README "arayüz girişi yok" diye kaydetmişti.

**Bulgu.** Alan çalışmıyordu — daha doğrusu, çalıştığı sanılan şeyi
yapmıyordu. `base.generate_artifact` 2. adımda koşulsuz `cluster_corpus(conn)`
çağırıyordu; `document_id` yalnızca 1. adımda doğrulanıp 5. adımda
kaydediliyordu. Üç üretici de (`report.py::_report_title`,
`mindmap.py::_map_title`, `quiz.py::_quiz_title`) `scope`/`document_id`'yi
**yalnızca başlık yazmak** için okuyor. Sonuç: `scope="document"` ile üretilen
artefakt *"dosya.pdf Raporu"* başlığını taşıyor ama içeriği **korpusun
tamamından** geliyordu.

`FEATURE_SPEC §9.8`'in hat tablosu 1. adımı "Seçim (scope → **chunk kümesi**)"
diye tanımlıyor. Yani spec doğruydu, kod ondan sapmıştı ve hiçbir test bunu
yakalamıyordu — testler alanın **taşındığını** doğruluyordu, **etki
ettiğini** değil. Faz 1'in "boş kutu" kayması ile aynı sınıf hata: bir şeyin
var olduğunu kanıtlamak, işe yaradığını kanıtlamak değildir.

Seçiciyi bu haliyle göndermek, kullanıcının "yalnızca bu belge" dediği yerde
ona korpus geneli bir artefaktı belge adıyla vermek olurdu — "sahte sayı
göstermeme" ilkesinin aynı ihlali. Bu yüzden önce motor düzeltildi.

**Düzeltme.** `topics.cluster_corpus(conn, document_id=...)` süzgeci aldı ve
`base.generate_artifact` seçili belgeyi kümelemeye geçiriyor. Süzme
`load_matrix`'in DÖNDÜRDÜĞÜ meta üzerinde yapılıyor, SQL'de değil: matris
`db_path` anahtarıyla önbellekli ve belge başına ayrı bir önbellek anahtarı
açmak tek belgelik bir istek için tüm korpusu yeniden okuturdu. `store.py`'ye
ve önbelleğe **dokunulmadı**.

Rotanın ön kontrolü de istenen kapsamla yapılıyor artık: korpus geneli
kümelenebiliyor diye tek chunk'lık bir belgeye "yeterli" demek, akışı açıp
hatayı SSE'nin içinde vermek olurdu. Tek chunk'lık belge artık akış
açılmadan **422 INSUFFICIENT_CORPUS** alıyor — bu bir kısıtlama değil, dürüst
davranış: kapsam belgeyse yeterlilik de belge üzerinden ölçülür.

**Belge kimliği yüzeye çıkarıldı.** `/api/documents` yalnızca `filename`
döndürüyordu, oysa `POST /api/artifacts` tamsayı `document_id` bekliyor —
arayüzün elinde gönderecek bir kimlik **yoktu**, boşluğun asıl sebebi buydu.
`DocumentInfo.id` eklendi ve `has_ocr_chunks` ile **birebir aynı desenle**
türetiliyor (ek sorgu, `store.py`'ye dokunulmadan). Silme yolu hâlâ filename
ile çalışıyor; kimlik ikiye ayrılmadı.

**Arayüz.** Kapsam seçici üç düğmenin de üstünde, tek yerde: kapsam üretilen
tipe değil korpusa ait bir karar. Varsayılan "Tüm belgeler" — mevcut davranış
değişmedi. Seçili belge silinirse kapsam sessizce korpusa döner (alternatif —
seçimi tutup isteği `DOCUMENT_NOT_FOUND` ile düşürmek — kullanıcıya kendi
silmiş olduğu belgeyi hata olarak geri gösterirdi). Belge yokken seçici hiç
render edilmez.

**Reddedilen alternatifler.**
- `components/ui/select.tsx` primitifi → **reddedildi**: yerel `<select>`
  klavye gezinmesini, ekran okuyucu desteğini ve mobil yerel listeyi bedelsiz
  veriyor. Faz 1'in `tabs.tsx` kararının aynısı; `package.json` değişmedi.
- Korpusu kümeleyip sonra seçili belgenin chunk'larını süzmek →
  **reddedildi**: kümelerin merkezleri diğer belgelerin chunk'larıyla
  hesaplanmış olurdu, yani "bu belgenin konuları" değil "korpus konularının
  bu belgeye düşen kısmı" çıkardı. Sessizce farklı bir şey.
- `store.load_matrix`'e belge süzgeci eklemek → **reddedildi**: önbellek
  `db_path` anahtarlı; belge başına anahtar açmak tek belgelik istekte tüm
  korpusu yeniden okuturdu.
- Seçiciyi motor düzeltilmeden göndermek → **reddedildi** (yukarıda).

**Ölçüm.** backend **206 passed** (Faz 4 tabanı 201 + 5 yeni test) ·
`eval/ui_proof.py` **49/49** (önceki taban 42; yedi yeni kontrol kapsam
seçicinin POST gövdesini ve kaydedilen artefaktın kapsamını ölçüyor) ·
`web` build + lint temiz · `package.json` ve `requirements.txt` değişmedi.

Yeni testlerin gerçekten kilit olduğu doğrulandı: `base.py`'deki tek satırlık
düzeltme geçici olarak geri alındığında
`test_generate_artifact_belge_kapsami_ureticiye_daraltilmis_topics_verir`
**kırmızıya döndü**, geri konduğunda yeşile.

## `USE_QUERY_INSTRUCTION` A/B'si — açıkta duran sözün kapatılması

`rag/config.py` "Faz 5'te eval setiyle A/B test edilecek" diye söz vermişti ve
o söz açıkta duruyordu: bayrak ölçülmemiş bir varsayım olarak `True`'ydu.
Ölçüldü.

**Tam eval iki kolda da 23/23.** Bu, "fark yok" demek DEĞİL — eval'in ölçtüğü
şey hangi kaynağın bulunduğu, oysa önekin değiştirdiği şey skorun büyüklüğü.
Ayırt edici ölçüm embedding-only ikinci koşumdan geldi (13 kaynak-doğrulanan
soru: `answerable` + `cross_lingual`, 7B YÜKLENMEDİ):

| | AÇIK | KAPALI | fark |
|---|---|---|---|
| ortalama top-1 skor | 0.7249 | 0.6713 | −0.0536 |
| en düşük skor | 0.5368 (Q21) | 0.4858 (Q21) | −0.0510 |
| top-1 kaynağı değişen | — | — | **0/13** |
| MIN_SCORE altında kalan | 0/13 | 0/13 | — |

13 sorunun 12'sinde önek skoru yükseltiyor, biri (Q08) hariç. Ama **hiçbirinde
getirilen chunk değişmiyor**: önek NE bulunduğunu değil, ne KADAR benzediğini
değiştiriyor.

**Karar: `True` kalıyor, değişiklik YOK.** Getirisi sıralama değil paydır ve
pay, zaten en ince olduğu yerde önemli: diller arası sorularda MIN_SCORE=0.45'e
mesafe 0.087'den 0.036'ya iniyor. Kapatmanın karşılığında ölçülmüş bir kazanç
yok.

**Ölçümün açığa çıkardığı asıl şey.** Bu bayrak bir tercih değil, `MIN_SCORE`'un
kalibrasyon zemini. Eşik — ve `DESIGN_SYSTEM §1.2`'nin güven bantları — bu önek
AÇIKKEN alınmış skorlara göre seçildi. Yani "KAPALI daha iyi çıksaydı" bile
benimsemek tek satırlık bir bayrak çevirme olmazdı, yeniden kalibrasyon
gerektirirdi. Deney bu yüzden baştan "açık bir varsayımı ölçüye bağlamak"
olarak tanımlandı, "retrieval'ı iyileştirmek" olarak değil.

Konu dışı sorular bu A/B'ye alınmadı: önek onların skorunu da düşürür, yani
eleme yönünde çalışır ve karşılaştırmayı tek yönlü olarak kolaylaştırırdı.

## Bu turun kapı sayıları (bakım turu)

Tek ölçüm oturumunda, üst üste binme olmadan alındı: eval **23/23** (163 sn,
ortalama 7.1 sn/soru) · backend **206 passed** · offline kanıtı **23/23,
0 soket** · `eval/fidelity_trap.py` **PASS (0.5487 / grounded)** ·
`eval/ui_proof.py` **49/49** · `web` build + lint temiz (5/5 statik sayfa) ·
`package.json` ve `requirements.txt` **değişmedi**. Baseline damgası:
`eval/baselines/59af499.json`.

Ölçüm sırasında not düşülen bir gözlem: `rag.db`'nin WAL dosyası bir
checkpoint ile ana dosyaya yazıldı (yan etkisiz bir SQLite işlemi, mantıksal
içerik değişmedi) ve bu, `eval/ui_proof.py`'de sessiz bir kırılganlığı görünür
kıldı. `_copy_db` yalnızca ANA dosyayı kopyalıyor ve WAL'i kasıtlı olarak
atıyor — gerekçesi hedefteki bayat WAL'in replay edilmesini önlemek. Ama
kaynakta bekleyen bir WAL varsa aynı kural koşumun **bayat bir korpusu**
ölçmesine yol açıyor: checkpoint öncesi 8 belge, sonrası 1 belge görüldü.
`rag.db` ölçüme girmiyor (eval `eval/eval.db` kullanıyor) ve bu turda hiçbir
sonucu etkilemedi.

**Sonradan düzeltildi.** `_copy_db` artık `shutil.copyfile` yerine SQLite'ın
`Connection.backup` API'sini kullanıyor: kaynağı salt okunur açıyor, WAL dahil
tutarlı bir anlık görüntü üretiyor ve kaynağa DOKUNMUYOR. `PRAGMA
wal_checkpoint` alternatifi reddedildi -- kullanıcının üretim veritabanına
yazardı. Üç regresyon testi eklendi (`backend/tests/test_ui_proof_copy.py`,
model yüklemez, tarayıcı açmaz) ve eski `shutil.copyfile` haline dönüldüğünde
bekleyen-WAL testinin kırmızıya döndüğü doğrulandı. Düzeltmeden sonraki
koşum korpusu artık DOĞRU raporluyor: 1 belge / 41 chunk (önce 8 belge
görüyordu), `ui_proof` **49/49** PASS.

## Entailment katmanı — deney yapıldı ve REDDEDİLDİ

Sadakat kapısının bilinen sınırını (kapı *grounding* ölçer, *entailment*
değil) üçüncü bir katmanla daraltmak denendi: rapora girecek her cümleyi,
bağlandığı bölümün kaynak metnine karşı `qwen2.5-7b`'ye doğrulatmak.
`FIDELITY_MIN_SCORE` yükseltilmedi, `bind_claims` değiştirilmedi.

**Deney reddedildi.** Kod geri alındı; kalan tek şey bu kayıt.

### Ret kriteri KODDAN ÖNCE yazılmıştı

1. Korpus sözcük dağarcığıyla yazılmış, korpusla çelişen bir cümle rapordan
   **düşürülecek**.
2. `report_trap.py`'nin koruduğu **44 iddia 44 kalacak**.
3. `fidelity_trap.py` **PASS kalacak** (0.5487 / grounded).
4. Süre artışı ölçülecek.

### Band kurulamayacağı ÖNCE ölçüldü

`eval.db`'deki iki gerçek rapor koşumunun 88 korunan iddiası şu skorlara
dağılıyor: 0.49→4 · 0.56→20 · 0.64→14 · 0.78→24 · 0.81→26. Tuzağın 0.5487'si
**20 gerçek iddianın bulunduğu kovanın içinde** — `MIN_SCORE`
kalibrasyonundaki örtüşmenin birebir aynısı. Yani "riskli band" diye bir şey
yok; katman korunan TÜM iddialara bakmak zorundaydı. Bu ölçüm hâlâ geçerli ve
gelecekteki her band önerisini baştan çürütüyor.

### Tuzak: korpusun KENDİ sözcükleriyle yazılmış çelişki

Faz 2'nin sözcüksel katmanı `fidelity_trap`'in tuzağını yakalıyor, ama
**entailment sayesinde değil**: tuzakta korpusta hiç geçmeyen iki özel ad var
("GPT-4", "OpenAI"). Arkada kalan boşluğu ölçmek için özel adsız bir çelişki
yazıldı:

- **Tuzak:** "Embedding vektörleri veritabanında saklanmaz; her sorguda
  yeniden hesaplanır." (korpus bunun TERSİNİ söylüyor)
- **Kontrol:** "Embedding vektörleri belge parçalarıyla birlikte bir tabloda
  saklanır." (çelişmiyor — düşmemeli)

İlk iki katmanın bu boşluğu gerçekten göremediği **ölçüldü**: tuzak
**0.7389 / grounded**, `unverified_terms` **[]** (katman sessiz). Kontrol
0.7362 / grounded.

### İki koşum, iki farklı başarısızlık kipi

| Bağlam | Doğrulayıcının ham cevabı | Sonuç |
|---|---|---|
| 1 chunk (bağlanan) | `1: HAYIR\n2: HAYIR` | Tuzak düştü ama **kontrol de düştü** — yanlış pozitif |
| 5 chunk (belgelerin tamamı) | `2\nEvet` | Biçim çöktü → **fail-open**, katman hiçbir şey düşürmedi |

**İlk koşumun kurgusu yanlıştı ve düzeltildi** (kayda geçiriliyor, §1.6):
bağlam olarak yalnızca bağlanan tek chunk verilmişti. Model haksız değildi —
kontrolü destekleyen cümle belge_04'ün BAŞKA bir chunk'ındaydı, yani gördüğü
bağlama göre "HAYIR" **doğru** cevaptı. Rapor hattında katman bölümün tüm
bağlam chunk'larını alır; tuzak da onu yansıtmalıydı.

Ama düzeltilmiş kurgu daha kötü bir şey gösterdi: 5 chunk'lık bağlamda model
istenen satır biçimini (`1: EVET`) **tamamen bıraktı** ve `2\nEvet` yazdı.
Ayrıştırıcı bunu okuyamadığı için katman fail-open davrandı — yani **sessizce
kapandı**.

### Neden reddedildi

Kriter 1 temsili kurguda sağlanmadı. Kriter 2 (`report_trap` 44→44)
**ölçülmedi**: kriter 1 zaten kararı verdiğinden 4 dakikalık koşum
harcanmadı — bu, kriter 2'nin sağlandığı anlamına GELMEZ.

Asıl gerekçe tek bir başarısız kriterden daha ağır: **fail-open bir katman,
güvenilmez olduğunda bunu göstermez.** Rapor tıpatıp aynı görünür, `dropped`
listesi boştur, kullanıcı üçüncü bir savunmanın çalıştığını sanır. Hiç
katman olmamasından daha kötüdür, çünkü var olmayan bir güvenceyi var gibi
gösterir. Fail-closed alternatifi de reddedildi: doğrulayıcı sustuğunda
raporu sessizce boşaltırdı (mindmap'in §11.5 kararının aynı gerekçesi).

Biçim çöküşü bu projede **ikinci kez** ölçülüyor: Faz 3'te de prompt'a
eklenen "cümle düzeni kullan" kuralı ölçülmüş ve işe yaramamıştı
(`_entity_like` docstring'i, FEATURE_SPEC §11.4). O zaman çözüm prompt'u
zorlamak değil, kararı **koda** taşımaktı. Aynı ders burada da geçerli:
`qwen2.5-7b`'ye biçim sözleşmesi dayatılamıyor, dolayısıyla üzerine bir kapı
kurulamıyor.

### Bilinen sınır olarak DURUYOR

Entailment boşluğu kapanmadı ve gizlenmiyor. Telafi hâlâ Faz 2'nin sözcüksel
katmanı: ürün, özel ad taşıyan çelişkili iddiayı **yayımlamıyor**. Özel ad
taşımayan çelişki için ölçülmüş bir savunma **yok** — bu, `fidelity_trap`'in
pinlediğinden daha geniş bir sınırdır ve artık sayılarıyla kayıtlı.

Gelecekte denenebilecek ama BU turda denenmeyen yol: doğrulayıcı olarak
biçim sözleşmesine uyabilen ayrı bir model. Foundry Local kataloğunda böyle
bir model olup olmadığı ölçülmedi; ölçülmeden önerilmiyor.

## v2'nin çalışma anı bağımlılıkları kendi adına yazıldı

`requirements.txt` yorumu "uvicorn/starlette/python-multipart/pydantic zaten
kuruluydu" diyordu. İfade DOĞRUYDU ama gerekçesi yanlıştı: `pip show`
ölçümü ikisinin de **streamlit'in** bağımlılığı olarak geldiğini gösterdi,
fastapi'nin değil (`fastapi` yalnızca annotated-doc/pydantic/starlette/
typing-extensions'a bağlı; uvicorn `fastapi[standard]` ekstrasında).

Yani v2 ürününün HTTP sunucusu ve PDF yüklemesinin çok parçalı form
ayrıştırıcısı, **v1 arayüzünün** bağımlılığından geliyordu. Streamlit
listeden çıkarıldığı gün README'nin `uvicorn backend.main:app` komutu ve
`POST /api/documents` yolu sessizce kırılırdı -- ve hiçbir test bunu
yakalamazdı, çünkü geliştirme ortamında paketler zaten kurulu.

`uvicorn>=0.52.1` ve `python-multipart>=0.0.32` açıkça beyan edildi. Kurulan
paket kümesi **değişmiyor** (ikisi de zaten geliyordu); değişen tek şey,
ürünün kendi bağımlılığının artık kendi adına yazılı olması.

Bu, Studio fazlarının "requirements.txt değişmedi" ölçümleriyle çelişmez: o
iddialar ilgili fazın yeni bir çalışma anı bağımlılığı EKLEMEDİĞİNİ söylüyor,
listenin kalıcı olarak donduğunu değil.

## Açık işler

**Studio katmanının dört fazı da kapandı**; `docs/STUDIO_PLAN.md §9`'da planlanan
işlerin tamamı ölçümle teslim edildi.

Bu bakım turunda kapananlar: MIT lisansı · model yüklemeyen kapıların CI'a
devri · `FEATURE_SPEC §9.10`'un işaretsiz kutuları · `scope="document"`
(motor düzeltmesi + arayüz girişi) · `USE_QUERY_INSTRUCTION` A/B'si.

Bu turda DENENİP REDDEDİLEN: entailment katmanı (yukarıda, sayılarıyla).

Açıkta kalan, gerekçesi kayıtlı işler:
- **Entailment boşluğu**, artık daha geniş biçimde kayıtlı: özel ad taşımayan
  çelişki için ölçülmüş savunma yok. LLM doğrulayıcı denendi ve reddedildi.
- **Hibrit retrieval** kapalı duruyor. Önkoşulu kod değil korpus büyüklüğü;
  bu ölçekte (20–40 chunk) ölçülmüş getirisi yok (23/23 → 22/23).
- **Data Table artefaktı** (STUDIO_PLAN §8): hat üç tiple kanıtlandı,
  dördüncüsü değerlendirilebilir.
- **Windows/CUDA host davranışı** ölçülmedi; yalnızca macOS/M4 ölçüldü. CI'ın
  `ubuntu-latest`'te yeşil olması yalnızca paketin kurulup import edilebildiğini
  gösterir, ürünün orada çalıştığını DEĞİL.

Kapsam dışı bırakılan ve gerekçesi kayıtlı olanlar (STUDIO_PLAN §8): Audio/Video
Overview (kaliteli yerel TTS Foundry Local katalogunda yok; bulut TTS ürünün tek
satış argümanını siler), Slide Deck / Infographic / Data Table (aynı hattın
farklı render'ları — hat artık üç tiple kanıtlandı, değerlendirilebilir).

**Taşınan bilinen sınırlar** (hiçbiri Faz 3–4'te kapanmadı, hiçbiri gizlenmiyor):
- Sadakat kapısının **entailment boşluğu** duruyor: konuya yakın ama korpusla
  çelişen iddia hâlâ `grounded` çıkıyor (`eval/fidelity_trap.py`, 0.5487).
  Telafi üç fazda da aynı: ürün o iddiayı YAYIMLAMIYOR.
- `FIDELITY_TERM_MIN_LENGTH=4` yüzünden kısa sayılar ("130", "30") quiz'de
  boşluk terimi olarak seçilemiyor.
- Çeldirici havuzu `_entity_like` sezgisiyle sınırlı: cümle içinde büyük harfle
  yazılmış sıradan sözcükler ("Bunun") havuza girebiliyor. Gerçek korpus
  terimleri oldukları için yanlış değiller, ama zayıf çeldirici oluyorlar.
- `qwen2.5-7b`'nin Türkçesi kusursuz değil; üretilen bir etikette aksanlı yazım
  görüldü ("Belge Parçalama Stratégisi"). Kayda geçti, düzeltilmedi.

## Hızlı komutlar

```bash
.venv/bin/python cli.py "RAG kaç adımdan oluşur?"       # tek soru
.venv/bin/python cli.py --show-chunks                    # etkileşimli, bağlamlı
.venv/bin/streamlit run streamlit_app.py                 # web arayüzü
.venv/bin/python eval/run_eval.py                        # 23 soruluk değerlendirme
.venv/bin/python eval/offline_proof.py                   # + ağ denetimi kaydı
.venv/bin/python -m pytest backend/tests -q               # backend testleri (model YÜKLEMEZ)
.venv/bin/python eval/mindmap_proof.py                    # Faz 3 kapanma ölçümü
.venv/bin/python eval/quiz_proof.py --trap                # Faz 4 kapanma ölçümü
.venv/bin/python -m rag.ingest --pdf dosya.pdf            # yeni belge yükle
```
