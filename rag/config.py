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

# --- Hibrit retrieval (BM25 + dense) ----------------------------------------
#
# Yalnızca ADAY HAVUZUNU genişletir: dense (cosine) top-k'nin dışında kalan
# ama BM25'e göre güçlü sözcüksel eşleşmesi olan chunk'lar havuza eklenir.
# Hit.score HER ZAMAN ham cosine'dır -- MIN_SCORE, Inspector renk bantları ve
# DESIGN_SYSTEM §1.2 semantiği bu alana bağlı; RRF/BM25 skoru asla Hit.score
# alanına yazılmaz (bkz. rag/retrieve.py). Yani bu, eşiği DEĞİL, k=4 sınırının
# dışarıda bıraktığı sözcüksel isabetleri (özel adlar, model kimlikleri,
# diller arası teknik terimler) kurtarır.
#
# 23 soruluk değerlendirme setiyle ÖLÇÜLDÜ (python eval/run_eval.py --json):
#   hibrit KAPALI : 23/23
#   hibrit AÇIK   : 22/23  (Q23 düşüyor)
#
# Q23 ("Bu projenin SQLite tabanlı deposu için ANN gerekli mi?") hem konu
# hem lexical olarak belge_04'e (SQLite) ve belge_07'ye (ANN) birden
# yakın. Dense-only'de belge_07 k=4'e ZAR ZOR sığıyordu (4. sırada, 0.551).
# Hibritte BM25 "SQLite"/"tabanlı"/"deposu" üzerinden belge_04'ü DAHA DA
# güçlendiriyor (hem dense hem BM25 aynı yönde -- bu YANLIŞ bir sinyal
# değil, gerçek bir çok-konulu belirsizlik) ve belge_07'nin zaten kırılgan
# olan 4. sıradaki yerini alıyor.
#
# Bu, hibritin YANLIŞ olduğu anlamına gelmez -- store.bm25_candidates'in
# birim testleri (backend/tests/test_hybrid_retrieval.py) k sınırının
# dışında kalan BİREBİR terim eşleşmelerini gerçekten kurtardığını
# gösteriyor. Ama BU KORPUSTA (20-40 chunk) rekabet o kadar düşük ki dense
# zaten neredeyse her şeyi buluyor; hibritin getirisi bu ölçekte henüz
# maliyetini karşılamıyor. Korpus büyüdükçe (k=4 için rekabet arttıkça)
# faydasının artması beklenir -- ama bu bir TAHMİN, "23 soruyla 22/23"
# ölçümünün üzerine iddia eklemek bu projenin MIN_SCORE'da kaçındığı hatanın
# aynısı olurdu (küçük örnek setine aşırı güvenmek). Bu yüzden varsayılan
# KAPALI; özellik tam çalışır ve test edilmiş durumda, bir bayrakla açılır.
HYBRID_RETRIEVAL_ENABLED = False

# BM25 aday havuzu bu kadar sonuç getirir (dense'in üstüne EKLENİR, yerini
# almaz). Yüksek tutmanın maliyeti yok -- FTS5 sorgusu SQLite içi, milisaniye
# altı; k=4'e indirgeme yine RRF ile yapılır.
BM25_CANDIDATE_LIMIT = 20

# Reciprocal Rank Fusion sabiti. Cormack ve ark. (2009) tarafından önerilen
# standart değer; sıralamaları KONUMLARINA göre birleştirir (ham skora göre
# değil), böylece cosine [0,1] ile BM25 [0,∞) ölçek uyuşmazlığı hiç sorun
# olmaz. Değiştirilmesi gereken bir kalibrasyon parametresi değildir.
RRF_K = 60

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

# ÖLÇÜLDÜ (gecikme incelemesi): asıl gecikme kaynağı PREFILL (bağlam işleme,
# ~5-9 sn, TOP_K=4 chunk için), decode DEĞİL -- 8-79 kelimelik gerçek eval
# cevapları arasında süre ile kelime sayısı arasında korelasyon yok (örn. 5
# kelimelik bir ret 16 sn sürerken 79 kelimelik bir özet 27 sn sürebiliyor).
# Yani bu değeri düşürmek TİPİK cevapları hızlandırmaz -- asıl gecikme
# çözümü warmup'ın gerçek bir çıkarım çağrısı içermesidir (bkz.
# backend/main.py::_warm_inference_paths). Yine de 300, "en fazla 3 cümle"
# talimatını modelin bazen görmezden gelmesi ihtimaline karşı bir ÜST SINIR
# olarak gereğinden geniş; 220'ye indirildi -- tipik cevaplar için hâlâ bol
# pay bırakıyor (ölçülen tipik cevaplar 10-80 kelime ~15-110 token), yalnızca
# UÇ (runaway/tekrar döngüsü) durumda tavanı erken keser.
MAX_ANSWER_TOKENS = 220

