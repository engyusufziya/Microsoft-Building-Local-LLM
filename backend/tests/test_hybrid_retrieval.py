"""Hibrit retrieval (rag/retrieve.py + rag/store.py::bm25_candidates).

Görev 3: dense (cosine) top-k, korpus büyüdükçe sözcüksel olarak birebir
eşleşen ama semantik olarak "merkez"den uzak kalan chunk'ları k sınırının
dışında bırakabilir (özel adlar, model kimlikleri, teknik terimler --
embedding'lerin en zayıf olduğu yer). Bu testler iki şeyi doğrular:

  1. store.bm25_candidates FTS5 üzerinden gerçekten çalışıyor.
  2. retrieve.get_top_chunks hibritken bu tarz bir chunk'ı KURTARIYOR --
     ve KRİTİK OLARAK: Hit.score hâlâ ham cosine'dır, RRF/BM25 skoru değil
     (rag/config.py'de dondurulan MIN_SCORE/Inspector sözleşmesi bozulmuyor).
"""

from __future__ import annotations

import math

import pytest

from rag import retrieve, store


class _Chunk:
    def __init__(self, content, source="a.pdf", page=1):
        self.content, self.source, self.page, self.via_ocr = content, source, page, False


@pytest.fixture()
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


# --------------------------------------------------------------------------- bm25_candidates


def test_bm25_candidates_birebir_terimi_bulur(conn):
    chunks = [
        _Chunk("elma armut portakal"),
        _Chunk("benzersiz-kod xyzzy123 hakkinda bilgi"),
        _Chunk("kiwi mango seftali"),
    ]
    embeddings = [[1.0, 0.0]] * 3
    store.upsert_document(conn, "a.pdf", 3, chunks, embeddings)

    ids = store.bm25_candidates(conn, "xyzzy123 nedir", limit=10)
    assert len(ids) == 1
    row = conn.execute("SELECT content FROM chunks WHERE id = ?", (ids[0],)).fetchone()
    assert "xyzzy123" in row["content"]


def test_bm25_candidates_bos_sorguda_bos_liste(conn):
    assert store.bm25_candidates(conn, "", limit=10) == []
    assert store.bm25_candidates(conn, "???", limit=10) == []


def test_bm25_candidates_silinen_belgede_gorunmez(conn):
    """FTS5 senkronu trigger'larla sağlanıyor -- delete sonrası indekste kalmamalı."""
    chunks = [_Chunk("xyzzy123 benzersiz terim")]
    store.upsert_document(conn, "a.pdf", 1, chunks, [[1.0, 0.0]])
    assert store.bm25_candidates(conn, "xyzzy123", limit=10) == [1]

    store.delete_document(conn, "a.pdf")
    assert store.bm25_candidates(conn, "xyzzy123", limit=10) == []


# --------------------------------------------------------------------------- get_top_chunks (hibrit)


def _unit(angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


def test_hibrit_lexical_kurtarma_dense_disinda_kalani_getirir(conn, monkeypatch):
    """Ana senaryo: D chunk'ı cosine'da 5. sırada (k=4 dışında) ama BENZERSİZ bir
    terimle sorguyla birebir eşleşiyor. Hibrit onu top-4'e taşımalı; dense-only
    (hybrid=False) taşımamalı. D'nin DÖNEN skoru yine kendi ham cosine'ı (0.50)
    olmalı -- RRF skoru DEĞİL.
    """
    labels = ["A", "B", "C", "E", "D"]
    angles = [0, 18, 26, 34, 60]  # cos: 1.0, .951, .899, .829, .500
    chunks = [_Chunk(f"icerik {name}" if name != "D" else "xyzzy123 benzersiz terim")
              for name in labels]
    embeddings = [_unit(a) for a in angles]
    store.upsert_document(conn, "doc.pdf", 1, chunks, embeddings)

    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [[1.0, 0.0]]
    )

    dense_only = retrieve.get_top_chunks("xyzzy123 nedir", k=4, conn=conn, hybrid=False)
    assert {round(h.score, 2) for h in dense_only} == {1.0, 0.95, 0.90, 0.83}  # D yok

    hybrid = retrieve.get_top_chunks("xyzzy123 nedir", k=4, conn=conn, hybrid=True)
    scores = [round(h.score, 2) for h in hybrid]
    assert 0.50 in scores  # D kurtarıldı
    assert 0.83 not in scores  # en zayıf dense aday (E) yerini D'ye bıraktı

    # KRİTİK: D'nin skoru RRF/BM25 değeri değil, kendi ham cosine'ı.
    d_hit = next(h for h in hybrid if round(h.score, 2) == 0.50)
    assert d_hit.score == pytest.approx(math.cos(math.radians(60)), abs=1e-6)


