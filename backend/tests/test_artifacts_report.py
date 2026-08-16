"""Studio Faz 2 -- Rapor Üreteci (FEATURE_SPEC.md §10) rag/ katmanı.

Foundry Local'a HİÇ dokunulmaz: chat client de embedding de monkeypatch'lenir
(conftest.py deseni). Bu dosya TEK bir soruyu regresyona kilitler: rapora
giren her cümle bir chunk'a bağlı mı, bağlanamayan/doğrulanamayan cümle
gerçekten rapordan ÇIKIYOR mu (§10.14 ürün kriterleri).

Korpus kasıtlı olarak TEK bir cümleyi tekrar eder: böylece gerçek içerik
terimlerinin doküman frekansı 1.0'a çıkar (ayırt edici sayılmazlar,
FIDELITY_TERM_DF_MAX_RATIO=0.15) ve terim katmanının TEK tetikleyicisi
korpusta hiç geçmeyen tuzak terimleri ("gpt-4", "openai") olur -- testin
düşürme sebebi belirsiz kalmaz.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from rag import config, store
from rag.artifacts import base, report
from rag.artifacts.fidelity import ClaimBinding, should_drop, unverified_terms

# Korpusun tamamında geçen cümle -- tüm terimleri df=1.0, yani AYIRT EDİCİ DEĞİL.
CORPUS_TEXT = "sqlite veritabanı float32 blob olarak saklar ve bölümleri korur"

# Rapora giren cümleler yalnızca korpus sözcüklerinden kurulur.
KEPT_FINDINGS = "sqlite veritabanı float32 blob olarak saklar."
KEPT_DETAIL = "Bölümleri korur ve blob olarak saklar."
KEPT_EXEC = "sqlite veritabanı bölümleri korur."

# Tuzak: konuya yakın ama korpusta HİÇ geçmeyen özel adlar taşıyor.
TRAP = "Bu sistem varsayılan olarak GPT-4 kullanır ve verileri OpenAI sunucularına gönderir."

# Hiçbir chunk'a bağlanamayan iddia (cos = -1).
UNSUPPORTED = "Bölümleri korur ama başka bir yöne bakar."


class _Chunk:
    def __init__(self, content, source="a.md", page=1):
        self.content, self.source, self.page, self.via_ocr = content, source, page, False


def _unit(angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _FakeChatClient:
    """`complete_chat(messages)` -- SDK'nın gerçek imzası (§10.2'de ölçüldü:
    çağrı başına ayar ALMIYOR)."""

    def __init__(self, texts):
        self.texts = list(texts)
        self.contexts = []

    def complete_chat(self, messages):
        self.contexts.append(messages[0]["content"])
        return _response(self.texts.pop(0) if self.texts else "Bölümleri korur.")


@pytest.fixture()
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture()
def corpus(conn):
    """İki belge x iki chunk; açılar iki kümeye ayrılacak şekilde seçildi."""
    store.upsert_document(
        conn, "a.md", 1,
        [_Chunk(CORPUS_TEXT, source="a.md"), _Chunk(CORPUS_TEXT, source="a.md")],
        [_unit(0), _unit(5)],
    )
    store.upsert_document(
        conn, "b.md", 1,
        [_Chunk(CORPUS_TEXT, source="b.md"), _Chunk(CORPUS_TEXT, source="b.md")],
        [_unit(90), _unit(95)],
    )
    return conn


@pytest.fixture()
def generated(corpus, monkeypatch):
    """Gerçek hattı (base.generate_artifact) sahte modelle uçtan uca koşar."""
    client = _FakeChatClient(
        [
            KEPT_FINDINGS,                 # 1) Temel Bulgular
            f"{KEPT_DETAIL} {TRAP}",       # 2) detay-0: biri kalır, biri düşer
            UNSUPPORTED,                   # 3) detay-1: tamamı düşer
            KEPT_EXEC,                     # 4) Yönetici Özeti (EN SON)
        ]
    )
    monkeypatch.setattr("rag.models.get_chat_client", lambda **kwargs: client)

    vectors = {
        KEPT_FINDINGS: _unit(0),
        KEPT_DETAIL: _unit(0),
        KEPT_EXEC: _unit(0),
        TRAP: _unit(0),          # grounded ÇIKAR -- pin korunur, düşürmeyi terim katmanı yapar
        UNSUPPORTED: _unit(180),  # cos=-1 -> unsupported
    }
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [vectors[t] for t in texts]
    )

    events = []
    artifact_id = base.generate_artifact(
        corpus, kind="report", scope="corpus", document_id=None, params={},
        emit=lambda name, payload: events.append((name, payload)),
    )
    from rag.artifacts.store import get_artifact

    return SimpleNamespace(
        artifact=get_artifact(corpus, artifact_id), events=events, client=client
    )


def _resolve(payload: dict, node_path: str):
    """RFC 6901 JSON pointer çözümü -- node_path'in payload'da GERÇEKTEN
    çözüldüğünü kanıtlar (§10.5)."""
    node = payload
    for token in node_path.split("/")[1:]:
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


# --------------------------------------------------------------------------- yardımcılar


def test_sample_evenly_ilk_n_almaz():
    """§10.4: küme chunk'ları limiti aşarsa EŞİT ARALIKLI örneklenir."""
    assert report._sample_evenly([1, 2, 3], 5) == [1, 2, 3]
    assert report._sample_evenly([1, 2, 3, 4, 5], 3) == [1, 3, 5]
    assert report._sample_evenly([1, 2, 3, 4, 5], 1) == [1]


