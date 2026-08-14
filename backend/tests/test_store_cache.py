"""rag/store.py `_matrix_cache`: kapanan bir bağlantının önbellek girdisi
yeni açılan bir bağlantıya sızıyor mu?

Kök neden: `:memory:` bağlantılar için önbellek anahtarı `id(conn)`'e
dayanıyordu (`memory:{id(conn)}`, bkz. store.connect) ve `close()` bu anahtarı
HİÇ düşürmüyordu (`_matrix_cache` yalnızca yazma işlemlerinde veya
clear_cache() ile geçersiz kılınıyordu). CPython serbest kalan bir nesnenin
bellek adresini hemen yeniden kullanabildiği için, kapanmış bir bağlantının
bayat matrisi yeni açılan (ve içeriği tamamen farklı) bir bağlantıya
çarpabiliyordu -- ~29 tam test koşumunda 1 kez üretildi: boş beklenirken
(5, 2) boyutlu bir matris sızdı.

id() yeniden kullanımı olasılıksal olduğu için testi buna bırakmıyoruz: iki
ayrı bağlantıya BİLEREK aynı cache_key'i atayarak çakışmayı deterministik
olarak kuruyoruz. Bu, id() yeniden kullanımının üreteceği durumla BİREBİR
aynı sonucu doğurur (aynı anahtar, önbellekte hâlâ duran bayat girdi), ama
GC davranışına bağlı değildir.
"""

from __future__ import annotations

from rag import store


class _Chunk:
    def __init__(self, content, source="a.md", page=1):
        self.content, self.source, self.page, self.via_ocr = content, source, page, False


def test_kapanan_baglanti_onbellegi_gecersiz_kilar():
    store.clear_cache()

    conn1 = store.connect(":memory:")
    store.upsert_document(conn1, "a.md", 1, [_Chunk("merhaba dünya")], [[1.0, 0.0]])
    matrix1, _ = store.load_matrix(conn1)
    assert matrix1.shape == (1, 2)

    # id() yeniden kullanımını deterministik olarak simüle et: conn1 kapanmadan
    # önce anahtarını al, kapat, sonra YENİ ve BOŞ bir bağlantıya aynı anahtarı
    # bilerek ata -- CPython'un id(conn2) == id(conn1) üretmesiyle aynı etki.
    collision_key = conn1.cache_key
    conn1.close()

    conn2 = store.connect(":memory:")
    conn2.cache_key = collision_key

    matrix2, meta2 = store.load_matrix(conn2)

    assert matrix2.shape == (0, 0), (
        "conn2 boş bir veritabanı ama kapanan conn1'in önbellek girdisi "
        f"sızdı: shape={matrix2.shape}"
    )
    assert meta2 == []
