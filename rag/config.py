"""
Projenin tek ayar noktası. Tüm modüller sabitleri buradan okur; hiçbir modül
model adını veya eşik değerini kendi içinde tanımlamaz.
"""

from pathlib import Path

# --- Foundry Local ---------------------------------------------------------

# Tüm script'ler AYNI app_name'i kullanmalı. Farklı app_name'ler ayrı uygulama
# veri dizinlerine düşebilir ve indirilmiş modellerin paylaşılmasını engeller.
APP_NAME = "foundry_local_rag"

EMBEDDING_MODEL = "qwen3-embedding-0.6b"

# Model seçimi TAM DEĞERLENDİRME SETİYLE ölçüldü (eval/results.json):
#   qwen2.5-7b : 15/15  (answerable 10/10, unanswerable 3/3, edge 2/2)
#   phi-4-mini : 12/15  (answerable 10/10, unanswerable 0/3, edge 2/2)
#
# Fark tam da en kritik yerde: phi-4-mini cevaplanamaz soruların ÜÇÜNDE DE
# reddetmek yerine uydurdu. İki model de retrieval'da 10/10 -- yani sorun
# arama değil, üretim.
#
# Bu ölçümü yeniden üretmek için:
#   python eval/run_eval.py --model phi-4-mini --json
CHAT_MODEL = "qwen2.5-7b"
ALT_CHAT_MODEL = "phi-4-mini"

# --- Veritabanı ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "rag.db"

# --- Chunking --------------------------------------------------------------

# PDF metni için kelime penceresi. Sayfalar ~400-600 kelime olduğundan bu ayar
# sayfa başına 3-5 chunk üretir; top-k=4 ile bağlam ~500 kelimede kalır.
CHUNK_WORDS = 130
CHUNK_OVERLAP_WORDS = 30

# data/*.md fixture'ları için ayrı ve daha küçük pencere. Belgeler ~130 kelime
# olduğundan CHUNK_WORDS ile her belge tek chunk'a düşer; o zaman top-k=4
# korpusun yarısını döndürür ve değerlendirme seti retrieval'ı ölçemez hale
# gelir. 60 kelime, belge başına 2-3 chunk üretir.
MARKDOWN_CHUNK_WORDS = 60

# Metin katmanı bu kadar kelimeden azsa sayfa "boş/taranmış" sayılır ve
# OCR'a düşer (OCR yoksa atlanıp uyarı listesine eklenir).
MIN_WORDS_PER_PAGE = 15

# --- Retrieval -------------------------------------------------------------

TOP_K = 4

# Cosine benzerliği bu eşiğin altındaysa LLM hiç çağrılmaz, doğrudan
# "bilmiyorum" dönülür.
#
# 15 soruluk değerlendirme setiyle kalibre edildi
# (python eval/run_eval.py --sweep-threshold):
#   cevaplanabilir 10 soru : 0.651 - 0.841
#   diğer 4 soru           : 0.429 - 0.741
#
# Gruplar örtüşüyor: tek bir eşik ikisini ayıramaz. Bu embedding retrieval'ın
# doğasında var -- anlamsal benzerlik, cevabın orada olduğu anlamına gelmez.
# En yüksek skorlu iki "cevapsız" soru (0.736 ve 0.741) korpusla AYNI konuda;
# biri cosine-Öklid karşılaştırması, diğeri fine-tuning prosedürü soruyor.
# Bu yüzden savunma iki katmanlı:
#   1) Bu eşik, konu dışı soruları LLM'e hiç gitmeden eler (ucuz ve kesin).
#   2) "Konu yakın ama cevap yok" kararını system prompt ile LLM verir.
#
# Eşik seçimi 0.55'ten 0.45'e indirildi. Sebep: eval setinin 10 cevaplanabilir
# sorusu 0.65+ alıyor, ama set dışından sorulan "Pencere boyu ve örtüşme kaç
# kelimedir?" sorusu -- cevabı belge_06'da AÇIKÇA yazan bir soru -- yalnızca
# 0.494 aldı ve 0.55 eşiğinde reddedildi. Yani eşik eval setinin ifade
# biçimlerine aşırı uydurulmuştu; 10 örnek gerçek taban değil.
#
# 0.45'te değerlendirme seti hâlâ 15/15 geçiyor (0.40-0.55 aralığının tamamında
# geçiyor), ama recall payı iki katına çıkıyor. Yanlış negatif (cevabı olan
# soruyu reddetmek) kullanıcı için, zor soruyu LLM'e gönderip ~5 saniyede doğru
# reddetmesini beklemekten daha kötü. İkinci katman güvenilir çalıştığı için
# eşiği agresif tutmanın getirisi yok; işi sadece konu DIŞI soruları elemek
# (İstanbul nüfusu: 0.274) ve gecikmeden tasarruf etmek.
MIN_SCORE = 0.45

# Qwen3 embedding modelleri retrieval'da asimetrik çalışır: sorguya talimat
# öneki eklenir, pasajlara eklenmez. Faz 5'te eval setiyle A/B test edilecek.
USE_QUERY_INSTRUCTION = True
QUERY_INSTRUCTION = (
    "Instruct: Bir soruya cevap veren belge parçalarını bul\nQuery: "
)

# Embedding'ler bu büyüklükte gruplar halinde hesaplanır. Tek seferde yüzlerce
# chunk göndermek bellek ve zaman aşımı riski yaratır.
EMBED_BATCH_SIZE = 32

# --- Cevap üretimi ---------------------------------------------------------

MAX_ANSWER_TOKENS = 300

# DİKKAT: Bu iki değeri ayarlayarak çıktıyı değiştirmeye çalışmayın.
# Ölçtük: SDK bunları istek gövdesine koyuyor (ChatClientSettings._serialize()
# içinde görünüyorlar) ama Foundry Local runtime'ı yok sayıyor — temperature
# 0.0 ile 1.5 birebir aynı çıktıyı, farklı random_seed'ler birebir aynı çıktıyı
# üretiyor. Yani üretim deterministik. ChatClientSettings alanlarından pratikte
# yalnızca max_tokens etkili. Tekrar/kalite sorunları prompt ve model seçimiyle
# çözülür, sampling ile değil.
TEMPERATURE = 0.2
TOP_P = 0.9

# DİKKAT: Bu metin hem system prompt'a gömülüdür hem de modelin reddettiğini
# ANLAMAK için kullanılır (answer.py: NO_ANSWER_TEXT alt dizesi cevapta var mı).
# Bu tespit birebir alt dize eşleşmesine dayanır ve KIRILGANDIR: model metni
# birebir üretmezse reddetme yakalanmaz.
#
# Ölçümle görüldü (eval/results.json, phi-4-mini Q13): model "Bu bilgi
# YÜKLENDİĞİNİZ belgelerde yok" yazdı (doğrusu "yüklediğiniz"), tek harflik
# fark tespiti kaçırdı ve arkasına uydurma içerik ekledi. qwen2.5-7b metni
# birebir ürettiği için bu sorun aktif modelde görülmüyor.
#
# Model değiştirilirse bu kırılganlık yeniden değerlendirilmeli; daha sağlam
# bir yol yapılandırılmış çıktı (response_format) olurdu.
NO_ANSWER_TEXT = "Bu bilgi yüklediğiniz belgelerde yok."