# DİKKAT: Bu iki değeri ayarlayarak çıktıyı değiştirmeye çalışmayın.
# Ölçtük: SDK bunları istek gövdesine koyuyor (ChatClientSettings._serialize()
# içinde görünüyorlar) ama Foundry Local runtime'ı yok sayıyor — temperature
# 0.0 ile 1.5 birebir aynı çıktıyı, farklı random_seed'ler birebir aynı çıktıyı
# üretiyor. Yani üretim deterministik. ChatClientSettings alanlarından pratikte
# yalnızca max_tokens etkili. Tekrar/kalite sorunları prompt ve model seçimiyle
# çözülür, sampling ile değil.
TEMPERATURE = 0.2
TOP_P = 0.9

# --- Sorgu yönlendirme (query routing) -------------------------------------

# ÖLÇÜLDÜ: dense retrieval "İlgili dökümanı bana özetle" gibi META sorguları
# yapısal olarak karşılayamaz. Aynı Türkçe pasaja karşı:
#   "RAG kaç adımdan oluşur?"      -> 0.766   (içerik sorusu)
#   "İlgili dökümanı bana özetle"  -> 0.322   (meta sorgu, -0.445)
# Meta sorgu hiçbir İÇERİK terimi taşımaz; benzerlik araması eşleşecek bir şey
# bulamaz. Belge İngilizce olduğunda üstüne diller arası ceza da binip 0.273'e
# iner (aşağıya bkz.) ve eşiğin çok altında kalır.
#
# Çözüm eşiği düşürmek DEĞİLDİR -- eşik tam da tasarlandığı gibi çalışıyor ve
# "bilmiyorum" garantisi ona dayanıyor (bkz. MIN_SCORE yorumu; phi-4-mini
# cevaplanamaz soruların 3'ünü de bu yüzden kaybetti). Çözüm, bu sorgu sınıfını
# retrieval'a hiç göndermeden AYRI BİR YOLA yönlendirmektir (rag/query_router.py).

# Özetleme yolunda modele gönderilecek en fazla chunk sayısı. Belge boyunca
# EŞİT ARALIKLI örneklenir; ilk N chunk alınsa özet yalnızca belgenin başını
# görürdü. Üst sınır gerekli: 41 chunk'lık bir belgenin tamamı ~5300 kelime
# eder ve prefill zaten baskın olan gecikmeyi (bkz. PROJE_DURUMU) katlar.
SUMMARY_MAX_CHUNKS = 12

# ÖLÇÜLDÜ: diller arası ceza. Aynı içeriğin TR ve EN hali, TR içerik sorusuyla:
#   TR pasaj -> 0.766 | EN pasaj -> 0.690   (fark -0.077)
# MIN_SCORE yalnızca TR soru -> TR belge ile kalibre edildi (15 eval sorusunun
# tamamı öyle). Gerçek kullanımda teknik PDF'ler çoğunlukla İngilizce. Bu fark
# eşiği düşürerek değil, hibrit retrieval (BM25 + dense) ile telafi edilir --
# özel adlar ve teknik terimler dilden bağımsız olarak birebir eşleşir.

# DİKKAT: Bu metin hem system prompt'a gömülüdür hem de modelin reddettiğini
# ANLAMAK için kullanılır (rag/answer.py::is_refusal).
#
# ESKİDEN birebir alt dize eşleşmesiydi ve KIRILGANDI: ÖLÇÜLDÜ (eval/results.json,
# phi-4-mini Q13) -- model "Bu bilgi YÜKLENDİĞİNİZ belgelerde yok" yazdı
# (doğrusu "yüklediğiniz"), tek harflik çekim farkı tespiti kaçırdı ve
# arkasına uydurma içerik ekledi. Görev 4'te düzeltildi: is_refusal artık
# difflib.SequenceMatcher ile bulanık (fuzzy) eşleşme kullanıyor -- kalibrasyon
# ve eşik gerekçesi orada. qwen2.5-7b metni birebir ürettiği için bu sorun
# aktif modelde hiç görülmedi, ama başka bir modele geçilirse artık
# yeniden değerlendirmeye gerek yok; savunma zaten dayanıklı.
NO_ANSWER_TEXT = "Bu bilgi yüklediğiniz belgelerde yok."

