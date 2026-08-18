"""Studio Faz 4 -- Quiz Üreteci (FEATURE_SPEC.md §12) rag/ katmanı.

Foundry Local'a HİÇ dokunulmaz. Bu dosya Faz 4'ün üç sözleşmesini kilitler:

  1. Her sorunun cevabı korpusta DOĞRULANABİLİR: üç tip cevabını korpustan
     birebir alır, dördüncüsünün (short_answer) referans cevabı sadakat
     kapısından geçer (§12.7).
  2. Çeldiriciler LLM'e uydurulmaz; BAŞKA kümelerin gerçek terimleridir ve
     soru chunk'ında geçmedikleri DOĞRULANIR (§12.5).
  3. short_answer bir eşikle doğru/yanlış'a indirgenmez: benzerlik skoru
     gösterilir ve toplam skora KATILMAZ (§12.8).

Korpus 8 chunk: FIDELITY_TERM_DF_MAX_RATIO=0.15 yüzünden bir terimin "ayırt
edici" sayılabilmesi için df/N <= 0.15 olmalı -- 4 chunk'lık bir korpusta
df=1 bile 0.25 verir ve HİÇBİR terim ayırt edici olmaz. 8 chunk'ta df=1 ->
0.125, yani tek chunk'ta geçen özel adlar boşluk adayı olabilir.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from rag import store
from rag.artifacts import base, quiz
from rag.artifacts.store import get_artifact
from rag.topics import Topic, cluster_corpus

# Her chunk TEK bir tam cümledir; hangi kümede hangi tipin kurulabileceği
# böylece TAM olarak öngörülebilir (§12.3 tip tablosu).
CHUNKS = [
    # a.md -- K0 (0°/5°): "SQLite" boşluk adayı
    ("a.md", "Bu projede vektörler SQLite motorunda saklanır ve sorgular hızlanır.", 0),
    ("a.md", "Ikinci parça yalnızca dolgu metni olarak burada durur.", 5),
    # a.md -- K1 (40°/45°): "Foundry" boşluk adayı
    ("a.md", "Sistem yanıtları üretirken Foundry çalışma zamanını kullanır ve modeli yükler.", 40),
    ("a.md", "Dorduncu parça yalnızca dolgu metni olarak burada durur.", 45),
    # b.md -- K2 (90°/95°)
    ("b.md", "Kullanıcı arayüzü Streamlit üzerinde çalışır ve soruları modele iletir.", 90),
    ("b.md", "Altıncı parça yalnızca dolgu metni olarak burada durur.", 95),
    # b.md -- K3 (130°/135°)
    ("b.md", "Vektör benzerliği hesaplanırken Cosine ölçüsü tercih edilir ve sıralama yapılır.", 130),
    ("b.md", "Sekizinci parça yalnızca dolgu metni olarak burada durur.", 135),
]

SA_QUESTION = "Vektörler nerede saklanır?"
SA_ANSWER = "Vektörler yerel bir veritabanında saklanır."
SA_TRAP = "Bu sistem GPT-4 kullanır ve OpenAI sunucularına gönderir."


class _Chunk:
    def __init__(self, content, source, page=1):
        self.content, self.source, self.page, self.via_ocr = content, source, page, False


def _unit(angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [math.cos(a), math.sin(a)]


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _FakeChatClient:
    def __init__(self, answer=SA_ANSWER):
        self.answer = answer
        self.calls = 0

    def complete_chat(self, messages):
        self.calls += 1
        return _response(f"SORU: {SA_QUESTION}\nCEVAP: {self.answer}")


@pytest.fixture()
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture()
def corpus(conn):
    for source in ("a.md", "b.md"):
        rows = [(c, v) for s, c, v in CHUNKS if s == source]
        store.upsert_document(
            conn, source, 1,
            [_Chunk(content, source) for content, _v in rows],
            [_unit(angle) for _c, angle in rows],
        )
    return conn


def _run(corpus, monkeypatch, sa_answer=SA_ANSWER):
    client = _FakeChatClient(sa_answer)
    monkeypatch.setattr("rag.models.get_chat_client", lambda **kwargs: client)
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [_unit(0) for _ in texts]
    )
    events = []
    artifact_id = base.generate_artifact(
        corpus, kind="quiz", scope="corpus", document_id=None, params={},
        emit=lambda name, payload: events.append((name, payload)),
    )
    return SimpleNamespace(
        artifact=get_artifact(corpus, artifact_id), events=events, client=client
    )


def _resolve(payload: dict, node_path: str):
    node = payload
    for token in node_path.split("/")[1:]:
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


# --------------------------------------------------------------------------- cümle seçimi


def test_yarim_cumle_ve_baslik_aday_olmaz():
    """§12.4: chunk'lar KELİME penceresiyle kesiliyor, cümle sınırı korunmuyor.
    Bir chunk'ın ilk "cümlesi" genelde önceki chunk'tan taşan yarım cümledir."""
    text = (
        "belgeleri aramasını ve bulduğu bilgiyi cevaba dahil etmesini sağlar.\n"
        "SQLite ile Yerel Veri Saklama\n"
        "Bu bölüm veritabanı katmanını ve saklama biçimini ayrıntılı olarak anlatır."
    )
    assert quiz._candidate_sentences(text) == [
        "Bu bölüm veritabanı katmanını ve saklama biçimini ayrıntılı olarak anlatır."
    ]


def test_url_iceren_cumle_elenir():
    """§12.4 + AGENTS.md §1.2: URL taşıyan cümle soru olamaz -- hem anlamsız
    boşluk üretiyor hem markdown export'una harici bağlantı sızdırırdı."""
    text = "Ayrıntılar için https://example.com/blog adresine bakabilirsiniz lütfen."
    assert quiz._candidate_sentences(text) == []


