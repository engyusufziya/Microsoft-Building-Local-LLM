"""Studio artefakt hattının ORTAK rag/ katmanı: şema göçü, corpus_fingerprint,
rag/topics.py::cluster_corpus, rag/artifacts/ (fidelity, store, base).

Bu dosya hattın TİP-BAĞIMSIZ kısmını ölçer; üretici başına testler
test_artifacts_{report,mindmap,quiz}.py'dedir.

FEATURE_SPEC.md §9'un doğrulanabilir kriterlerinin regresyon kilidi. Foundry
Local'a HİÇ dokunulmaz -- conftest.py'nin deseni izlenir: kümeleme zaten
tamamen numpy/store tabanlı (embed_texts çağırmaz), yalnızca
fidelity.bind_claims için rag.models.embed_texts monkeypatch'lenir.
"""

from __future__ import annotations

import math

import pytest

from rag import config, store, topics
from rag.artifacts import base
from rag.artifacts import fidelity
from rag.artifacts import store as astore
from rag.artifacts.fidelity import ClaimBinding


class _Chunk:
    def __init__(self, content, source="a.md", page=1):
        self.content, self.source, self.page, self.via_ocr = content, source, page, False


def _unit(angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


@pytest.fixture()
def conn():
    # Burada clear_cache() YOK, bilinçli: store._Connection.close() kapanışta
    # ":memory:" önbellek girdisini kendisi düşürüyor (bkz. test_store_cache.py,
    # id() çakışması orada deterministik olarak kanıtlanıyor). Savunma amaçlı
    # bir clear_cache() burada dursaydı, o düzeltme ileride bozulduğunda bu
    # dosyadaki testleri yeşil tutup regresyonu maskelerdi.
    c = store.connect(":memory:")
    yield c
    c.close()


# --------------------------------------------------------------------------- şema göçü


def test_sema_yeni_tablolar_ve_indeksler_eklendi(conn):
    """§9.1: üç yeni tablo + üç yeni indeks; mevcut şema dokunulmamış."""
    objs = {
        (r["type"], r["name"])
        for r in conn.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'index')"
        )
    }
    for name in ("artifacts", "artifact_claims", "quiz_attempts"):
        assert ("table", name) in objs
    for name in ("idx_artifacts_kind", "idx_claims_artifact", "idx_attempts_artifact"):
        assert ("index", name) in objs
    # mevcut şema (documents/chunks/chunks_fts + idx_chunks_doc) korunmuş
    for name in ("documents", "chunks", "chunks_fts"):
        assert ("table", name) in objs
    assert ("index", "idx_chunks_doc") in objs


def test_config_studio_sabitleri():
    """Regresyon kilidi: FEATURE_SPEC §9.3'teki altı sabit."""
    assert config.ARTIFACT_SECTION_MAX_TOKENS == 700
    assert config.ARTIFACT_LABEL_MAX_TOKENS == 40
    assert config.ARTIFACT_QUESTION_MAX_TOKENS == 200
    assert config.TOPIC_MIN_CLUSTER_SIZE == 2
    assert config.TOPIC_MAX_CLUSTERS == 12
    # FIDELITY_MIN_SCORE == MIN_SCORE bilinçli (§9.3) -- ölçümsüz ayrılmamalı.
    assert config.FIDELITY_MIN_SCORE == config.MIN_SCORE == 0.45


# --------------------------------------------------------------------------- corpus_fingerprint


def test_corpus_fingerprint_deterministik_ve_degisir(conn):
    fp1 = store.corpus_fingerprint(conn)
    fp2 = store.corpus_fingerprint(conn)
    assert fp1 == fp2
    assert len(fp1) == 64

    store.upsert_document(conn, "a.md", 1, [_Chunk("c1")], [[1.0, 0.0]])
    fp_with_doc = store.corpus_fingerprint(conn)
    assert fp_with_doc != fp1

    store.delete_document(conn, "a.md")
    fp_after_delete = store.corpus_fingerprint(conn)
    assert fp_after_delete == fp1


# --------------------------------------------------------------------------- topics.cluster_corpus