# --- Studio artefaktları -----------------------------------------------------
#
# rag/artifacts/ (mind map, rapor, quiz) ve rag/topics.py (kümeleme) için.
# Faz 1'de yalnızca TOPIC_* ve FIDELITY_MIN_SCORE okunur; üç token bütçesi
# Faz 2-4'te tüketilir. Şimdiden yazılmalarının tek sebebi config'in tek
# seferde ve tek yerde büyümesi (CLAUDE.md §1.3).

# MAX_ANSWER_TOKENS = 220 sohbet cevabı için KASITLI ve doğru (bkz. o sabitin
# yorumu) -- rapor bölümü için yetersiz, düğüm etiketi için fazlasıyla geniş.
# Tek sabiti büyütmek sohbetin runaway kesicisini kaybettirirdi, bu yüzden üç
# ayrı bütçe var; her biri kendi artefaktının gerçek boyutuna göre seçildi:
ARTIFACT_SECTION_MAX_TOKENS = 700    # rapor bölümü: birkaç paragraf
ARTIFACT_LABEL_MAX_TOKENS = 40       # mind map düğüm etiketi: birkaç kelime
ARTIFACT_QUESTION_MAX_TOKENS = 200   # quiz sorusu + çeldiriciler

# rag/topics.py::cluster_corpus. 20-40 chunk'lık korpus ölçeğinde 2 doğru
# taban: tek chunk'lık bir "küme" bir konu değil, gürültüdür.
TOPIC_MIN_CLUSTER_SIZE = 2

# Üstü okunamaz bir harita üretir (mind map/quiz kapsamı için anlamsız kadar
# çok küme).
#
# UYARI: Bu korpusta (~17-20 chunk) TOPIC_MAX_CLUSTERS ile
# TOPIC_MIN_CLUSTER_SIZE AYNI ANDA sağlanamaz -- 12 küme x en az 2 chunk = en
# az 24 chunk gerekir. Çözüm bir eşiği değiştirmek değil, ÖNCELİK tanımlamak:
# TOPIC_MIN_CLUSTER_SIZE sert kısıt, TOPIC_MAX_CLUSTERS tavandır. Etkin küme
# sayısı rag/topics.py'de min(TOPIC_MAX_CLUSTERS, N // TOPIC_MIN_CLUSTER_SIZE)
# olarak hesaplanır.
TOPIC_MAX_CLUSTERS = 12

# rag/artifacts/fidelity.py::verdict_for. MIN_SCORE ile AYNI DEĞER, bilinçli:
# iki ayrı eşik iki ayrı kalibrasyon hikayesi demek olurdu -- bu projede
# eşiklerin hikayesi (MIN_SCORE'un 0.55'ten 0.45'e inişi, yukarı bkz.) değerin
# kendisi kadar önemli. Ayrılmaları ancak bir ÖLÇÜMLE gerekçelendirilebilir
# (CLAUDE.md §1.4); Faz 1'de böyle bir ölçüm yok.
FIDELITY_MIN_SCORE = 0.45

# 'weak' bandının genişliği: grounded ile unsupported arasındaki gri alan
# FIDELITY_MIN_SCORE - 0.10 ile FIDELITY_MIN_SCORE arasıdır.
#
# Başlangıçta fidelity.py içinde _WEAK_BAND_WIDTH olarak duruyordu; gerekçesi
# "FIDELITY_MIN_SCORE'a bağlı türev bir genişlik, tek tüketicisi verdict_for"
# idi. Buraya taşındı çünkü o gerekçe yanlıştı: bu 0.10 verdict SÖZLEŞMESİNİN
# parçası (docs/STUDIO_PLAN.md §2, docs/FEATURE_SPEC.md §9.6) ve 'weak' bandı
# kullanıcıya gösterilecek -- yani MIN_SCORE ile aynı sınıfta, bir uygulama
# detayı değil.
#
# REDDEDİLEN ALTERNATİF: sabiti yerinde bırakıp kalite-muhafizi'nin config
# merkeziliği taramasına "gerekçesi yorumda yazılı türetilmiş bant genişlikleri
# istisnadır" maddesi eklemek. Reddedildi: böyle bir muafiyeti yazarın kendisi
# onaylamış olur, modül içinde kalan her sabit yanına bir gerekçe yorumu alır
# ve tarama ayırt etme gücünü kaybeder. Bir bulguyu kaybetmek sorun değil,
# kuralı kaybetmek sorun (CLAUDE.md §1.3 kasıtlı olarak mutlaktır).
FIDELITY_WEAK_BAND_WIDTH = 0.10