def test_split_paragraphs_kaynak_etiketini_temizler():
    """Model sızdırırsa [Kaynak: ...] cümleye bölünmeden ÖNCE temizlenir --
    atıflar deterministik olarak citations'tan gelir (§10.8)."""
    paragraphs = report._split_paragraphs(
        "Birinci cümle [Kaynak: a.md s.1]. İkinci cümle.\n\nİkinci paragraf."
    )
    assert paragraphs == [["Birinci cümle .", "İkinci cümle."], ["İkinci paragraf."]]


def test_unverified_terms_turkce_kucultme_ve_alt_dize(corpus):
    """§10.6 kural 2 ve 5: 'İ' birleşen nokta üretmez; Türkçe eki alt dize
    eşleşmesiyle geçilir."""
    chunk_ids = [r["id"] for r in corpus.execute("SELECT id FROM chunks")]
    # "Bölüm" korpusta yalnızca "bölümleri" olarak geçiyor: df=0 -- ama alt
    # dize olarak bulunuyor, doğrulanmış sayılır (Türkçe ekini sözlüksüz
    # geçmenin tek yolu).
    assert unverified_terms(corpus, "Bu Bölüm blob saklar.", chunk_ids) == []
    assert unverified_terms(corpus, TRAP, chunk_ids) != []
    # "OpenAI" -> "openaı": Türkçe-duyarlı küçültme I'yı ı yapar (kural 2).
    assert "gpt-4" in unverified_terms(corpus, TRAP, chunk_ids)
    assert "openaı" in unverified_terms(corpus, TRAP, chunk_ids)
    # "İSTANBUL" cümle başı DEĞİL -> büyük harf özel ad işareti sayılır.
    assert "istanbul" in unverified_terms(corpus, "Bu şehir İSTANBUL kadar büyük.", chunk_ids)


def test_unverified_terms_yalnizca_varlik_benzeri_terimleri_kontrol_eder(corpus):
    """§10.6 kural 4b -- Faz 2 kapanma ölçümünün getirdiği şart.

    ÖLÇÜLDÜ (eval.db, gerçek üretilmiş rapor, 47 cümle): yalnız df'ye bakan
    biçim 42 cümleyi düşürüyordu; 20 chunk'lık korpusta sıradan Türkçe çekim de
    df=0 alıyor ve hallüsinasyondan ayrılamıyor. Varlık şartıyla 43/47 cümle
    rapora girdi ve tuzak yalnızca doğru iki terimle düştü.
    """
    chunk_ids = [r["id"] for r in corpus.execute("SELECT id FROM chunks")]
    # Sıradan sözcükler: korpusta hiç geçmiyor (df=0) ama özel ad/kimlik değil.
    assert unverified_terms(corpus, "Bu yöntem kesinlikle dayanır.", chunk_ids) == []
    # Cümle başındaki büyük harf özel ad işareti DEĞİL (her cümle öyle başlar).
    assert unverified_terms(corpus, "Ankara blob saklar.", chunk_ids) == []
    # Rakam taşıyan token, büyük harfi olmasa da kontrol edilir -- modelin
    # uydurduğu sayı (gerçek koşumda: "200-400 kelime") böyle yakalandı.
    assert unverified_terms(corpus, "Her parça 200-400 kelime tutar.", chunk_ids) == ["200-400"]
    # RAKAMSIZ tire varlık işareti DEĞİL: "soru-cevap" Türkçe birleşik sözcük,
    # model kimliği değil. Üretim korpusunda 4 yanlış pozitif üretmişti (§10.6).
    assert unverified_terms(corpus, "Bu bir soru-cevap sistemidir.", chunk_ids) == []


