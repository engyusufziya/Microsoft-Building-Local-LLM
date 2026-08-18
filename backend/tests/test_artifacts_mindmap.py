"""Studio Faz 3 -- Zihin Haritası (FEATURE_SPEC.md §11) rag/ katmanı.

Foundry Local'a HİÇ dokunulmaz: chat client de embedding de monkeypatch'lenir
(conftest.py deseni). Bu dosya Faz 3'ün iki sözleşmesini regresyona kilitler:

  1. Yapı korpustan gelir, LLM YALNIZCA etiket yazar. Düğüm sayısı, chunk
     üyelikleri ve kenarlar modelden BAĞIMSIZ.
  2. Kapıdan geçemeyen etiket düğümü YOK ETMEZ -- korpustan türeyen
     deterministik ada düşer ve öneri `dropped`'a sebebiyle yazılır (§11.5).
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from rag import config, store
from rag.artifacts import base, mindmap
from rag.artifacts.fidelity import unverified_terms
from rag.artifacts.store import get_artifact
from rag.topics import cluster_corpus, topic_similarity

# Korpusun tamamında geçen cümle: tüm terimleri df=1.0 (AYIRT EDİCİ DEĞİL),
# böylece terim katmanının tek tetikleyicisi tuzak etiketin özel adları olur
# (test_artifacts_report.py'nin aynı gerekçesi).
CORPUS_TEXT = "sqlite veritabanı float32 blob olarak saklar ve bölümleri korur"


class _Chunk:
    def __init__(self, content, source="a.md", page=1):
        self.content, self.source, self.page, self.via_ocr = content, source, page, False


def _unit(angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _FakeChatClient:
    def __init__(self, texts):
        self.texts = list(texts)
        self.contexts = []

    def complete_chat(self, messages):
        self.contexts.append(messages[0]["content"])
        return _response(self.texts.pop(0) if self.texts else "Yedek konu")


@pytest.fixture()
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture()
def corpus(conn):
    """İki belge x iki chunk. Açılar KASITLI: küme merkezleri arası cosine
    MINDMAP_EDGE_MIN_SIMILARITY'nin ÜSTÜNDE kalsın (kenar testi)."""
    store.upsert_document(
        conn, "a.md", 1,
        [_Chunk(CORPUS_TEXT, source="a.md"), _Chunk(CORPUS_TEXT, source="a.md")],
        [_unit(0), _unit(5)],
    )
    store.upsert_document(
        conn, "b.md", 1,
        [_Chunk(CORPUS_TEXT, source="b.md"), _Chunk(CORPUS_TEXT, source="b.md")],
        [_unit(40), _unit(45)],
    )
    return conn


def _run(corpus, monkeypatch, labels, vectors=None):
    """Gerçek hattı (base.generate_artifact) sahte modelle uçtan uca koşar."""
    client = _FakeChatClient(labels)
    monkeypatch.setattr("rag.models.get_chat_client", lambda **kwargs: client)

    # Etiket iddiaları 0 dereceye bağlanır -> ilk chunk ile cos=1.0 (grounded).
    table = dict(vectors or {})
    monkeypatch.setattr(
        "rag.models.embed_texts",
        lambda texts, is_query=False: [table.get(t, _unit(0)) for t in texts],
    )

    events = []
    artifact_id = base.generate_artifact(
        corpus, kind="mindmap", scope="corpus", document_id=None, params={},
        emit=lambda name, payload: events.append((name, payload)),
    )
    return SimpleNamespace(
        artifact=get_artifact(corpus, artifact_id), events=events, client=client
    )


def _resolve(payload: dict, node_path: str):
    """RFC 6901 JSON pointer çözümü -- node_path'in payload'da GERÇEKTEN
    çözüldüğünü kanıtlar."""
    node = payload
    for token in node_path.split("/")[1:]:
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


