# Microsoft Foundry Local Nedir

Foundry Local, büyük dil modellerini bir kullanıcının kendi cihazında, tamamen
çevrimdışı olarak çalıştırmayı sağlayan hafif bir çalışma zamanı (runtime) ve SDK'dır.
Microsoft tarafından geliştirilmiştir.

Foundry Local'ın en önemli özelliği, model indirme ve yönetimini otomatik olarak
yapmasıdır. Geliştirici, hangi donanımın mevcut olduğunu elle kontrol etmek zorunda
değildir; Foundry Local, kullanılabilir donanımı (CPU, GPU veya NPU) otomatik olarak
tespit eder ve en uygun model sürümünü seçer.

Apple Silicon işlemcili Mac bilgisayarlarda Foundry Local, Metal aracılığıyla GPU
hızlandırması sunar. Bu, modelin CPU'ya göre önemli ölçüde daha hızlı çalışmasını
sağlar.

Foundry Local, bir model kataloğu sunar. Bu katalogda küçük modellerden (birkaç yüz
milyon parametre) büyük modellere (on milyar parametre üzeri) kadar farklı boyutlarda
seçenekler bulunur. Küçük modeller daha hızlı çalışır ama daha sınırlı bilgi
kapasitesine sahiptir; büyük modeller daha isabetli cevaplar üretir ama daha fazla
bellek ve işlem gücü gerektirir.

Foundry Local, hem sohbet (chat) modellerini hem de embedding modellerini
destekler, bu da onu yerel bir RAG sisteminin her iki bileşeni için de uygun hale
getirir.