def test_unverified_terms_bos_baglam_muafiyet_degil(corpus):
    """§10.6: context_chunk_ids boş gelirse katman sessizce KAPANMAZ."""
    assert unverified_terms(corpus, TRAP, []) != []


def test_should_drop_kapali_kume():
    """§10.6 tablosu -- dört satırın dördü."""
    grounded = ClaimBinding("/n/0", "x", 1, 0.55, "grounded")
    assert should_drop(grounded, []) is None
    assert should_drop(grounded, ["gpt-4"]) == "unverified_terms"
    assert should_drop(ClaimBinding("/n/1", "x", 1, 0.40, "weak"), []) == "weak"
    assert should_drop(ClaimBinding("/n/2", "x", None, None, "unsupported"), []) == "unsupported"


# --------------------------------------------------------------------------- uçtan uca üretim


def test_rapor_bolum_sirasi_ve_kimlikleri(generated):
    """§10.3: sections HER ZAMAN exec ile başlar, findings 1., detay'lar küme
    sırasında -- exec EN SON üretilse bile."""
    payload = generated.artifact["payload"]
    assert payload["kind"] == "report"
    assert payload["outline"] == [
        "executive_summary", "key_findings", "detailed_analysis", "tables", "citations",
    ]
    ids = [s["id"] for s in payload["sections"]]
    assert ids[0] == "exec"
    assert ids[1] == "findings"
    assert all(i.startswith("detail-") for i in ids[2:])
    kinds = [s["kind"] for s in payload["sections"]]
    assert kinds[:2] == ["executive_summary", "key_findings"]
    # tables/citations sections dizisinde DEĞİL, payload'ın üst düzey alanları.
    assert "tables" not in kinds and "citations" not in kinds


def test_her_iddia_bir_claim_satiri_ve_cozulebilir_node_path(generated):
    """§10.14 birinci ürün kriteri: rapora giren her cümlenin artifact_claims
    satırı VAR ve node_path'i payload'da GERÇEKTEN çözülüyor."""
    payload = generated.artifact["payload"]
    claims = generated.artifact["claims"]

    sentences = [
        (f"/sections/{i}/paragraphs/{j}/sentences/{k}", sentence)
        for i, section in enumerate(payload["sections"])
        for j, paragraph in enumerate(section["paragraphs"])
        for k, sentence in enumerate(paragraph["sentences"])
    ]
    by_path = {c["node_path"]: c for c in claims}
    for node_path, sentence in sentences:
        assert node_path in by_path
        assert by_path[node_path]["claim_text"] == sentence
        assert _resolve(payload, node_path) == sentence
        assert by_path[node_path]["chunk_id"] is not None

    # Düşürülenler de payload'da çözülür -- ama /dropped altında.
    for i, item in enumerate(payload["dropped"]):
        assert _resolve(payload, f"/dropped/{i}") == item
        assert by_path[f"/dropped/{i}"]["claim_text"] == item["text"]


def test_tuzak_dusuruldu_ve_gövdede_gecmiyor(generated):
    """§10.14: doğrulanamayan iddia rapordan ÇIKARILMIŞ; metni gövdede yok."""
    payload = generated.artifact["payload"]
    trap = next(d for d in payload["dropped"] if d["text"] == TRAP)
    assert trap["reason"] == "unverified_terms"
    assert "gpt-4" in trap["terms"] and "openaı" in trap["terms"]  # I -> ı (§10.6 kural 2)
    assert trap["score"] >= config.FIDELITY_MIN_SCORE  # grounded ÇIKTI, pin korunuyor

    body = " ".join(
        sentence
        for section in payload["sections"]
        for paragraph in section["paragraphs"]
        for sentence in paragraph["sentences"]
    ).lower()
    assert "gpt" not in body and "openai" not in body

    # Bağlanamayan iddia da düşer, sebebi AYRI.
    unsupported = next(d for d in payload["dropped"] if d["text"] == UNSUPPORTED)
    assert unsupported["reason"] == "unsupported"
    assert unsupported["terms"] == []


def test_fidelity_score_oran_ve_dropped_ayri_sayilar(generated):
    """§10.6: tuzak fidelity_score'da grounded SAYILIR (boşluk gizlenmez) ve
    aynı anda dropped listesinde YER ALIR (ürün onu yayımlamaz)."""
    artifact = generated.artifact
    claims = artifact["claims"]
    grounded = sum(1 for c in claims if c["verdict"] == "grounded")
    assert artifact["fidelity_score"] == pytest.approx(grounded / len(claims))
    trap_claim = next(c for c in claims if c["claim_text"] == TRAP)
    assert trap_claim["verdict"] == "grounded"
    assert TRAP in [d["text"] for d in artifact["payload"]["dropped"]]