# rag/artifacts/fidelity.py::unverified_terms -- Faz 2'nin ikinci katmanı
# (FEATURE_SPEC.md §10.6). Cosine "bu konuda bir chunk var mı" sorusunu
# cevaplıyor, özel adları/model kimliklerini (entailment boşluğu, bkz.
# FIDELITY_MIN_SCORE'un üstündeki 0.5487 tuzağı) kaçırıyor; bu iki sabit,
# sözcüksel doküman-frekansından türeyen İKİNCİ ve BAĞIMSIZ bir sinyal kurar.
# Ne biri ne öbürü FIDELITY_MIN_SCORE'u DEĞİŞTİRME gerekçesi değildir --
# tamamlayıcıdır (§9.6'da eşik yükseltme zaten reddedildi).
#
# ÖLÇÜLDÜ (eval.db: 20 chunk, rag.db: 61 chunk; model YÜKLEMEZ, saf metin
# taraması -- python -m pytest kadar ucuz):
#   (a) Tuzağın terimleri her iki korpusta da HİÇ geçmiyor (df=0, oran=0.000)
#       -- "gpt-4" ve "openai" (Türkçe-duyarlı küçültmeyle "openaı") ratio
#       eşiğinin her zaman altında, yani her zaman AYIRT EDİCİ sayılıyor.
#   (b) Korpustan birebir alınmış 399 cümle (eval.db 64 + rag.db 335), kendi
#       kaynak chunk'ı bağlam verildiğinde 0/399 toplu düşürüldü -- gerçek
#       içerik alt dize eşleşmesiyle her zaman kendi bağlamında bulunuyor.
#
# (b) ÖLÇÜMÜ YANILTICIYDI, KAYDA GEÇİRİLDİ (FEATURE_SPEC.md §10.6): birebir
# alınmış cümle kendi bağlamında HER ZAMAN bulunur; LLM nesri ise aynı bilgiyi
# BAŞKA sözcüklerle yazar. Gerçek üretilmiş raporda (eval.db, 47 cümle) yalnız
# df'ye bakan biçim 42 cümleyi düşürdü -- çünkü 20 chunk'lık korpusta sıradan
# Türkçe çekim de df=0 alıyor. Çözüm bu iki sabiti DEĞİŞTİRMEK olmadı (ikisi de
# ayrım üretmiyor, ölçüldü); kurala ikinci bir şart eklendi: terim ayrıca
# "varlık benzeri" olmalı (rakam/tire/nokta ya da cümle başı olmayan büyük
# harf). Aynı koşumda 43/47 cümle rapora girdi, tuzak yalnızca "gpt-4" ve
# "openaı" ile düştü. Bkz. fidelity.py::_entity_like.
FIDELITY_TERM_MIN_LENGTH = 4

# 2-3 harfli Türkçe bağlaçlar/ekler ("ve", "bu", "bir", "da", "de", "ile")
# hiçbir zaman ayırt edici bir sinyal taşımaz; MIN_LENGTH=4 bunları terim
# kontrolüne HİÇ sokmadan eler (df hesaplamasını gereksiz yere gürültüye
# maruz bırakmaz).
FIDELITY_TERM_DF_MAX_RATIO = 0.15

# ÖLÇÜLDÜ: 0.15'te en yaygın gerçek korpus terimleri kontrol dışı kalıyor --
# "rag" oran=0.50/0.51, "bir" oran=0.75/0.246, "ve" oran=0.65/0.23, "bu"
# oran=0.60/0.197 (eval.db/rag.db) hiçbiri "ayırt edici" sayılmıyor. Bilinen
# sınır: MIN_LENGTH>=4'ü aşan ama küçük korpusta seyrek geçen bazı gerçek
# bağlaçlar ("kadar", "olarak") yine de ayırt edici sayılabiliyor (rag.db'de
# sırasıyla oran=0.033/0.049) -- ama (b) ölçümünün 0/399 sonucu gösteriyor ki
# bu, gerçek/kendi bağlamına sahip içeriği toplu düşürmüyor; alt dize
# eşleşmesi kendi kaynağında her zaman buluyor.

# --- Studio Faz 3: Mind Map ---------------------------------------------------