def test_scatter_key_deterministik():
    """Aynı korpus aynı quiz'i üretmeli: sıralama anahtarı süreçler arasında
    sabit olmalı (`hash()` PYTHONHASHSEED ile değişir, kullanılmaz)."""
    assert quiz._scatter_key("Streamlit") == quiz._scatter_key("Streamlit")
    assert quiz._scatter_key("Streamlit") != quiz._scatter_key("Cosine")


# --------------------------------------------------------------------------- tip dağılımı


def test_dort_kume_dort_farkli_tip(corpus, monkeypatch):
    """§12.3: tip tablosu küme index'ine göre denenir, kurulabilen ilk tip
    seçilir. Bu korpus dördünü de kurulabilir kılıyor."""
    result = _run(corpus, monkeypatch)
    questions = result.artifact["payload"]["questions"]

    assert len(cluster_corpus(corpus)) == 4
    assert [q["type"] for q in questions] == [
        "multiple_choice", "fill_blank", "true_false", "short_answer",
    ]
    assert [q["topic_id"] for q in questions] == [0, 1, 2, 3]
    assert [q["id"] for q in questions] == ["q0", "q1", "q2", "q3"]
    # LLM YALNIZCA short_answer için çağrıldı.
    assert result.client.calls == 1


def test_bosluk_sorusu_terimi_gizler_cevap_terimin_kendisidir(corpus, monkeypatch):
    """multiple_choice/fill_blank: cevap korpustan BİREBİR gelir, uydurulmaz."""
    result = _run(corpus, monkeypatch)
    questions = result.artifact["payload"]["questions"]

    mc, fb = questions[0], questions[1]
    assert mc["answer"] == "SQLite"
    assert quiz._BLANK in mc["prompt"]
    assert "SQLite" not in mc["prompt"]
    assert mc["evidence"] == CHUNKS[0][1]

    assert fb["answer"] == "Foundry"
    assert quiz._BLANK in fb["prompt"]
    assert fb["choices"] == []  # serbest metin


def test_celdiriciler_baska_kumelerden_gelir_ve_kaynakta_gecmez(corpus, monkeypatch):
    """§12.5: çeldiriciler LLM'e yazdırılmaz; başka kümelerin GERÇEK
    terimleridir ve soru chunk'ında geçmedikleri doğrulanır (yani yanlış
    oldukları kanıtlıdır)."""
    result = _run(corpus, monkeypatch)
    mc = result.artifact["payload"]["questions"][0]
    source_text = CHUNKS[0][1]

    assert len(mc["choices"]) == 4
    assert mc["answer"] in mc["choices"]
    distractors = [c for c in mc["choices"] if c != mc["answer"]]
    assert len(distractors) == 3
    assert set(distractors) == {"Foundry", "Streamlit", "Cosine"}
    for distractor in distractors:
        assert distractor.lower() not in source_text.lower()