# --------------------------------------------------------------------------- etiket temizleme


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Chunking stratejisi", "Chunking stratejisi"),
        ("**Chunking stratejisi**", "Chunking stratejisi"),
        ("Konu: Chunking stratejisi", "Chunking stratejisi"),
        ('"Chunking stratejisi."', "Chunking stratejisi"),
        ("Chunking stratejisi\nAçıklama: bu bölüm...", "Chunking stratejisi"),
        ("   Chunking    stratejisi  ", "Chunking stratejisi"),
    ],
)
def test_clean_label_susleme_temizler(raw, expected):
    """§11.4: model prompt'a rağmen markdown/önek/noktalama üretebiliyor
    (raporda kayda geçmiş kozmetik kusurun aynısı). Etiket bir düğüm ADI
    olduğu için temizlik zorunlu."""
    assert mindmap._clean_label(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "Bu küme belgelerin ortak konusunu ayrıntılı biçimde anlatır.",  # 5 kelimeden uzun
    ],
)
def test_clean_label_bicimi_tutmayan_etiket_bos_doner(raw):
    """Boş ya da 5 kelimeden uzun etiket GEÇERSİZDİR -- çağıran deterministik
    yedeğe düşer, düğüm isimsiz kalmaz."""
    assert mindmap._clean_label(raw) == ""


# --------------------------------------------------------------------------- başlık istisnası (§11.4)


def test_baslikta_buyuk_harf_ozel_ad_isareti_sayilmaz(corpus):
    """§11.4 -- ÖLÇÜMDEN doğan kural.

    Faz 3'ün ilk koşumunda 7 etiketin 3'ü düştü ("Yakın Komşu Arama
    Teknikleri" gibi) ve üçü de YANLIŞ POZİTİFTİ: başlıkta HER sözcük büyük
    yazıldığı için "cümle başı olmayan büyük harf" işareti hiçbir bilgi
    taşımıyor. Ayrım çağırana taşındı; cümle veren çağıranın davranışı
    DEĞİŞMEDİ (varsayılan `is_title=False`).
    """
    chunk_ids = [row["id"] for row in corpus.execute("SELECT id FROM chunks")]
    label = "Yakın Komşu Arama Teknikleri"

    # Cümle olarak değerlendirilirse: büyük harfli sözcükler kontrol edilir ve
    # korpusta geçmedikleri için doğrulanamamış sayılır.
    assert unverified_terms(corpus, label, chunk_ids) != []
    # Başlık olarak değerlendirilirse: büyük harf kolu hiç çalışmaz.
    assert unverified_terms(corpus, label, chunk_ids, is_title=True) == []


def test_baslikta_rakam_kolu_calismaya_devam_eder(corpus):
    """İstisna büyük harf koluyla SINIRLI: uydurma model kimliği hâlâ yakalanır
    -- yoksa Faz 2'nin tuzak savunması etiketlerde sessizce kapanırdı."""
    chunk_ids = [row["id"] for row in corpus.execute("SELECT id FROM chunks")]
    assert "gpt-4" in unverified_terms(corpus, "GPT-4 mimarisi", chunk_ids, is_title=True)


# --------------------------------------------------------------------------- yapı


def test_dugumler_kok_ve_kume_basina_bir_dugum(corpus, monkeypatch):
    """§11.5: nodes[0] KÖK'tür ve korpus metadatasından gelir; her küme için
    tam olarak bir topic düğümü vardır."""
    result = _run(corpus, monkeypatch, ["Alfa konusu", "Beta konusu"])
    payload = result.artifact["payload"]
    nodes = payload["nodes"]

    assert payload["kind"] == "mindmap"
    assert nodes[0]["kind"] == "root"
    assert nodes[0]["parent"] is None
    assert nodes[0]["label_source"] == "corpus"
    assert nodes[0]["size"] == 4  # korpustaki toplam chunk

    topics = [n for n in nodes if n["kind"] == "topic"]
    assert len(topics) == len(cluster_corpus(corpus))
    assert all(n["parent"] == "root" for n in topics)
    assert sorted(cid for n in topics for cid in n["chunk_ids"]) == [1, 2, 3, 4]
    assert all(n["size"] == len(n["chunk_ids"]) for n in topics)