def test_cluster_corpus_belge_bazinda_ayirir(conn):
    """Üç ayrı belgeden gelen, açıyla iyi ayrılmış chunk'lar üç ayrı kümeye düşmeli."""
    chunks = (
        [_Chunk(f"a{i}", source="a.md") for i in range(3)]
        + [_Chunk(f"b{i}", source="b.md") for i in range(2)]
        + [_Chunk(f"c{i}", source="c.md") for i in range(3)]
    )
    angles = [0, 4, 8, 90, 94, 180, 184, 188]
    store.upsert_document(conn, "doc.pdf", 1, chunks, [_unit(a) for a in angles])

    result = topics.cluster_corpus(conn, max_clusters=3, min_cluster_size=2)
    assert len(result) == 3
    assert {t.size for t in result} == {3, 2, 3}

    ids_by_source = {}
    for i, ch in enumerate(chunks, start=1):
        ids_by_source.setdefault(ch.source, set()).add(i)

    found_groups = {frozenset(t.chunk_ids) for t in result}
    expected_groups = {frozenset(v) for v in ids_by_source.values()}
    assert found_groups == expected_groups

    # boyuta göre azalan id ataması
    assert [t.id for t in result] == [0, 1, 2]
    assert [t.size for t in result] == sorted([t.size for t in result], reverse=True)


def test_cluster_corpus_kucuk_kume_en_yakina_emilir(conn):
    """4. adım: min_cluster_size altında kalan küme atılmaz, en yakın kümeye emilir."""
    chunks = [_Chunk(f"x{i}") for i in range(5)]
    # {0,2}: cift; {90,92}: cift; {180}: tekil -- 180, kosinuse gore 90/92
    # cubuguna 0/2'den cok daha yakin (cos(88)=0.03 > cos(178)=-0.999).
    angles = [0, 2, 90, 92, 180]
    store.upsert_document(conn, "doc.pdf", 1, chunks, [_unit(a) for a in angles])

    result = topics.cluster_corpus(conn, max_clusters=3, min_cluster_size=2)

    assert all(t.size >= 2 for t in result)
    assert len(result) == 2  # 3 hedeflenmişti, emilme sonrası 2'ye düştü

    # chunk id'leri 1-tabanlı (insert sırası); 180'lik chunk (id=5) 90/92
    # grubuyla (id=3,4) aynı kümede olmalı.
    absorbing = next(t for t in result if 5 in t.chunk_ids)
    assert set(absorbing.chunk_ids) == {3, 4, 5}


def test_cluster_corpus_determinizm(conn):
    """İki ardışık çağrı birebir aynı Topic listesini üretmeli (id, sıra, chunk_ids, centroid)."""
    chunks = [_Chunk(f"c{i}") for i in range(6)]
    angles = [0, 5, 10, 90, 95, 200]
    store.upsert_document(conn, "doc.pdf", 1, chunks, [_unit(a) for a in angles])

    t1 = topics.cluster_corpus(conn)
    t2 = topics.cluster_corpus(conn)

    assert [t.id for t in t1] == [t.id for t in t2]
    assert [t.chunk_ids for t in t1] == [t.chunk_ids for t in t2]
    assert [t.size for t in t1] == [t.size for t in t2]
    for a, b in zip(t1, t2):
        assert (a.centroid == b.centroid).all()


def test_cluster_corpus_sinir_durumlari(conn):
    """N==0 ve N < TOPIC_MIN_CLUSTER_SIZE InsufficientCorpusError fırlatır."""
    matrix, meta = store.load_matrix(conn)
    assert matrix.shape == (0, 0)
    with pytest.raises(topics.InsufficientCorpusError):
        topics.cluster_corpus(conn)

    store.upsert_document(conn, "a.md", 1, [_Chunk("tek")], [[1.0, 0.0]])
    with pytest.raises(topics.InsufficientCorpusError):
        topics.cluster_corpus(conn, min_cluster_size=2)


def test_topic_similarity(conn):
    chunks = [_Chunk(f"c{i}") for i in range(4)]
    angles = [0, 2, 90, 92]
    store.upsert_document(conn, "doc.pdf", 1, chunks, [_unit(a) for a in angles])

    result = topics.cluster_corpus(conn, max_clusters=2, min_cluster_size=2)
    assert len(result) == 2
    sim = topics.topic_similarity(result[0], result[1])
    assert -1.0 <= sim <= 1.0
    assert topics.topic_similarity(result[0], result[0]) == pytest.approx(1.0, abs=1e-5)