def test_hibrit_esik_altindaki_lexical_eslesmeyi_kurtarmaz(conn, monkeypatch):
    """Hibrit ADAY havuzunu genişletir, MIN_SCORE eşiğini DEĞİL.

    D'nin cosine'ı eşiğin (0.45) altındaysa -- BM25'te birebir eşleşse bile --
    min_score verilince yine elenir. Bu, config.py'deki "eşik değil, k sınırı
    kurtarılıyor" iddiasının regresyon testi.
    """
    chunks = [_Chunk("icerik A"), _Chunk("xyzzy123 benzersiz terim")]
    embeddings = [_unit(0), _unit(80)]  # ikinci chunk cosine ~ 0.17
    store.upsert_document(conn, "doc.pdf", 1, chunks, embeddings)
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [[1.0, 0.0]]
    )

    hits = retrieve.get_top_chunks(
        "xyzzy123 nedir", k=4, min_score=0.45, conn=conn, hybrid=True
    )
    assert all(h.score >= 0.45 for h in hits)
    assert not any("xyzzy123" in h.content for h in hits)


def test_varsayilan_kapali(conn):
    """ÖLÇÜLDÜ (Görev 3, eval/config.py::HYBRID_RETRIEVAL_ENABLED): 23 soruluk
    sette hibrit AÇIKKEN 22/23, KAPALIYKEN 23/23 -- varsayılan bu yüzden kapalı.
    Bu test o kararın YANLIŞLIKLA geri alınmasına karşı bir kilit.
    """
    from rag import config

    assert config.HYBRID_RETRIEVAL_ENABLED is False


def test_hibrit_devre_disi_config_bayragi(conn, monkeypatch):
    """hybrid=None -> config.HYBRID_RETRIEVAL_ENABLED okunur (kapalı yön)."""
    from rag import config

    chunks = [_Chunk(f"icerik {i}") for i in range(3)]
    store.upsert_document(conn, "doc.pdf", 1, chunks, [_unit(a) for a in (0, 20, 40)])
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [[1.0, 0.0]]
    )
    monkeypatch.setattr(config, "HYBRID_RETRIEVAL_ENABLED", False)

    # bm25_candidates çağrılırsa patlat -- kapalıyken hiç çağrılmamalı.
    monkeypatch.setattr(
        store, "bm25_candidates",
        lambda *a, **kw: pytest.fail("HYBRID_RETRIEVAL_ENABLED=False iken çağrılmamalı"),
    )
    retrieve.get_top_chunks("herhangi bir soru", k=2, conn=conn)  # patlamamalı


def test_hibrit_etkin_config_bayragi(conn, monkeypatch):
    """hybrid=None -> config.HYBRID_RETRIEVAL_ENABLED okunur (açık yön).

    Bayrak True'yken bm25_candidates GERÇEKTEN çağrılmalı -- yalnızca
    "patlamıyor" değil, doğru koşulda doğru davranış.
    """
    from rag import config

    chunks = [_Chunk("xyzzy123 benzersiz terim"), _Chunk("baska icerik")]
    store.upsert_document(conn, "doc.pdf", 1, chunks, [_unit(60), _unit(0)])
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [[1.0, 0.0]]
    )
    monkeypatch.setattr(config, "HYBRID_RETRIEVAL_ENABLED", True)

    called = []
    real_bm25 = store.bm25_candidates
    monkeypatch.setattr(
        store, "bm25_candidates",
        lambda *a, **kw: (called.append(True), real_bm25(*a, **kw))[1],
    )
    retrieve.get_top_chunks("xyzzy123 nedir", k=2, conn=conn)
    assert called, "HYBRID_RETRIEVAL_ENABLED=True iken bm25_candidates çağrılmalı"