def test_dugum_kaynaklari_her_chunk_icin_atif_tasir(corpus, monkeypatch):
    """§11.5 "her düğüm kaynağa tıklanabilir": düğümün TÜM chunk'larının
    kaynak etiketi payload'dadır -- arayüz ikinci bir istek atmaz."""
    result = _run(corpus, monkeypatch, ["Alfa konusu", "Beta konusu"])
    for node in result.artifact["payload"]["nodes"]:
        if node["kind"] == "root":
            continue
        assert len(node["citations"]) == len(node["chunk_ids"])
        for citation in node["citations"]:
            assert citation["citation"].startswith("[Kaynak: ")
            assert citation["chunk_id"] in node["chunk_ids"]


def test_yapi_modelden_bagimsiz(corpus, monkeypatch):
    """§11.1: "haritayı LLM çizmez". Etiketler tamamen değişse bile düğüm
    kimlikleri, chunk üyelikleri ve kenarlar AYNI kalır."""
    first = _run(corpus, monkeypatch, ["Alfa konusu", "Beta konusu"])
    second = _run(corpus, monkeypatch, ["Bambaska sey", "Tamamen farkli"])

    def skeleton(artifact):
        payload = artifact["payload"]
        return (
            [(n["id"], n["kind"], tuple(n["chunk_ids"])) for n in payload["nodes"]],
            [(e["from"], e["to"], round(e["weight"], 6)) for e in payload["edges"]],
        )

    assert skeleton(first.artifact) == skeleton(second.artifact)


# --------------------------------------------------------------------------- kenarlar


def test_kenar_esigi_ham_cosine_ile_karsilastirilir(corpus, monkeypatch):
    """§11.6: kenar ağırlığı HAM COSINE'dır (topic_similarity ile birebir) ve
    yalnızca MINDMAP_EDGE_MIN_SIMILARITY'yi AŞAN çiftler çizilir."""
    result = _run(corpus, monkeypatch, ["Alfa konusu", "Beta konusu"])
    edges = result.artifact["payload"]["edges"]
    topics = cluster_corpus(corpus)

    assert len(edges) == 1
    edge = edges[0]
    expected = topic_similarity(topics[0], topics[1])
    assert edge["weight"] == pytest.approx(expected)
    assert edge["weight"] > config.MINDMAP_EDGE_MIN_SIMILARITY
    assert edge["relation"] == "related"


def test_uzak_kumelerde_kenar_yok_bu_hata_degil(conn, monkeypatch):
    """Kenarsız harita geçerli bir çıktıdır: kümeler gerçekten uzaksa yıldız
    çizilir (config.MINDMAP_EDGE_MIN_SIMILARITY ölçümü)."""
    store.upsert_document(
        conn, "a.md", 1, [_Chunk(CORPUS_TEXT), _Chunk(CORPUS_TEXT)],
        [_unit(0), _unit(5)],
    )
    store.upsert_document(
        conn, "b.md", 1,
        [_Chunk(CORPUS_TEXT, source="b.md"), _Chunk(CORPUS_TEXT, source="b.md")],
        [_unit(90), _unit(95)],
    )
    result = _run(conn, monkeypatch, ["Alfa konusu", "Beta konusu"])
    assert result.artifact["payload"]["edges"] == []
    assert len([n for n in result.artifact["payload"]["nodes"] if n["kind"] == "topic"]) == 2


# --------------------------------------------------------------------------- sadakat kapısı


