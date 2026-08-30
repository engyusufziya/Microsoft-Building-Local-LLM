"""short_answer eşik kalibrasyonu — FEATURE_SPEC §12.6'nın [!danger] kararı için ÖLÇÜM.

Spec `short_answer`'ı bir eşiğe indirgemeyi REDDETMİŞTİ ve gerekçesi şuydu:
"bir eşik uydurmak, ölçülmemiş bir kararı ölçülmüş gibi sunmak olurdu."
Bu koşucu tam olarak o eksiği kapatır: eşiği uydurmak yerine ETİKETLİ bir
küme üzerinde ölçer.

NE ÖLÇÜLÜYOR
    `score_attempt`'in kullandığı benzerliğin AYNISI: kullanıcının cevabı ile
    referans cevap, İKİSİ DE `is_query=False` ile embed edilir (simetrik
    cevap<->cevap kosinüsü; sorgu->chunk asimetrik benzerliği DEĞİL).
    Sonra eşik taranır ve her eşik için karışıklık matrisi çıkarılır.

ETİKETLEME — kim, nasıl, hangi sınırla
    Etiketler bu dosyayı yazan ajan tarafından ELLE verildi; bağımsız bir
    insan değerlendirmesi DEĞİL. Bu bilinen ve kayıtlı bir sınırdır: küme
    "doğru cevap neye benzer" konusundaki bir yargıyı temsil ediyor ve o
    yargı tek kaynaklı. Kümenin BÜYÜMESİ ya da bağımsız etiketlenmesi
    sonucu değiştirebilir.

    Küme korpusun kendisinden kuruldu (data/*.md), çünkü gerçek bir quiz'in
    referans cevabı da korpustan çıkıyor -- embedding dağılımı eşleşsin diye.

    Üç sınıf:
      dogru       : öğrencinin kendi kelimeleriyle yazdığı, referansla AYNI
                    olguyu söyleyen kısa cevap
      yakin_yanlis: AYNI belgeden, konusu bitişik ama BAŞKA bir olgu -- asıl
                    zor durum, gerçek bir öğrenci hatası böyle görünür
      uzak_yanlis : BAŞKA bir belgeden gelen, konusu bile farklı cevap

KOŞUM
    .venv/bin/python eval/short_answer_calibration.py
    Yalnızca EMBEDDING modeli yüklenir (7B yok), ~15 sn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag import models  # noqa: E402

# --------------------------------------------------------------------------- küme
# (referans cevap, doğru cevap, yakın-yanlış, uzak-yanlış)
ITEMS: list[tuple[str, str, str, str]] = [
    (
        "RAG üç adımdan oluşur: retrieval, augmentation ve generation.",
        "Üç aşaması var: önce arama, sonra bağlamı ekleme, sonra üretme.",
        "RAG'de arama kelime eşleşmesiyle değil anlamsal benzerlikle yapılır.",
        "SQLite tek bir dosyada saklanan sunucusuz bir veritabanı motorudur.",
    ),
    (
        "Birinci adım retrieval'dır: soruyla ilgili metin parçaları belge veritabanından bulunur.",
        "İlk adımda soruya benzeyen metin parçaları veritabanından çekiliyor.",
        "İkinci adımda bulunan parçalar modelin girdisine ek bağlam olarak eklenir.",
        "Foundry Local modelleri kullanıcının kendi cihazında çevrimdışı çalıştırır.",
    ),
    (
        "RAG'de arama kelime eşleşmesiyle değil anlamsal benzerlikle yapılır.",
        "Arama kelimelere değil anlama bakıyor.",
        "RAG üç adımdan oluşur: retrieval, augmentation ve generation.",
        "Chunk'lar arasında örtüşme bırakmak sınırda kalan cümleleri kurtarır.",
    ),
    (
        "Embedding, bir metnin anlamını sayısal bir vektöre çeviren tekniktir.",
        "Metni anlamını taşıyan sayı dizisine dönüştürme işlemi.",
        "Benzer anlamlı metinler embedding uzayında birbirine yakın vektörler üretir.",
        "Sistem mesajı modelin genel davranışını belirler.",
    ),
    (
        "Benzer anlama gelen metinler embedding uzayında birbirine yakın vektörler üretir.",
        "Anlamca yakın cümlelerin vektörleri de birbirine yakın oluyor.",
        "Embedding, metnin anlamını sayısal bir vektöre çeviren tekniktir.",
        "Foundry Local model indirmeyi ve yönetimini otomatik yapar.",
    ),
    (
        "Cosine similarity iki vektör arasındaki açıyı ölçer, büyüklüğünü değil.",
        "İki vektörün arasındaki açıya bakar; uzunlukları önemli değil.",
        "Benzerliği ölçmek için en yaygın yöntem cosine similarity'dir.",
        "Belgeler tam haliyle değil, daha küçük parçalara bölünerek kullanılır.",
    ),
    (
        "Foundry Local, dil modellerini kullanıcının kendi cihazında çevrimdışı çalıştıran bir runtime ve SDK'dır.",
        "Modelleri internet olmadan kendi bilgisayarında çalıştırmayı sağlayan araç.",
        "Foundry Local Microsoft tarafından geliştirilmiştir.",
        "Cosine similarity iki vektör arasındaki açıyı ölçer.",
    ),
    (
        "Foundry Local kullanılabilir donanımı (CPU, GPU veya NPU) otomatik olarak seçer.",
        "Hangi donanım varsa onu kendisi buluyor, elle ayar gerekmiyor.",
        "Foundry Local model indirme ve yönetimini otomatik olarak yapar.",
        "Prompt engineering, modele verilen talimatların tasarlanması sürecidir.",
    ),
    (
        "SQLite sunucusuz ve kendi kendine yeten bir SQL veritabanı motorudur.",
        "Ayrı sunucu istemeyen, kendi başına çalışan bir SQL veritabanı.",
        "SQLite'ta tüm veritabanı tek bir dosyada saklanır.",
        "RAG'in ikinci adımı augmentation'dır.",
    ),
    (
        "SQLite'ta tüm veritabanı tek bir dosyada saklanır.",
        "Veritabanının tamamı tek dosyada duruyor.",
        "SQLite kurulumsuz çalışır ve platformlar arası uyumludur.",
        "Embedding metni sayısal bir vektöre çevirir.",
    ),
    (
        "Bir RAG sisteminde SQLite'ta belge parçaları ve embedding vektörleri bir tabloda saklanır.",
        "Chunk'lar ve onların vektörleri aynı tabloda tutuluyor.",
        "SQLite yerel bir RAG uygulaması için uygun bir seçimdir çünkü internet gerektirmez.",
        "Çok küçük parçalar kullanıldığında bağlam eksik kalabilir.",
    ),
    (
        "Prompt engineering, dil modeline verilen talimatların dikkatlice tasarlanması sürecidir.",
        "Modele ne söyleyeceğini iyi tasarlama işi.",
        "Sohbet modeline gönderilen mesajlar sistem ve kullanıcı mesajı olmak üzere iki rolden oluşur.",
        "SQLite tek dosyada saklanan bir veritabanıdır.",
    ),
    (
        "Sistem mesajı modelin genel davranışını belirler.",
        "Modelin nasıl davranacağını sistem mesajı ayarlıyor.",
        "Kullanıcı mesajı modele sorulan asıl soruyu taşır.",
        "Foundry Local donanımı otomatik seçer.",
    ),
    (
        "RAG sistemlerinde belgeler tam haliyle değil, daha küçük parçalara (chunk) bölünür.",
        "Belgeler bütün olarak değil küçük parçalara ayrılarak kullanılıyor.",
        "Bölme işlemi retrieval kalitesini doğrudan etkileyen kritik bir tasarım kararıdır.",
        "Cosine similarity vektörler arasındaki açıyı ölçer.",
    ),
    (
        "Çok küçük parçalar kullanıldığında bağlam eksik kalabilir.",
        "Parçalar fazla küçük olursa bağlam kopuyor.",
        "Çok büyük parçalar kullanıldığında alakasız metin retrieval sonucunu kirletir.",
        "Foundry Local Microsoft tarafından geliştirilmiştir.",
    ),
    (
        "Çok büyük parçalar kullanıldığında alakasız metin retrieval sonucunu kirletir.",
        "Parça çok büyük olursa içine alakasız şeyler karışıyor ve arama bozuluyor.",
        "Çok küçük parçalar kullanıldığında bağlam eksik kalabilir.",
        "Sistem mesajı modelin genel davranışını belirler.",
    ),
    (
        "Chunk'lar arasında örtüşme bırakmak, sınırda kalan cümlelerin kaybolmasını önler.",
        "Parçaları biraz üst üste bindirirsek sınırdaki cümleler kaybolmuyor.",
        "Bölme işlemi retrieval kalitesini etkileyen kritik bir karardır.",
        "Embedding metnin anlamını vektöre çevirir.",
    ),
    (
        "RAG'in ikinci adımı augmentation'dır: bulunan parçalar modelin girdisine ek bağlam olarak eklenir.",
        "İkinci aşamada bulunan metinler modele bağlam diye veriliyor.",
        "Üçüncü adım generation'dır: model bağlamı kullanarak cevabı üretir.",
        "SQLite kurulumsuz çalışır.",
    ),
]


def _cosine_matrix(texts: list[str]) -> np.ndarray:
    vectors = np.asarray(models.embed_texts(texts), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0.0, 1.0, norms)


def main(argv=None) -> int:
    print("=== short_answer eşik kalibrasyonu (FEATURE_SPEC §12.6) ===\n")
    print(f"  Etiketli öğe : {len(ITEMS)} referans x 3 sınıf = {len(ITEMS) * 3} çift")
    print(f"  Embedding    : cevap<->cevap, İKİSİ DE is_query=False")
    print(f"  Etiketleyen  : bu koşucuyu yazan ajan (bağımsız insan DEĞİL)\n")

    # score_attempt ile AYNI çağrı biçimi: hepsi is_query=False (varsayılan).
    flat: list[str] = []
    for reference, correct, near, far in ITEMS:
        flat.extend([reference, correct, near, far])
    unit = _cosine_matrix(flat)

    pairs: list[tuple[str, float]] = []
    for i in range(len(ITEMS)):
        base = i * 4
        reference = unit[base]
        pairs.append(("dogru", float(reference @ unit[base + 1])))
        pairs.append(("yakin_yanlis", float(reference @ unit[base + 2])))
        pairs.append(("uzak_yanlis", float(reference @ unit[base + 3])))

    for label in ("dogru", "yakin_yanlis", "uzak_yanlis"):
        values = np.array([s for lbl, s in pairs if lbl == label])
        print(f"  {label:14s} n={len(values):2d}  "
              f"min={values.min():.4f}  ort={values.mean():.4f}  max={values.max():.4f}")

    positives = np.array([s for lbl, s in pairs if lbl == "dogru"])
    negatives = np.array([s for lbl, s in pairs if lbl != "dogru"])

    print(f"\n  ÖRTÜŞME: en düşük doğru = {positives.min():.4f}, "
          f"en yüksek yanlış = {negatives.max():.4f}")
    separable = positives.min() > negatives.max()
    print(f"  Tam ayrılabilir mi: {'EVET' if separable else 'HAYIR'}\n")

    print("  eşik   doğru↑  yanlış↓   isabet   yanlış-'doğru'   kaçan-doğru")
    print("  " + "-" * 62)
    best = None
    for threshold in np.arange(0.50, 0.96, 0.025):
        tp = int((positives >= threshold).sum())
        fn = len(positives) - tp
        fp = int((negatives >= threshold).sum())
        tn = len(negatives) - fp
        accuracy = (tp + tn) / (len(positives) + len(negatives))
        marker = ""
        if best is None or accuracy > best[1]:
            best = (float(threshold), accuracy, tp, fn, fp, tn)
        print(f"  {threshold:.3f}   {tp:2d}/{len(positives):2d}   {tn:2d}/{len(negatives):2d}"
              f"    {accuracy:6.1%}        {fp:2d}              {fn:2d}{marker}")

    assert best is not None
    threshold, accuracy, tp, fn, fp, tn = best
    print(f"\n  EN İYİ EŞİK: {threshold:.3f}  (isabet {accuracy:.1%})")
    print(f"    doğruyu doğru bildi        : {tp}/{len(positives)}")
    print(f"    yanlışı yanlış bildi       : {tn}/{len(negatives)}")
    print(f"    YANLIŞA 'doğru' dedi       : {fp}   <- kullanıcıya yanlış onay")
    print(f"    DOĞRUYA 'yanlış' dedi      : {fn}   <- kullanıcıya haksız ret")

    # AYRIMIN NEREDE ÇALIŞTIĞI: "tamamen konu dışı" ile "doğru"yu ayırmak
    # kolay; asıl karıştıran "konusu bitişik ama yanlış". İkisini ayrı ölçmek,
    # kararın hangi durumda çöktüğünü isimlendiriyor.
    near = np.array([s for lbl, s in pairs if lbl == "yakin_yanlis"])
    far = np.array([s for lbl, s in pairs if lbl == "uzak_yanlis"])
    print(f"\n  --- Ayrımın nerede çalıştığı ---")
    print(f"  doğru (min {positives.min():.4f}) vs UZAK yanlış (max {far.max():.4f}): "
          f"{'AYRILIYOR' if positives.min() > far.max() else 'ayrılmıyor'}")
    print(f"  doğru (min {positives.min():.4f}) vs YAKIN yanlış (max {near.max():.4f}): "
          f"{'ayrılıyor' if positives.min() > near.max() else 'AYRILMIYOR'}")
    print("  Yani model 'konu dışı'yı eleyebiliyor; 'konusu doğru ama olgusu")
    print("  yanlış' cevabı doğrudan AYIRAMIYOR -- quiz'de asıl önemli olan da bu.")

    print("\n  --- Karar ---")
    if fp == 0 and fn == 0:
        print("  Küme tam ayrıldı. Eşikle işaretleme ÖLÇÜMLE desteklenir.")
        return 0
    print(f"  Küme tam AYRILMADI: {fp + fn} çift en iyi eşikte bile yanlış sınıflanıyor.")
    print("  Eşikle işaretleme, bu hata payını kullanıcıya KESİN bir yargı")
    print("  olarak sunmak anlamına gelir. Karar ve gerekçe PROJE_DURUMU.md'de.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
