# Prompt Engineering Temelleri

Prompt engineering, bir dil modeline verilen talimatların, istenen davranışı elde
etmek için dikkatlice tasarlanması sürecidir. Bir sohbet modeline gönderilen mesajlar
genellikle iki rolden oluşur: sistem mesajı ve kullanıcı mesajı.

Sistem mesajı, modelin genel davranışını belirler. Örneğin bir RAG uygulamasında
sistem mesajı şöyle olabilir: "Sadece verilen bağlamı kullanarak cevap ver, bağlam
dışında bilgi ekleme, bilgi yoksa bilmediğini söyle." Bu talimat, modelin kendi
eğitim belleğinden uydurma yapmasını önler.

Kullanıcı mesajı, kullanıcının gerçek sorusunu içerir.

RAG sistemlerinde prompt engineering'in en önemli görevi, modeli verilen bağlama
sadık tutmaktır. Ayrıca üretim uzunluğunu sınırlamak (örneğin en fazla üç cümle
istemek) modelin konudan sapmasını veya aynı ifadeleri tekrar etmesini önlemeye
yardımcı olur.

İyi tasarlanmış bir sistem mesajı, aynı model ile çok farklı kalitede cevaplar
arasındaki farkı yaratabilir. Bu nedenle prompt engineering, model seçimi kadar
önemli bir mühendislik kararıdır.