# --------------------------------------------------------------------------- fidelity


def test_verdict_for_bantlari():
    assert fidelity.verdict_for(None) == "unsupported"
    assert fidelity.verdict_for(0.45) == "grounded"
    assert fidelity.verdict_for(0.44) == "weak"
    assert fidelity.verdict_for(0.35) == "weak"
    assert fidelity.verdict_for(0.34) == "unsupported"


def test_bind_claims_grounded_weak_unsupported(conn, monkeypatch):
    """Sadakat kapısının üç bandı: gerçek/yakın bir iddia grounded, orta
    mesafeli bir iddia weak, ilgisiz bir iddia unsupported çıkmalı.
    """
    store.upsert_document(conn, "a.md", 1, [_Chunk("hedef chunk")], [_unit(0)])

    vectors_by_text = {
        "grounded iddia": _unit(0),    # cos=1.00  -> grounded
        "weak iddia": _unit(66),       # cos=0.407 -> weak (0.35-0.45)
        "unsupported iddia": _unit(90),  # cos=0.00  -> unsupported
    }

    def fake_embed(texts, is_query=False):
        return [vectors_by_text[t] for t in texts]

    monkeypatch.setattr("rag.models.embed_texts", fake_embed)

    claims = [
        ("/nodes/0", "grounded iddia"),
        ("/nodes/1", "weak iddia"),
        ("/nodes/2", "unsupported iddia"),
    ]
    bindings = fidelity.bind_claims(conn, claims)
    verdicts = {b.node_path: b.verdict for b in bindings}
    assert verdicts == {
        "/nodes/0": "grounded",
        "/nodes/1": "weak",
        "/nodes/2": "unsupported",
    }
    # skor HAM COSINE olarak kalmalı -- yeniden ölçeklenmemiş.
    grounded = next(b for b in bindings if b.node_path == "/nodes/0")
    assert grounded.score == pytest.approx(1.0, abs=1e-6)
    assert grounded.chunk_id == 1

    assert fidelity.fidelity_score(bindings) == pytest.approx(1 / 3)


def test_bind_claims_bos_korpus(conn):
    bindings = fidelity.bind_claims(conn, [("/n/0", "herhangi bir iddia")])
    assert bindings == [
        ClaimBinding("/n/0", "herhangi bir iddia", None, None, "unsupported")
    ]


def test_bind_claims_bos_liste(conn):
    assert fidelity.bind_claims(conn, []) == []


def test_fidelity_score_bos_liste_none_doner():
    assert fidelity.fidelity_score([]) is None


# --------------------------------------------------------------------------- artifacts/store.py CRUD


def test_create_list_get_delete_artifact(conn):
    # artifact_claims.chunk_id gerçek bir chunks.id'ye REFERENCES eder
    # (foreign_keys=ON); grounded iddia için geçerli bir chunk gerekli.
    store.upsert_document(conn, "a.md", 1, [_Chunk("hedef chunk")], [[1.0, 0.0]])
    claims = [
        ClaimBinding("/nodes/0", "iddia 1", 1, 0.71, "grounded"),
        ClaimBinding("/nodes/1", "iddia 2", None, None, "unsupported"),
    ]
    artifact_id = astore.create_artifact(
        conn,
        kind="mindmap",
        scope="corpus",
        document_id=None,
        title="Test Harita",
        params={"x": 1},
        payload={"nodes": []},
        corpus_fingerprint="deadbeef",
        fidelity_score=0.5,
        generation_ms=123,
        claims=claims,
    )
    assert artifact_id > 0

    summaries = astore.list_artifacts(conn)
    assert len(summaries) == 1
    assert summaries[0]["id"] == artifact_id
    assert "payload" not in summaries[0]

    assert astore.list_artifacts(conn, kind="report") == []
    assert len(astore.list_artifacts(conn, kind="mindmap", scope="corpus")) == 1

    detail = astore.get_artifact(conn, artifact_id)
    assert detail["title"] == "Test Harita"
    assert detail["payload"] == {"nodes": []}
    assert detail["params"] == {"x": 1}
    assert len(detail["claims"]) == 2
    assert detail["claims"][0]["verdict"] == "grounded"

    assert astore.get_artifact(conn, 999999) is None

    assert astore.delete_artifact(conn, artifact_id) is True
    assert astore.delete_artifact(conn, artifact_id) is False
    assert astore.get_artifact(conn, artifact_id) is None
    # ON DELETE CASCADE: iddialar da gitmiş olmalı.
    remaining = conn.execute("SELECT COUNT(*) FROM artifact_claims").fetchone()[0]
    assert remaining == 0


