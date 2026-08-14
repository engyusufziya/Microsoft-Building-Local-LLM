"""rag/answer.py::is_refusal -- Görev 4: NO_ANSWER_TEXT tespitindeki kırılganlığın giderilmesi.

ÖLÇÜLDÜ (eval/results.json, phi-4-mini Q13): eski birebir alt dize eşleşmesi
model "Bu bilgi YÜKLENDİĞİNİZ belgelerde yok" yazınca (doğrusu
"yüklediğiniz") tespiti kaçırdı -- 2. katman savunma (config.py docstring'i,
"halüsinasyona karşı iki katmanlı savunma") sessizce devre dışı kaldı ve
model arkasına uydurma içerik ekledi.
"""

from __future__ import annotations

import pytest

from rag import answer, config


# --------------------------------------------------------------------------- gerçek reddetme varyantları (True olmalı)


@pytest.mark.parametrize(
    "text",
    [
        "Bu bilgi yüklediğiniz belgelerde yok.",
        "Bu bilgi yüklediğiniz belgelerde yok",  # noktasız
        "bu bilgi yüklediğiniz belgelerde yok.",  # küçük harf
        "Bu bilgi YÜKLENDİĞİNİZ belgelerde yok.",  # ÖLÇÜLEN gerçek hata (phi-4-mini Q13)
        "Bu bilgi  yüklediğiniz belgelerde yok .",  # fazla boşluk
        '"Bu bilgi yüklediğiniz belgelerde yok."',  # tırnak eklenmiş
        "Üzgünüm, bu bilgi yüklediğiniz belgelerde yok, başka bir soru sorabilir misiniz?",
    ],
)
def test_gercek_reddetme_varyantlari_yakalanir(text):
    assert answer.is_refusal(text) is True


# --------------------------------------------------------------------------- alakasız cevaplar (False olmalı -- yanlış pozitif riski)


@pytest.mark.parametrize(
    "text",
    [
        "RAG üç adımdan oluşur: retrieval, augmentation, generation.",
        "SQLite, sunucusuz ve kendi kendine yeten bir SQL veritabanı motorudur.",
        "Cosine similarity iki vektör arasındaki açıyı ölçer; büyüklüğü değil.",
        "Chunklar arasında örtüşme yoksa bağlam kaybolur.",
        "Bu özellik yüklü belgelerde henüz test edilmedi.",
        "Yüklediğiniz belgede böyle bir bilgi bulunmuyor ama benzer bir konu var.",
        # kasıtlı olarak zor: hedef kelimelerin çoğunu paylaşıyor ama farklı bir iddia
        "Bu bilgi tüm belgelerde ortak olarak yok sayılan bir varsayımdır.",
        "",
        # ÖLÇÜLDÜ (eval Q04, SYSTEM_PROMPT gevşetildikten sonraki regresyon):
        # "sum of ALL matching blocks" metriği bu tamamen doğru, alakalı
        # cevabı YANLIŞ POZİTİF reddetme olarak işaretlemişti -- Türkçe'de
        # "belge"/"bilgi" gibi ortak alt diziler uzun bir metinde dağınık
        # onlarca küçük parça olarak birikip hedefin uzunluğunu aşabiliyordu.
        '"Araba" ve "otomobil" kelimelerinin vektörleri birbirine yakın çıkar, '
        "çünkü bu kelimeler anlamlı olarak benzerdir ve embedding işlemi "
        "metinlerin anlamlı içeriğini vektör formuna dönüştürdüğü için böyle "
        "bir yakınlık ortaya çıkar. Bu özellik, RAG'de belge veritabanında "
        "arama aşamasında kullanılabilecek anlamlı benzerliklerin tespiti ve "
        "belgenin daha doğru ve kapsamlı bir yanıt sağlamasına yardımcı "
        "olabilir. Örneğin, bir kullanıcı araba kelimesini kullanırsa, "
        "embedding uzayında otomobil kelimesine yakın olan vektörleri "
        "bulabilir.",
        # Aynı desende, gerçekçi uzunlukta başka bir alakalı cevap.
        "Foundry Local'ın en önemli özelliği, kullanılabilir donanımı (CPU, "
        "GPU veya NPU) otomatik olarak tespit edip en uygun model sürümünü "
        "seçmesidir. Apple Silicon işlemcili Mac bilgisayarlarda Metal "
        "aracılığıyla GPU hızlandırması sunar. Hem sohbet hem embedding "
        "modellerini desteklediği için yerel bir RAG sisteminin her iki "
        "bileşeni için de uygundur.",
    ],
)
def test_alakasiz_cevaplar_reddetme_sayilmaz(text):
    assert answer.is_refusal(text) is False


def test_esik_gercek_ve_alakasiz_arasindaki_bosluga_yerlesir():
    """Kalibrasyon notu (rag/answer.py::_REFUSAL_MATCH_THRESHOLD) ile aynı
    ölçümü doğrular: gerçek varyantlar >=0.80, en zor alakasız örnek <0.80.
    """
    assert config.NO_ANSWER_TEXT == "Bu bilgi yüklediğiniz belgelerde yok."
    assert answer._REFUSAL_MATCH_THRESHOLD == pytest.approx(0.80)


def test_eval_harness_ayni_fonksiyonu_kullanir():
    """eval/run_eval.py::refused artık answer.is_refusal'a delege ediyor --
    iki farklı reddetme tanımı sürüklenip production ile eval'in farklı
    şeyleri ölçmesi riski (bu görevin regresyon senaryosu) burada kapanır.
    """
    import importlib
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
    run_eval = importlib.import_module("run_eval")
    assert run_eval.refused is not answer.is_refusal  # sarmalayıcı, aynı obje değil
    assert run_eval.refused("Bu bilgi YÜKLENDİĞİNİZ belgelerde yok.") is True
    assert run_eval.refused("RAG üç adımdan oluşur.") is False