def test_citations_yalnizca_rapora_giren_iddialardan(generated):
    """§10.8: düşürülen iddianın kaynağı rapora kaynak GÖSTERİLMEZ."""
    payload = generated.artifact["payload"]
    kept_chunk_ids = {
        c["chunk_id"]
        for c in generated.artifact["claims"]
        if c["node_path"].startswith("/sections/")
    }
    cited = {c["chunk_id"] for c in payload["citations"]}
    assert cited == kept_chunk_ids
    assert payload["citations"] == sorted(
        payload["citations"], key=lambda c: (c["source"], c["page"] or 0)
    )
    assert payload["citations"][0]["citation"] == f"[Kaynak: {payload['citations'][0]['source']} s.1]"


def test_coverage_tablosu_deterministik(generated):
    """§10.7: tek tablo, tamamen metadatadan; satır toplamı chunk sayısıdır."""
    tables = generated.artifact["payload"]["tables"]
    assert [t["id"] for t in tables] == ["coverage"]
    table = tables[0]
    assert table["columns"][0] == "Belge"
    assert [row[0] for row in table["rows"]] == ["a.md", "b.md"]
    assert all(sum(row[1:]) == 2 for row in table["rows"])


def test_exec_baglami_diger_bolumlerin_birlesimi(generated):
    """§10.4: Yönetici Özeti'nin kendi chunk'ı yok; bağlamı diğer bölümlerin
    bağlam chunk'larının BİRLEŞİMİ."""
    sections = {s["id"]: s for s in generated.artifact["payload"]["sections"]}
    others = set()
    for section_id, section in sections.items():
        if section_id != "exec":
            others |= set(section["context_chunk_ids"])
    assert set(sections["exec"]["context_chunk_ids"]) == others


def test_progress_olaylari_bolum_basina_yayilir(generated):
    """§10.11: 12 çağrılık üretimde ilerleme zorunlu; pct 0-100 TAM SAYI."""
    progress = [p for name, p in generated.events if name == "progress"]
    # 1 findings + 2 küme + 1 exec
    assert len(progress) == 4
    assert [p["pct"] for p in progress] == [25, 50, 75, 100]
    assert all(isinstance(p["pct"], int) for p in progress)
    assert progress[-1]["detail"] == "4/4 bölüm yazıldı"


def test_bolum_baglami_build_context_bicimini_kullanir(generated):
    """§10.4: bölüm bağlamı retrieve.build_context ile AYNI biçimde verilir --
    iki ayrı bağlam biçimi iki ayrı prompt davranışı demek olurdu."""
    findings_prompt = generated.client.contexts[0]
    assert "[1] [Kaynak: a.md s.1]" in findings_prompt
    assert "[2] [Kaynak: b.md s.1]" in findings_prompt
    # Exec'in bağlamı chunk DEĞİL, üretilmiş bölüm metnidir.
    assert KEPT_DETAIL in generated.client.contexts[-1]


def test_detay_basligi_belgeden_deterministik_turer(generated):
    """§10.3: küme etiketleme Faz 3'ün işi; Faz 2 başlığı '{belge} (n bölüm)'."""
    titles = [
        s["title"] for s in generated.artifact["payload"]["sections"]
        if s["kind"] == "detailed_analysis"
    ]
    assert sorted(titles) == ["a.md (2 bölüm)", "b.md (2 bölüm)"]


# --------------------------------------------------------------------------- markdown


def test_to_markdown_dusurulen_metni_gecmez_harici_kaynak_yok(generated):
    """§10.12: düşürülen iddianın METNİ değil yalnızca SAYISI dipnot olur;
    çıktı hiçbir http(s):// üretmez (CLAUDE.md §1.2)."""
    md = report.to_markdown(generated.artifact["payload"])
    assert "http://" not in md and "https://" not in md
    assert TRAP not in md and UNSUPPORTED not in md
    assert "2 iddia" in md  # tuzak + bağlanamayan
    assert KEPT_EXEC in md
    assert "## Yönetici Özeti" in md
    assert "## Kaynaklar" in md
    assert "| Belge |" in md


def test_to_markdown_bos_payload_patlamaz():
    assert report.to_markdown({}) == "\n"
