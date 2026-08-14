"""Sorgu sınıfı yönlendirme (rag/query_router.py) + özetleme/korpus yolları.

Bu testlerin varlık sebebi ölçülmüş bir üretim hatasıdır: "İlgili dökümanı bana
özetle" sorgusu 0.28-0.30 skor alıp eşiğin (0.45) altında kaldı ve sistem
"bilgi belgelerde yok" dedi -- oysa belge yüklüydü. Kök neden meta sorgunun
hiçbir içerik terimi taşımaması; eşik değil.

En kritik iki test:
  - test_icerik_sorulari_search_yolunda_kalir  -> yönlendirme mevcut davranışı
    BOZMUYOR (eval setinin 15 sorusu buradan geçiyor).
  - test_esik_dusurulmedi                      -> hata "eşiği düşür" ile
    çözülmedi; "bilmiyorum" garantisi yerinde.
"""

from __future__ import annotations

import sqlite3

import pytest

from rag import config, query_router, store


# --------------------------------------------------------------------------- sınıflandırma


@pytest.mark.parametrize(
    "query",
    [
        "İlgili dökümanı bana özetle",          # üretimde çöken sorgu
        "ilgili dokumani bana ozetle",          # aksansız yazım
        "Bu belgeyi özetler misin?",
        "Dosyanın içeriği ne hakkında?",
        "Bu PDF ne anlatıyor?",
        "summarize this document",
        "give me an overview of the file",
        "Özetle",                               # kısa sorgu, gönderge yok
        "Kısaca özetle",
    ],
)
def test_meta_sorgular_summarize_yoluna_gider(query):
    assert query_router.classify(query).kind == "summarize"


@pytest.mark.parametrize(
    "query",
    [
        "Kaç belge yükledim?",
        "kac dokuman var",
        "Hangi belgeler yüklü?",
        "how many documents do I have",
        "which documents are loaded",
    ],
)
def test_korpus_sorulari_corpus_yoluna_gider(query):
    assert query_router.classify(query).kind == "corpus"


@pytest.mark.parametrize(
    "query",
    [
        "RAG kaç adımdan oluşur ve bu adımlar nelerdir?",
        "Cosine similarity tam olarak neyi ölçer?",
        "Foundry Local hangi donanımları kullanabilir?",
        "Pencere boyu ve örtüşme kaç kelimedir?",
        "İstanbul'un nüfusu kaçtır?",           # konu dışı ama yine içerik sorusu
        "Chroma ve FAISS'ten hangisi daha hızlıdır?",
    ],
)
def test_icerik_sorulari_search_yolunda_kalir(query):
    """Yönlendirme mevcut davranışı GENİŞLETİR, daraltmaz.

    Eval setinin soruları bu yoldan geçiyor; buradaki bir regresyon 15/15
    sonucunu sessizce bozardı.
    """
    assert query_router.classify(query).kind == "search"


def test_ozetleme_fiili_korpus_desenini_ezer():
    """Regresyon: eval/eval_set.json Q18'de gerçekten yakalandı.

    "Yüklü belgelerin tamamını özetle" hem korpus deseni ("yuklu belge") hem
    özetleme fiili ("ozetle") taşıyor. İlk sürümde korpus deseni önce
    kontrol ediliyordu ve sorgu yanlışlıkla belge LİSTESİ döndürüyordu,
    özetlemiyordu.
    """
    assert query_router.classify("Yüklü belgelerin tamamını kısaca özetle").kind == "summarize"


def test_konu_ozeti_meta_sorgu_sayilmaz():
    """"RAG'i özetle" bir İÇERİK sorusudur -- nesnesi belge değil, konu.

    Özetleme yolu fiil + belge göndergesi ister; yalnızca fiile bakılsaydı bu
    sorgu yanlışlıkla belge özetine yönlenir ve kullanıcı konu hakkında değil
    belge hakkında cevap alırdı.
    """
    route = query_router.classify("Retrieval augmented generation konusunu özetle")
    assert route.kind == "search"


