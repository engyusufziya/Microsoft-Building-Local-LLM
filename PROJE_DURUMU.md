# Proje Durumu

> Bu dosya projenin güncel teknik durumunu, alınan kararları ve gerekçelerini
> özetler. Aşağıdaki her sonuç koddan veya ölçümden doğrulanmıştır; hiçbiri
> varsayım değildir.

## Proje

Microsoft Türkiye AI Innovators programı kapsamında geliştirilen, Foundry
Local üzerinde **tamamen offline çalışan Türkçe bir PDF belge Q&A asistanı**.
Kullanıcı PDF yükler, sistem belgeyi parçalayıp embed eder; sorular yalnızca
yüklenen belgelerden, kaynak atıflı olarak cevaplanır.

Motor (RAG çekirdeği) tamamlanmış ve ölçülmüş durumda. Proje şu anda
Streamlit/CLI prototipinden, portföy niteliğinde bir SaaS ürününe
dönüştürülüyor (bkz. "v2 Dönüşümü" bölümü).

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

15 soruluk set (10 cevaplanabilir + 3 cevaplanamaz "yakın tuzak" + 2 kenar
durum): **15/15 geçiyor**. Retrieval **10/10** doğru kaynak belgeyi
buluyor. Ortalama 6.6 sn/soru (non-streaming). Eşik kısa devresinde
(konu dışı soru, LLM hiç çağrılmıyor) 0.1 sn.

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

**Faz 2 (Design System) — taslak hazır, uygulanabilir plana çevriliyor.**
Renk paleti Indigo/Purple + retrieval güven skoru için semantik renk
katmanı (≥0.70 güçlü, 0.55–0.70 orta, 0.45–0.55 zayıf, <0.45 elendi).
Tipografi Inter + JetBrains Mono (yerel paketlenmiş, CDN yok). Bileşen
kütüphanesi shadcn/ui. Üç kolonlu masaüstü düzeni: Sidebar (260px) ·
Chat (esnek) · Retrieval Inspector (380px, kalıcı).

**Sonraki adımlar:** Faz 3 (Core Features & Explainability spec) onayı,
ardından Faz 4 (kodlama).

## Açık işler

- Offline kanıtı: Wi-Fi kapalı tam eval koşumu ve kaydı.
- v2 arayüzünün baştan sona kurulması (yukarıda özetlenen plan).

## Hızlı komutlar

```bash
.venv/bin/python cli.py "RAG kaç adımdan oluşur?"       # tek soru
.venv/bin/python cli.py --show-chunks                    # etkileşimli, bağlamlı
.venv/bin/streamlit run streamlit_app.py                 # web arayüzü
.venv/bin/python eval/run_eval.py                        # 15 soruluk değerlendirme
.venv/bin/python -m rag.ingest --pdf dosya.pdf            # yeni belge yükle
```