def test_kapidan_gecemeyen_etiket_korpustan_turer_dugum_kalir(corpus, monkeypatch):
    """§11.5 -- Faz 3'ün rapordan AYRILDIĞI nokta.

    Tuzak etiket ("GPT-4 mimarisi") korpusta hiç geçmeyen bir model kimliği
    taşıyor: ikinci katman düşürür. Düğüm SİLİNMEZ, etiketi
    topics.topic_title'ın ürettiği ada düşer ve `label_source` bunu söyler.
    """
    result = _run(corpus, monkeypatch, ["GPT-4 mimarisi", "Beta konusu"])
    payload = result.artifact["payload"]
    topics = [n for n in payload["nodes"] if n["kind"] == "topic"]

    assert len(topics) == 2  # düğüm KAYBOLMADI
    fallback = topics[0]
    assert fallback["label_source"] == "fallback"
    assert fallback["label"] == "a.md (2 bölüm)"

    assert len(payload["dropped"]) == 1
    dropped = payload["dropped"][0]
    assert dropped["text"] == "GPT-4 mimarisi"
    assert dropped["reason"] == "unverified_terms"
    assert "gpt-4" in dropped["terms"]
    assert dropped["score"] is not None  # HAM COSINE korunur


def test_bicimsiz_etiket_label_invalid_olarak_dusurulur(corpus, monkeypatch):
    """Biçimi tutmayan etiket kapıya HİÇ sokulmaz (bind_claims'e boş dize
    vermek anlamsız bir skor üretirdi); sebep `label_invalid`, skor None."""
    result = _run(
        corpus, monkeypatch,
        ["Bu küme belgelerin ortak konusunu ayrıntılı biçimde anlatır.", "Beta konusu"],
    )
    payload = result.artifact["payload"]
    dropped = payload["dropped"]

    assert [d["reason"] for d in dropped] == ["label_invalid"]
    assert dropped[0]["score"] is None
    assert dropped[0]["text"] == ""
    assert payload["nodes"][1]["label_source"] == "fallback"


def test_claims_yalnizca_model_etiketleri_icin_yazilir(corpus, monkeypatch):
    """§11.7: yedek etiket korpustan deterministik türüyor -- onu iddia sayıp
    sadakat oranına katmak, ölçülmemişi ölçülmüş göstermek olurdu."""
    result = _run(corpus, monkeypatch, ["GPT-4 mimarisi", "Beta konusu"])
    artifact = result.artifact
    payload = artifact["payload"]

    kept = [c for c in artifact["claims"] if c["node_path"].startswith("/nodes/")]
    assert len(kept) == 1
    assert _resolve(payload, kept[0]["node_path"]) == "Beta konusu"

    dropped_claims = [c for c in artifact["claims"] if c["node_path"].startswith("/dropped/")]
    assert len(dropped_claims) == 1
    assert dropped_claims[0]["claim_text"] == "GPT-4 mimarisi"

    # fidelity_score bir ORAN: 2 iddianın 2'si de grounded bağlanmış
    # (tuzağı düşüren ikinci katman, bağlamayı DEĞİŞTİRMEZ -- §10.1.2 pini).
    assert artifact["fidelity_score"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- ilerleme + export


def test_progress_olaylari_kume_basina_ve_tam_sayi(corpus, monkeypatch):
    """§9.5'te dondurulmuş ölçek: `pct` 0-100 TAM SAYI."""
    result = _run(corpus, monkeypatch, ["Alfa konusu", "Beta konusu"])
    progress = [payload for name, payload in result.events if name == "progress"]

    assert len(progress) == 2
    assert [p["pct"] for p in progress] == [50, 100]
    assert all(isinstance(p["pct"], int) for p in progress)


def test_markdown_export_disari_kaynak_icermez(corpus, monkeypatch):
    """§11.8 / AGENTS.md §1.2: markdown düz metindir, http(s):// üretmez;
    düşürülen etiketin METNİ gövdeye girmez, yalnızca sayısı."""
    result = _run(corpus, monkeypatch, ["GPT-4 mimarisi", "Beta konusu"])
    text = mindmap.to_markdown(result.artifact["payload"])

    assert "http://" not in text and "https://" not in text
    assert "Beta konusu" in text
    assert "GPT-4 mimarisi" not in text        # düşürülen ÖNERİ gövdede yok
    assert "a.md (2 bölüm)" in text            # yerine deterministik ad
    assert "1 etiket önerisi" in text          # yalnızca SAYI
    assert "[Kaynak: a.md s.1]" in text
