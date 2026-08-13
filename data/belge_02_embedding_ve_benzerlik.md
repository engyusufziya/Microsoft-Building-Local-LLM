# Embedding ve Vektör Benzerliği

Embedding, bir metnin anlamını sayısal bir vektöre çeviren bir tekniktir. Her kelime,
cümle veya belge parçası, sabit boyutlu bir sayı dizisine dönüştürülür. Bu dönüşüm,
metnin yüzeysel harflerini değil, anlamsal içeriğini yakalar.

Benzer anlama gelen metinler, embedding uzayında birbirine yakın vektörler üretir.
Örneğin "araba" ve "otomobil" kelimelerinin vektörleri birbirine yakın çıkar, çünkü
anlamları benzerdir; "araba" ve "elma" vektörleri ise birbirinden uzak çıkar.

Bu vektörler arasındaki benzerliği ölçmek için en yaygın yöntem cosine similarity'dir.
Cosine similarity, iki vektör arasındaki açıyı ölçer, vektörlerin büyüklüğünü değil.
Bu sayede, bir metin daha uzun olsa bile anlamca aynıysa yüksek benzerlik skoru alır.
Cosine similarity değeri 1'e yaklaştıkça benzerlik artar, 0'a yaklaştıkça benzerlik
azalır.

RAG sistemlerinde embedding, retrieval adımının temelidir: kullanıcının sorusu da bir
vektöre çevrilir ve belge veritabanındaki vektörlerle karşılaştırılarak en benzer
metin parçaları bulunur.
