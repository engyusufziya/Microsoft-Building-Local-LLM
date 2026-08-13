# Belge Parçalama (Chunking) Stratejisi

RAG sistemlerinde belgeler, doğrudan tam haliyle kullanılmaz; daha küçük parçalara
(chunk) bölünür. Bu bölme işlemi, retrieval kalitesini doğrudan etkileyen kritik bir
tasarım kararıdır.

Çok küçük parçalar (örneğin tek bir cümle) kullanıldığında, bağlam eksik kalabilir;
model, cümlenin ait olduğu daha geniş konuyu göremez. Çok büyük parçalar (örneğin
tüm bir belge) kullanıldığında ise alakasız metin, retrieval sonucunu kirletir ve
modelin dikkatini dağıtır.

Yaygın bir yaklaşım, belgeleri paragraf sınırlarında bölmek ve her parçayı yaklaşık
iki yüz ila dört yüz kelime uzunluğunda tutmaktır. Parçalar arasında bir paragraflık
bir örtüşme (overlap) bırakmak, bir cümlenin iki parça arasında bölünüp bağlamını
kaybetmesini önler.

Chunking stratejisi, kullanılan embedding modelinin ve dil modelinin kapasitesine
göre ayarlanmalıdır. Küçük dil modelleri, daha az sayıda ve daha kısa parçayla daha
iyi sonuç verir; çünkü sınırlı bağlam penceresini gereksiz bilgiyle doldurmamış olur.