# rag/artifacts/mindmap.py -- iki küme merkezi arasındaki HAM cosine bu değeri
# AŞIYORSA haritaya "ilişkili" kenarı çizilir (topics.topic_similarity).
#
# DİKKAT: bu MIN_SCORE DEĞİLDİR ve onunla aynı soruyu cevaplamaz. MIN_SCORE
# "bu chunk bu SORUYA cevap veriyor mu" eşiğidir; bu sabit "bu iki KONU
# birbirine yakın mı" eşiğidir. İkisini eşitlemek (0.45) haritayı okunmaz
# yapar -- ölçüm aşağıda.
#
# ÖLÇÜLDÜ (model YÜKLEMEZ: kayıtlı embedding'ler + rag/topics.py kümelemesi):
#   eval.db, 20 chunk ->  7 küme,  21 çift: min 0.2493 medyan 0.4366 max 0.6094
#   rag.db , 61 chunk -> 10 küme,  45 çift: min 0.2446 medyan 0.4707 max 0.7827
#
#   eşik   eval.db kenar (ort. derece)   rag.db kenar (ort. derece)
#   0.45   ~medyanın üstü: çiftlerin YARISI    ~çiftlerin yarısı   -> hairball
#   0.50    7/21 (2.0)                        20/45 (4.0)         -> hairball
#   0.55    2/21 (0.6)                        11/45 (2.2)         <- SEÇİLDİ
#   0.60    1/21 (0.3)                         8/45 (1.6)
#   0.65    0/21 (0.0)                         2/45 (0.4)
#
# 0.55 seçildi çünkü iki korpusun İKİSİNDE birden okunabilir kalıyor: büyük
# korpusta ortalama derece 2.2 (her düğümün birkaç komşusu var), küçük
# korpusta harita boşalmıyor ama yalnızca gerçekten yakın iki çift kalıyor
# (0.6094 RAG<->prompt engineering, 0.5520 prompt engineering<->chunking --
# ikisi de elle bakıldığında doğru "ilişkili" çiftler). 0.50'de rag.db'de 10
# düğüme 20 kenar düşüyor: her düğüm her düğüme bağlı görünür ve kenarın
# taşıdığı bilgi sıfırlanır. 0.65'te küçük korpus tamamen kenarsız kalır.
#
# Kenar yokluğu HATA DEĞİLDİR: kümeler gerçekten uzaksa harita yıldız
# (yalnızca kök-düğüm kenarları) olarak çizilir.
MINDMAP_EDGE_MIN_SIMILARITY = 0.55

# Küme etiketini yazan LLM çağrısına verilen chunk sayısı (merkeze en yakın
# ilk N). SUMMARY_MAX_CHUNKS (12) rapor BÖLÜMÜ içindir; <=5 kelimelik bir
# etiket için 12 chunk'lık bağlam yalnızca prefill maliyeti demektir (ölçüldü:
# gecikmenin baskın kaynağı prefill, bkz. MAX_ANSWER_TOKENS yorumu). 3, kümenin
# merkezini temsil etmeye yeter -- kümeler zaten tek konuya karşılık geliyor
# (eval.db'de 7 kümenin 7'si de tam olarak bir kaynak belge).
MINDMAP_LABEL_CONTEXT_CHUNKS = 3

# --- Studio Faz 4: Quiz -------------------------------------------------------

# Küme başına soru kotası. STUDIO_PLAN §6.3'ün "sorular tek chunk'a sıkışmasın"
# kuralı: kapsam kümeden gelir, sorular korpusa dağılır. 1 seçildi çünkü LLM
# çağrısı sayısı doğrudan gecikmedir (prefill baskın) ve 10 kümelik üretim
# korpusunda 10 soru zaten dolu bir quiz'dir.
QUIZ_QUESTIONS_PER_TOPIC = 1

# Üst sınır: korpus büyüyüp küme sayısı tavana dayasa bile quiz bir oturumda
# bitirilebilir kalmalı. TOPIC_MAX_CLUSTERS (12) x QUIZ_QUESTIONS_PER_TOPIC (1)
# ile aynı değer; ikisi ayrıldığında (kota 2 olursa) bu tavan bağlayıcı olur.
QUIZ_MAX_QUESTIONS = 12

# Çoktan seçmeli şık sayısı (1 doğru + 3 çeldirici). Çeldiriciler LLM'e
# uydurtulmaz, BAŞKA kümelerin doğru cevaplarından gelir (§12.5) -- yani havuz
# küme sayısıyla sınırlı. 4, 7 kümelik korpusta bile her soruya 3 çeldirici
# bulunabilmesini garanti eder (6 aday > 3 gerek).
QUIZ_CHOICE_COUNT = 4