def test_hedef_belge_sorgudan_cozulur():
    route = query_router.classify(
        "Foundry planını özetle", ["Summer School Foundry Local Plan.pdf", "diger.pdf"]
    )
    assert route.kind == "summarize"
    assert route.target == "Summer School Foundry Local Plan.pdf"


def test_turkce_buyuk_i_tuzagi():
    """"İ".lower() birleşen noktalı 'i̇' üretir; düz karşılaştırma kaçırır."""
    assert query_router.normalize("İLGİLİ DÖKÜMAN") == "ilgili dokuman"


# --------------------------------------------------------------------------- store yardımcıları


class _Chunk:
    def __init__(self, content, page=1, source="a.pdf"):
        self.content, self.page, self.source, self.via_ocr = content, page, source, False


@pytest.fixture()
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


def _ingest(conn, filename, n_chunks, dim=4):
    chunks = [_Chunk(f"bolum {i}", page=i + 1, source=filename) for i in range(n_chunks)]
    embeddings = [[float(i + 1)] * dim for i in range(n_chunks)]
    store.upsert_document(conn, filename, n_chunks, chunks, embeddings)


def test_get_document_chunks_belge_sirasini_korur(conn):
    _ingest(conn, "a.pdf", 5)
    rows = store.get_document_chunks(conn, "a.pdf")
    assert [r["content"] for r in rows] == [f"bolum {i}" for i in range(5)]


def test_get_document_chunks_esit_arali_ornekler(conn):
    """Sınır: ilk N alınsaydı özet belgenin yalnızca başını görürdü."""
    _ingest(conn, "a.pdf", 20)
    rows = store.get_document_chunks(conn, "a.pdf", limit=5)
    assert len(rows) == 5
    assert rows[0]["content"] == "bolum 0"    # ilk korunur
    assert rows[-1]["content"] == "bolum 19"  # son korunur
    assert rows[2]["content"] != "bolum 2"    # baştan sıralı değil, yayılmış


def test_get_document_chunks_limit_asilmiyorsa_hepsi_doner(conn):
    _ingest(conn, "a.pdf", 3)
    assert len(store.get_document_chunks(conn, "a.pdf", limit=10)) == 3


def test_corpus_stats(conn):
    _ingest(conn, "a.pdf", 3)
    _ingest(conn, "b.pdf", 2)
    stats = store.corpus_stats(conn)
    assert stats["documents"] == 2
    assert stats["chunks"] == 5


# --------------------------------------------------------------------------- yollar (LLM'siz)


def test_corpus_yolu_llm_cagirmadan_cevaplar(conn, monkeypatch):
    """Kesin bir sayının uydurulabilir olmaması için LLM'e hiç gidilmez."""
    from rag import answer, models

    _ingest(conn, "a.pdf", 3)

    def _boom(*a, **kw):
        raise AssertionError("Korpus sorusunda LLM çağrılmamalı")

    monkeypatch.setattr(models, "get_chat_client", _boom)

    result = answer.answer_query("Kaç belge yükledim?", conn=conn)
    assert result.answered
    assert "1 belge" in result.text
    assert "a.pdf" in result.text


def test_summarize_birden_fazla_belgede_tahmin_etmez(conn, monkeypatch):
    from rag import answer, models

    _ingest(conn, "a.pdf", 2)
    _ingest(conn, "b.pdf", 2)
    monkeypatch.setattr(
        models, "get_chat_client", lambda *a, **kw: pytest.fail("LLM çağrılmamalı")
    )

    result = answer.answer_query("Belgeyi özetle", conn=conn)
    assert "Hangi belgeyi" in result.text
    assert "a.pdf" in result.text and "b.pdf" in result.text


def test_esik_dusurulmedi():
    """Meta-sorgu hatası eşiği zayıflatarak çözülmedi.

    MIN_SCORE düşürülseydi eval'in 3 cevaplanamaz sorusu kaybedilirdi
    (phi-4-mini'nin 3/3 kaybettiği yer). Bu test o refleksi kilitler.
    """
    assert config.MIN_SCORE == 0.45