def test_true_false_dogru_varyant_gercek_kaynagi_gosterir(corpus, monkeypatch):
    """§12.4: doğruluk değeri METADATA'dan doğrulanabilir -- entailment
    yargısı değil."""
    result = _run(corpus, monkeypatch)
    tf = result.artifact["payload"]["questions"][2]

    assert tf["answer"] == "true"
    assert tf["choices"] == ["true", "false"]
    assert tf["source"] in tf["prompt"]  # gerçek belgeye atfediliyor
    assert tf["evidence"] in tf["prompt"]


def test_true_false_yanlis_varyant_baska_belgeye_atfeder():
    """Tek chunk üzerinde doğrudan kurulur: tek sayılı küme kimliği YANLIŞ
    varyantı seçer ve cümle o belgede GEÇMEDİĞİ doğrulanır."""
    row = {"id": 1, "source": "a.md", "page": 1,
           "content": CHUNKS[0][1], "via_ocr": 0}
    topic = Topic(id=1, chunk_ids=[1], centroid=None, size=1)
    question = quiz._build_true_false_question(
        topic, [row], set(), {"a.md": CHUNKS[0][1], "b.md": "Tamamen farklı bir metin."}
    )

    assert question["answer"] == "false"
    assert "b.md belgesinde geçiyor" in question["prompt"]
    assert question["source"] == "a.md"     # GERÇEK kaynak korunur
    assert question["evidence"] == CHUNKS[0][1]


def test_true_false_tek_belgede_kurulamaz():
    """Yanlış atıf için başka belge yoksa tip kurulmaz (None) -- kurgu
    doğrulanamaz olurdu."""
    row = {"id": 1, "source": "a.md", "page": 1,
           "content": CHUNKS[0][1], "via_ocr": 0}
    topic = Topic(id=1, chunk_ids=[1], centroid=None, size=1)
    assert quiz._build_true_false_question(
        topic, [row], set(), {"a.md": CHUNKS[0][1]}
    ) is None


# --------------------------------------------------------------------------- sadakat kapısı


def test_short_answer_iddiasi_modelin_cevabidir(corpus, monkeypatch):
    """§12.7: kapı, modelin UYDURMUŞ olabileceği metni korumalı. short_answer'da
    bu referans cevaptır; diğer üçünde korpustan alınan cümledir."""
    result = _run(corpus, monkeypatch)
    artifact = result.artifact
    payload = artifact["payload"]

    paths = {c["node_path"]: c["claim_text"] for c in artifact["claims"]}
    assert paths["/questions/3/answer"] == SA_ANSWER
    assert paths["/questions/0/evidence"] == CHUNKS[0][1]
    for node_path, text in paths.items():
        assert _resolve(payload, node_path) == text


def test_dogrulanamayan_referans_cevap_soruyu_dusurur(corpus, monkeypatch):
    """Tuzak referans cevap ("GPT-4"/"OpenAI" korpusta hiç geçmiyor) ikinci
    katmandan düşer; soru quiz'e ALINMAZ, sayısı gösterilir."""
    result = _run(corpus, monkeypatch, sa_answer=SA_TRAP)
    payload = result.artifact["payload"]

    assert [q["type"] for q in payload["questions"]] == [
        "multiple_choice", "fill_blank", "true_false",
    ]
    assert len(payload["dropped"]) == 1
    dropped = payload["dropped"][0]
    assert dropped["reason"] == "unverified_terms"
    assert "gpt-4" in dropped["terms"]
    # `text` DOĞRULANAMAYAN metnin kendisidir (modelin referans cevabı), soru
    # gövdesi değil -- hangi metnin düştüğü kayıttan silinmez (§12.7).
    assert dropped["text"] == SA_TRAP
    assert dropped["prompt"] == SA_QUESTION
    # Soru quiz'e alınmadı.
    assert all(SA_QUESTION != q["prompt"] for q in payload["questions"])


# --------------------------------------------------------------------------- puanlama


def _payload(*questions):
    return {"kind": "quiz", "questions": list(questions), "dropped": []}


def _question(qid, qtype, answer, choices=()):
    return {
        "id": qid, "type": qtype, "topic_id": 0, "prompt": "?",
        "choices": list(choices), "answer": answer, "chunk_id": 1,
        "source": "a.md", "citation": "[Kaynak: a.md s.1]", "evidence": "gerekçe",
    }


