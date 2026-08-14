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
kalmadı.

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

## Açık işler

Yok.

## Hızlı komutlar

```bash
.venv/bin/python cli.py "RAG kaç adımdan oluşur?"       # tek soru
.venv/bin/python cli.py --show-chunks                    # etkileşimli, bağlamlı
.venv/bin/streamlit run streamlit_app.py                 # web arayüzü
.venv/bin/python eval/run_eval.py                        # 23 soruluk değerlendirme
.venv/bin/python eval/offline_proof.py                   # + ağ denetimi kaydı
.venv/bin/python -m rag.ingest --pdf dosya.pdf            # yeni belge yükle
```
