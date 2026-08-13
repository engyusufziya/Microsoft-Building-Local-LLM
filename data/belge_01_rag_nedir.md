# RAG (Retrieval-Augmented Generation) Nedir

Retrieval-Augmented Generation (RAG), bir dil modelinin cevap üretmeden önce ilgili
belgeleri aramasını ve bulduğu bilgiyi cevaba dahil etmesini sağlayan bir yöntemdir.
Üç adımdan oluşur.

Birinci adım retrieval'dır: kullanıcının sorusuyla ilgili metin parçaları, önceden
hazırlanmış bir belge veritabanından bulunur. Bu arama, kelime eşleşmesiyle değil,
anlamsal benzerlikle yapılır.

İkinci adım augmentation'dır: bulunan metin parçaları, modelin girdisine ek bağlam
olarak eklenir. Model artık soruyu tek başına değil, bu bağlamla birlikte görür.

Üçüncü adım generation'dır: model, verilen bağlamı kullanarak bir cevap üretir.

RAG'in temel faydası, modelin kendi eğitim belleğinden tahmin yürütmek zorunda
kalmadan, doğrudan verilen kaynaktan cevap vermesidir. Bu, halüsinasyon riskini
azaltır ve cevapların kaynak gösterilebilir olmasını sağlar. RAG, modeli yeniden
eğitmeden güncel veya özel veriyle çalışmasını sağlayan pratik bir yöntemdir.