def test_deterministik_puanlama_tam_eslesme():
    payload = _payload(
        _question("q0", "multiple_choice", "SQLite", ["SQLite", "Foundry"]),
        _question("q1", "true_false", "false", ["true", "false"]),
        _question("q2", "fill_blank", "Foundry"),
    )
    scored = quiz.score_attempt(payload, {"q0": "SQLite", "q1": "true", "q2": "Foundry"})

    assert [r["correct"] for r in scored["results"]] == [True, False, True]
    assert scored["correct_count"] == 2
    assert scored["deterministic_total"] == 3
    assert scored["score"] == pytest.approx(2 / 3)
    assert scored["similarity_total"] == 0


def test_normalize_turkce_buyuk_i_tuzagini_asar():
    """Düz str.lower() 'İ' için BİRLEŞEN NOKTA üretir ve karşılaştırma sessizce
    başarısız olur (fidelity._term_lower'da kayıtlı aynı tuzak)."""
    payload = _payload(_question("q0", "fill_blank", "İstanbul"))
    scored = quiz.score_attempt(payload, {"q0": "istanbul"})
    assert scored["results"][0]["correct"] is True

    payload = _payload(_question("q0", "fill_blank", "SQLite"))
    assert quiz.score_attempt(payload, {"q0": " sqlite. "})["results"][0]["correct"] is True


def test_cevapsiz_soru_yanlis_sayilir_hata_degil():
    payload = _payload(_question("q0", "fill_blank", "Foundry"))
    scored = quiz.score_attempt(payload, {})
    assert scored["results"][0]["correct"] is False
    assert scored["results"][0]["given"] is None


def test_short_answer_benzerlik_skoru_toplam_puana_KATILMAZ(monkeypatch):
    """§12.8 / STUDIO_PLAN §6.3: short_answer bir EŞİKLE doğru/yanlış'a
    indirgenmez. `correct` None kalır, skor yalnızca deterministik sorulardan
    hesaplanır."""
    vectors = {"kullanıcı cevabı": _unit(30), SA_ANSWER: _unit(0)}
    monkeypatch.setattr(
        "rag.models.embed_texts",
        lambda texts, is_query=False: [vectors[t] for t in texts],
    )
    payload = _payload(
        _question("q0", "fill_blank", "Foundry"),
        _question("q1", "short_answer", SA_ANSWER),
    )
    scored = quiz.score_attempt(payload, {"q0": "Foundry", "q1": "kullanıcı cevabı"})

    short = scored["results"][1]
    assert short["correct"] is None
    assert short["similarity"] == pytest.approx(math.cos(math.radians(30)), abs=1e-6)
    assert scored["deterministic_total"] == 1
    assert scored["similarity_total"] == 1
    assert scored["score"] == pytest.approx(1.0)  # yalnızca q0'dan


def test_yalnizca_short_answer_varsa_skor_none(monkeypatch):
    """Deterministik soru yoksa 0.0 yazmak "hepsini yanlış yaptı" demek olurdu."""
    monkeypatch.setattr(
        "rag.models.embed_texts", lambda texts, is_query=False: [_unit(0) for _ in texts]
    )
    payload = _payload(_question("q0", "short_answer", SA_ANSWER))
    scored = quiz.score_attempt(payload, {"q0": "bir şey"})
    assert scored["score"] is None
    assert scored["deterministic_total"] == 0


# --------------------------------------------------------------------------- ilerleme + export


def test_progress_olaylari_tam_sayi(corpus, monkeypatch):
    result = _run(corpus, monkeypatch)
    progress = [p for name, p in result.events if name == "progress"]
    assert [p["pct"] for p in progress] == [25, 50, 75, 100]
    assert all(isinstance(p["pct"], int) for p in progress)


def test_markdown_sorular_ve_ayri_cevap_anahtari(corpus, monkeypatch):
    """§12.9: cevap anahtarı AYRI bölümde (çıktı çalışma kâğıdı olarak da
    kullanılabilsin) ve hiçbir http(s):// yok."""
    result = _run(corpus, monkeypatch)
    text = quiz.to_markdown(result.artifact["payload"])

    assert "http://" not in text and "https://" not in text
    assert "## Sorular" in text
    assert "## Cevap Anahtarı" in text
    assert text.index("## Sorular") < text.index("## Cevap Anahtarı")
    assert "SQLite" in text.split("## Cevap Anahtarı")[1]
    # true_false şıkları kullanıcıya Türkçe gösterilir; payload kanonik kalır.
    assert "- Doğru" in text and "- Yanlış" in text
