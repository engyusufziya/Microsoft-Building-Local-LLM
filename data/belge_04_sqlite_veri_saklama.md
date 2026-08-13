# SQLite ile Yerel Veri Saklama

SQLite, sunucusuz ve kendi kendine yeten bir SQL veritabanı motorudur. Tüm veritabanı,
tek bir dosyada saklanır; ayrı bir veritabanı sunucusu kurmaya gerek yoktur.

SQLite'ın avantajları arasında kurulumsuz çalışması, platformlar arası uyumluluğu ve
basit entegrasyonu sayılabilir. Bu özellikler, onu yerel bir RAG uygulaması için
uygun bir seçim yapar: internet bağlantısı veya harici bir sunucu gerektirmez.

Bir RAG sisteminde SQLite, genellikle şu şekilde kullanılır: belge parçaları (chunk)
ve bu parçalara ait embedding vektörleri, bir tabloda saklanır. Her satır bir
belge parçasını temsil eder ve şu alanları içerebilir: benzersiz bir kimlik (id),
kaynak belgenin adı (source), metnin kendisi (content) ve metnin embedding vektörü.

Embedding vektörleri sayısal listeler olduğu için, SQLite'a doğrudan yazılamazlar.
Bunun için vektör, JSON formatında bir metne çevrilerek saklanır; okunurken tekrar
sayısal listeye dönüştürülür.

Küçük ölçekli projelerde, tüm embedding vektörleri belleğe okunup sorgu vektörüyle
karşılaştırılabilir. Çok büyük belge koleksiyonlarında ise özel vektör veritabanları
veya SQL uzantıları daha uygun olur.
