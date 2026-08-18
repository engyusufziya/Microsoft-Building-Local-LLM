# eval/baselines/

Bu dizin, `eval/run_eval.py` koşumlarının donmuş anlık görüntülerini tutar.

`eval/results.json` **CANLI** dosyadır: her koşum onun üzerine yazar, bir
öncekini yok eder. Bu yüzden `results.json` kendisi asla baseline sayılmaz —
bir sonraki koşum onu değiştirebilir.

Bir sonucu baseline olarak sabitlemek için, `eval/results.json`'ı bu dizine,
**alındığı commit'in kısa SHA'sı** dosya adıyla birebir kopyalarız (örn.
`0b67a00.json`). Kopya yeniden üretim değildir; mevcut `results.json`'ın
tam kopyasıdır.

Buradaki dosyalar asla üzerine yazılmaz veya elle düzenlenmez. Yeni bir
ölçüm, yeni bir SHA ile yeni bir dosya demektir. İki koşumu karşılaştırırken
hangi corpus fingerprint'i ve hangi embedding modeliyle alındıklarını da
belirtin — aksi halde karşılaştırma anlamsızdır.