# --------------------------------------------------------------------------- base.generate_artifact


def test_generate_artifact_kayitsiz_kind_generation_failed(conn):
    """Seçim ve kümeleme GERÇEKTEN çalışır, sonra kayıtlı üretici yoksa
    GenerationFailedError fırlar.

    Faz 1'de bu testin `kind`'ı "mindmap"ti (o zaman registry BOŞTU). Faz 3/4
    ile üç kind'in üçü de kayıtlandı; test artık gerçekten kayıtsız bir kind
    kullanıyor. Ölçtüğü davranış aynı: hat 3. adıma kadar çalışır."""
    chunks = [_Chunk(f"c{i}") for i in range(4)]
    store.upsert_document(
        conn, "a.md", 1, chunks, [_unit(a) for a in (0, 5, 90, 95)]
    )

    events = []
    with pytest.raises(base.GenerationFailedError):
        base.generate_artifact(
            conn, kind="kayitsiz-kind", scope="corpus", document_id=None,
            params={}, emit=lambda name, payload: events.append((name, payload)),
        )

    stages = [payload["stage"] for name, payload in events if name == "stage"]
    assert stages == ["selection", "clustering", "generation"]


def test_generate_artifact_yetersiz_korpus_once_asamalar_yayilir(conn):
    events = []
    with pytest.raises(topics.InsufficientCorpusError):
        base.generate_artifact(
            conn, kind="mindmap", scope="corpus", document_id=None,
            params={}, emit=lambda name, payload: events.append((name, payload)),
        )
    # kümeleme adımı patlamadan ÖNCE seçim ve kümeleme stage'leri yayılmış olmalı
    stages = [payload["stage"] for name, payload in events if name == "stage"]
    assert stages == ["selection", "clustering"]


def test_generate_artifact_bilinmeyen_belge_id(conn):
    events = []
    with pytest.raises(ValueError):
        base.generate_artifact(
            conn, kind="mindmap", scope="document", document_id=999,
            params={}, emit=lambda name, payload: events.append((name, payload)),
        )
    assert events == [("stage", {"stage": "selection", "label": "Kaynaklar seçiliyor"})]


def test_cluster_corpus_belge_kapsami_yalnizca_o_belgeyi_kumeler(conn):
    """§9.8 1. adım: `scope="document"` chunk KÜMESİNİ daraltır.

    Bu davranış eskiden YOKTU: `document_id` yalnızca doğrulanıp kaydediliyor,
    kümeleme her zaman korpusun tamamı üzerinde koşuyordu. Sonuç, belge adını
    taşıyan başlığın altında korpus geneli bir artefakttı.
    """
    store.upsert_document(
        conn, "a.md", 1, [_Chunk(f"a{i}", source="a.md") for i in range(3)],
        [_unit(a) for a in (0, 5, 10)],
    )
    store.upsert_document(
        conn, "b.md", 1, [_Chunk(f"b{i}", source="b.md") for i in range(3)],
        [_unit(a) for a in (90, 95, 100)],
    )

    a_id = conn.execute("SELECT id FROM documents WHERE filename = 'a.md'").fetchone()["id"]
    a_chunk_ids = {
        r["id"] for r in conn.execute("SELECT id FROM chunks WHERE source = 'a.md'")
    }

    scoped = topics.cluster_corpus(conn, document_id=a_id)
    clustered = {cid for t in scoped for cid in t.chunk_ids}
    assert clustered == a_chunk_ids
    assert sum(t.size for t in scoped) == 3

    # Kapsamsız çağrı DEĞİŞMEDİ: altı chunk'ın altısı da kümelenir.
    assert sum(t.size for t in topics.cluster_corpus(conn)) == 6


