# Proje Durumu — Local RAG AI Assistant (Foundry Local)

> Bu dosyayı Claude Code'a (VS Code) verip "bu projeye kaldığımız yerden devam
> edelim, önce bu dosyayı oku" diyerek bağlamı aktarabilirsin.

## Proje

Microsoft Türkiye AI Innovators programı — Foundry Local + RAG ile tamamen
offline çalışan Türkçe bir belge Q&A asistanı. 2 günlük sprint hedefi.
macOS Apple Silicon üzerinde geliştiriliyor.

## Şu ana kadar doğrulanmış kararlar

- **Ortam:** Foundry Local kurulu (Homebrew), Python venv + `foundry-local-sdk` kurulu.

- **Chat modeli: KARAR HENÜZ KESİNLEŞMEDİ, karşılaştırma yarım kaldı.**
  - `qwen2.5-0.5b` denendi: Türkçe'de çok tutarsız çıktı verdi, elendi.
  - `phi-4-mini` (GPU/Metal doğrulandı, model ID `Phi-4-mini-instruct-generic-gpu:5`):
    açık uçlu/bağlamsız soruda Türkçe halüsinasyon ve tekrar döngüsü gösterdi
    ("geriatörik" gibi uydurma terimler). **Ama bağlam verilip (RAG'e yakın
    koşul) üretim uzunluğu sınırlandığında temiz, doğru, tekrarsız Türkçe
    cevap üretti.** Şu ana kadarki en güçlü aday.
  - `qwen2.5-7b`: benchmark verisinde (Microsoft'un phi-4-mini model kartı
    karşılaştırması) genel skor ve çok dillilikte phi-4-mini'den daha iyi
    görünüyor (Multilingual MMLU 64.4 vs 49.3). Kullanıcı bunu da test etmek
    istedi; `test_qwen25_7b_grounded.py` hazırlandı (phi-4-mini ile aynı
    bağlam/sorularla birebir kıyaslanabilir), **ama indirilip çalıştırılıp
    sonucu değerlendirilmedi.** GPU varyantı ~5.2 GB, phi-4-mini'nin (~3.7 GB)
    üzerinde, 16 GB+ RAM önerilir (kullanıcının gerçek RAM/çip bilgisi hâlâ
    doğrulanmadı).
  - **Yapılacak ilk iş: `test_qwen25_7b_grounded.py`'yi çalıştırıp phi-4-mini'nin
    bilinen iyi sonucuyla (üç adım + amaç sorularına temiz cevap) kıyaslayıp
    chat modelini kesinleştirmek.**
- **Dil:** Türkçe. Belge seti Türkçe hazırlandı.
- **Belge seti:** `data/` klasöründe 6 adet `.md` dosyası — projenin kendi
  kavramlarını anlatıyor (RAG, embedding, Foundry Local, SQLite, prompt
  engineering, chunking). Kaynağı doğrulanmış, orijinal yazılmış içerik.

## Mimari

```
Kullanıcı → Streamlit arayüzü → RAG pipeline
  1. Soru embed edilir (qwen3-embedding-0.6b)
  2. SQLite'tan (rag.db) en benzer top-k chunk bulunur (cosine similarity)
  3. Bağlam + soru, [KESİNLEŞMEMİŞ chat modeli]'ne system prompt ile gönderilir
  4. Model sadece bağlama dayanarak cevap üretir
```

## Mevcut test/yardımcı script'ler (proje klasöründe olmalı)

Bunları tekrar yazmaya gerek yok, hepsi hazır ve daha önce en az bir kez
çalıştırıldı:

- `test_setup.py` — embedding + chat modelinin temel çalışırlığını doğrular.
- `test_phi4mini.py` — phi-4-mini'yi açık uçlu Türkçe sorularla test eder
  (halüsinasyon/tekrar döngüsü sorununu burada gördük).
- `test_phi4mini_grounded.py` — phi-4-mini'yi bağlam verilerek test eder
  (temiz sonuç bunda alındı, RAG'in gerçek koşuluna en yakın test).
- `test_qwen25_7b_grounded.py` — aynı bağlam/sorularla qwen2.5-7b testi.
  **Sonucu henüz alınmadı, öncelik bu.**
- `ingest.py` — belgeleri chunk'layıp embed edip SQLite'a yazan script.
  **İçinde düzeltilmemiş olabilecek bir hata var, aşağıya bak.**

## Şu anki blokaj / son yapılan iş

İki paralel açık iş var:

1. **Model karşılaştırması yarım kaldı.** `test_qwen25_7b_grounded.py`
   hazırlandı ama çalıştırılmadı/sonucu değerlendirilmedi. phi-4-mini'nin
   bilinen iyi sonucuyla kıyaslanıp chat modeli kesinleştirilmeli.
2. **`ingest.py` içinde bilinen bir hata vardı:** script içindeki
   `EMBEDDING_MODEL` değişkeni bir noktada yanlışlıkla `"phi-4-mini"` olarak
   ayarlanmıştı (olması gereken: `"qwen3-embedding-0.6b"`). Kullanıcıya bunu
   `grep -n "EMBEDDING_MODEL" ingest.py` ile kontrol edip düzeltmesi
   söylendi ama düzeltildiği teyit edilmedi. **Claude Code önce bu satırı
   kontrol etmeli.**

## Sıradaki adımlar (öncelik sırasıyla)

1. `test_qwen25_7b_grounded.py`'yi çalıştır, phi-4-mini'nin bilinen iyi
   sonucuyla kıyasla, chat modelini kesinleştir.
2. `ingest.py`'deki `EMBEDDING_MODEL` satırını kontrol et/düzelt, çalıştır,
   `rag.db` oluştuğunu ve chunk sayısının beklenenle eşleştiğini doğrula.
3. `retrieve.py` yaz: `get_top_chunks(query, k=3)` — cosine similarity ile
   SQLite'tan en benzer chunk'ları getirir. 5 test sorusuyla gözle doğrula.
4. `answer_query()` yaz: retrieval + seçilen chat modelinin client'ını
   birleştir. System prompt: "sadece bağlamı kullan, kısa cevap ver, tekrar
   etme."
5. Kaynak atıfı ekle (`[Kaynak: dosya_adı]`) + similarity eşiği (düşük
   skorda LLM'i çağırmadan "bilmiyorum" dönsün).
6. Streamlit arayüzü (`@st.cache_resource` ile model önbellekleme şart,
   yoksa her soruda modeller yeniden yüklenir).
7. 15 soruluk değerlendirme seti (10 cevaplanabilir + 3 cevaplanamaz + 2
   kenar durum).
8. Offline kanıtı (Wi-Fi kapalı test).
9. README + kod temizliği + sunum provası.

## Önemli teknik notlar

- Foundry Local Python SDK güncel API'si (doğrulanmış, Microsoft Learn'den):
  `Configuration`, `FoundryLocalManager.initialize()`,
  `manager.catalog.get_model(alias)`, `.download()`, `.load()`,
  `.get_embedding_client()` / `.get_chat_client()`,
  `client.generate_embeddings(list)`, `client.complete_streaming_chat(messages)`.
- Streaming loop'ta son chunk'ta `chunk.choices` boş gelebilir — kontrol
  etmeden `chunk.choices[0]` erişmek `IndexError` verir.
- GPU/CPU kontrolü: `model.id` içinde `-gpu` veya `-cpu` geçer, yüklemeden
  önce yazdırıp doğrulamak iyi bir alışkanlık.
- macOS'ta paket: `pip install foundry-local-sdk` (Windows'a özel
  `foundry-local-sdk-winml` DEĞİL).
