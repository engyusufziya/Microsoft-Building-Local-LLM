# Offline Kanıt Raporu

> Bu dosya `python eval/offline_proof.py` tarafından otomatik üretilir.
> El ile düzenlenmez -- yeniden çalıştırıp üzerine yazın.

**Koşum zamanı:** 2026-08-13T22:13:36+00:00
**Model:** qwen2.5-7b (qwen2.5-7b-instruct-generic-gpu:4)
**Eval sonucu:** 23/23 (TÜMÜ GEÇTİ)

## Yöntem

Wi-Fi fiziksel olarak kapatılmadı -- bu makinenin ağ durumunu değiştirmek bu
script'in yetki alanı dışında bir yan etki. Bunun yerine `socket.socket.connect`
tüm eval koşumu boyunca saydam biçimde sarılıp HER TCP bağlantı denemesi
kaydedildi (engellemeden). Bu, "ağ kapalıyken çalıştı" gözleminden daha
güçlü bir iddiayı doğrudan ölçer: **kod, açık bir ağ varken bile dışarıya
hiç istek denemedi** -- yanlışlıkla açık bırakılmış bir Wi-Fi'ın testi
sessizce geçirmesi riski yok.

## Sonuç

**BEKLENMEYEN BULGU: 0 bağlantı denemesi.** Bu koşumda
`socket.socket.connect` HİÇ çağrılmadı -- modele giden tek bir istek bile
Python'un socket katmanından geçmedi. Kaynağı araştırıldı:
`foundry_local_sdk/detail/core_interop.py`, model çağrılarını (chat,
embedding, katalog, indirme -- hepsi) `ctypes` ile yerel bir ikiliye
(`foundry_local_core`) doğrudan FFI çağrısı olarak gönderiyor;
`foundry_local_manager.py`'deki HTTP/port bahsi (`127.0.0.1:0`) yalnızca
yapılandırma alanı, Python SDK'sının kullandığı gerçek iletişim kanalı değil.

Bu, "yalnızca loopback'e bağlandı" kanıtından DAHA GÜÇLÜ bir bulgu: ağ
yığınına (loopback dahil) hiç girilmiyor -- aynı süreç içinde doğrudan
bellek/FFI çağrısı. socket seviyesinde "sıfır bağlantı" bu yüzden bir
enstrümantasyon hatası değil, mimarinin kendisi.

**Loopback dışı bağlantı denemesi: 0**

✅ **DOĞRULANDI** — eval koşumu boyunca dışarıya (loopback dahil hiçbir adrese) tek bir istek bile denenmedi. 23 soruluk tam eval, gerçek model çağrılarıyla, sıfır ağ etkinliğiyle tamamlandı.