def test_cluster_corpus_belge_kapsami_yetersiz_chunk(conn):
    """Tek chunk'lık bir belge, korpus kalabalık olsa bile kümelenemez.

    Dürüst davranış budur: kapsam belgeyse yeterlilik de belge üzerinden
    ölçülür. Rota bunu akış açılmadan ÖNCE 422 INSUFFICIENT_CORPUS'a çevirir.
    """
    store.upsert_document(
        conn, "buyuk.md", 1, [_Chunk(f"x{i}", source="buyuk.md") for i in range(4)],
        [_unit(a) for a in (0, 5, 90, 95)],
    )
    store.upsert_document(
        conn, "tek.md", 1, [_Chunk("y", source="tek.md")], [_unit(180)]
    )
    tek_id = conn.execute("SELECT id FROM documents WHERE filename = 'tek.md'").fetchone()["id"]

    with pytest.raises(topics.InsufficientCorpusError):
        topics.cluster_corpus(conn, document_id=tek_id)

    # Korpus geneli hâlâ kümelenebiliyor -- yetersizlik KAPSAMA ait.
    assert topics.cluster_corpus(conn)


def test_generate_artifact_belge_kapsami_ureticiye_daraltilmis_topics_verir(conn):
    """Hattın uçtan uca kilidi: üretici, YALNIZCA seçili belgenin chunk'larını görür."""
    store.upsert_document(
        conn, "a.md", 1, [_Chunk(f"a{i}", source="a.md") for i in range(3)],
        [_unit(a) for a in (0, 5, 10)],
    )
    store.upsert_document(
        conn, "b.md", 1, [_Chunk(f"b{i}", source="b.md") for i in range(3)],
        [_unit(a) for a in (90, 95, 100)],
    )
    a_id = conn.execute("SELECT id FROM documents WHERE filename = 'a.md'").fetchone()["id"]
    a_chunk_ids = {
        r["id"] for r in conn.execute("SELECT id FROM chunks WHERE source = 'a.md'")
    }

    seen: dict = {}

    class _KapsamKaydeden:
        kind = "kayitsiz-kind"

        def generate(self, ctx):
            seen["chunk_ids"] = {cid for t in ctx.topics for cid in t.chunk_ids}
            seen["scope"] = ctx.scope
            seen["document_id"] = ctx.document_id
            return base.GeneratedArtifact(title="t", payload={}, claims=[])

    base.register(_KapsamKaydeden())
    try:
        base.generate_artifact(
            conn, kind="kayitsiz-kind", scope="document", document_id=a_id,
            params={}, emit=lambda name, payload: None,
        )
    finally:
        base._registry.pop("kayitsiz-kind", None)

    assert seen["chunk_ids"] == a_chunk_ids
    assert seen["scope"] == "document"
    assert seen["document_id"] == a_id


def test_registry_uc_kind_da_kayitli_ve_register_calisir(conn):
    """§9.5: üç üreticinin üçü de kendi modülü yüklenirken kaydolur.

    Faz 1'de registry BOŞTU, Faz 2'de yalnızca `report` doldu; Faz 3 mindmap'i,
    Faz 4 quiz'i ekledi. Kayıt, `rag/artifacts/__init__.py`'nin alt modülleri
    import etmesiyle gerçekleşir -- bu dosyanın `from rag.artifacts import base`
    satırı paketi zaten yüklüyor."""
    assert base.get_generator("report") is not None
    assert base.get_generator("mindmap") is not None
    assert base.get_generator("quiz") is not None
    # Kayıtlı OLMAYAN bir kind hâlâ None döner -- hattın 3. adımdaki hata yolu
    # (test_generate_artifact_kayitsiz_kind_generation_failed) buna dayanıyor.
    assert base.get_generator("kayitsiz-kind") is None

    class _DummyGenerator:
        kind = "kayitsiz-kind"

        def generate(self, ctx):
            return base.GeneratedArtifact(title="t", payload={}, claims=[])

    base.register(_DummyGenerator())
    try:
        assert base.get_generator("kayitsiz-kind") is not None
    finally:
        # global registry'yi diğer testlere sızdırmamak için temizle.
        base._registry.pop("kayitsiz-kind", None)
