"""
Quiz Üreteci -- Studio Faz 4 (FEATURE_SPEC.md §12).

STUDIO_PLAN §6.3'ün tespiti doğru: zor kısım soru üretimi değil, ÇELDİRİCİ
üretimidir. Bu modül planın "hibrit" fikrini bir adım daha ileri götürür ve
çeldiricileri LLM'e HİÇ yazdırmaz -- çeldirici havuzu BAŞKA kümelerin
chunk'larından çıkarılmış GERÇEK korpus terimleridir. Gerekçe ölçümle birlikte
§12.5'te; özeti: LLM'e "makul ama yanlış bir şık yaz" demek, doğrulanamayan bir
iddiayı cevap anahtarına koymaktır -- kapı grounding ölçüyor, entailment değil
(§9.6'nın bilinen sınırı).

Dört soru tipinin üçü TAMAMEN DETERMİNİSTİK (LLM çağrısı yok):
    multiple_choice : korpus cümlesinde ayırt edici terim boşaltılır,
                      çeldiriciler başka kümelerin gerçek terimleri
    fill_blank      : aynı boşluk, serbest metin cevabı
    true_false      : cümle + KAYNAK ATFI ("bu bilgi X belgesinde geçiyor")
                      -- doğruluk değeri metadata'dan DOĞRULANABİLİR
    short_answer    : TEK LLM adımı (soru + referans cevap)

Tip küme başına SABİT değildir: her küme için tipler deterministik bir sırada
denenir, KURULABİLEN ilk tip seçilir (§12.3). Ölçüldü (§12.4): entity benzeri
boşluk adayı eval.db'de 7 kümenin yalnızca 2'sinde, rag.db'de 10 kümenin
6'sında var -- tipi zorlamak, kurulamayan soru demek olurdu.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from typing import Optional

from .. import config, models
from ..retrieve import Hit, build_context
from ..topics import Topic
from .base import GeneratedArtifact, GenerationContext, register
from .fidelity import bind_claims, distinctive_terms, should_drop, unverified_terms

# --------------------------------------------------------------------------- cümle seçimi

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n|\n")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_URL_RE = re.compile(r"https?://", re.IGNORECASE)

# Bir soru gövdesi olabilecek cümlenin sınırları. İkisi de ÖLÇÜMDEN geldi
# (§12.4 sondası) ve prompt metnindeki "en fazla N kelime" sınırlarıyla aynı
# sınıfta -- config sabiti olmazlar:
#   - alt sınır: 8 kelimeden kısa "cümleler" bu korpusta madde başlığı çıkıyor
#   - üst sınır: PDF metninde noktalama olmadan akan 100+ kelimelik satırlar var
_SENTENCE_MIN_WORDS = 8
_SENTENCE_MAX_WORDS = 40

# Boşluk işareti. Kullanıcıya gösterilir, cevapla karşılaştırılmaz.
_BLANK = "_____"


def _candidate_sentences(text: str) -> list[str]:
    """Chunk metninden SORU GÖVDESİ olabilecek cümleler.

    Dört eleme, dördü de ÖLÇÜLMÜŞ bir sorunu çözüyor (§12.4 sondaları):
      1. Cümle nokta/ünlem/soru ile BİTMELİ -- başlık satırları ("SQLite ile
         Yerel Veri Saklama") bitmiyor ve ilk sondada boşluk adayı olarak
         seçilip "Saklama" gibi anlamsız boşluklar üretiyordu.
      2. Cümle BÜYÜK HARF ya da rakamla BAŞLAMALI. Chunking kelime penceresiyle
         çalışıyor (CHUNK_WORDS=130, sayfa sınırı korunur ama CÜMLE sınırı
         korunmaz), bu yüzden bir chunk'ın ilk "cümlesi" neredeyse her zaman
         bir önceki chunk'tan taşan YARIM cümledir. Kuru koşumda üretilen
         soru buydu: «belgeleri aramasını ve bulduğu bilgiyi cevaba dahil
         etmesini sağlar.» -- doğru bir alıntı ama okunmaz bir soru.
      3. Uzunluk sınırları (yukarıda).
      4. http(s):// içeren satır ELENİR. İki sebep: PDF'teki URL satırından
         çıkan boşluk ("4501968", bir blog kimliği) anlamsız bir soru üretiyor
         VE markdown export'una URL sızdırırdı -- CLAUDE.md §1.2'nin "harici
         kaynak yok" grep kontrolünü kıran tek yol budur.
    """
    out: list[str] = []
    for paragraph in _PARAGRAPH_SPLIT_RE.split(text or ""):
        for sentence in _SENTENCE_SPLIT_RE.split(paragraph.strip()):
            sentence = sentence.strip()
            if not sentence.endswith((".", "!", "?")):
                continue
            first = sentence[0]
            if not (first.isdigit() or (first.isalpha() and first == first.upper())):
                continue
            if _URL_RE.search(sentence):
                continue
            words = len(sentence.split())
            if _SENTENCE_MIN_WORDS <= words <= _SENTENCE_MAX_WORDS:
                out.append(sentence)
    return out


def _chunk_rows(conn: sqlite3.Connection, chunk_ids: list[int]) -> list[sqlite3.Row]:
    """chunk_ids sırasını KORUYARAK satırları döner."""
    if not chunk_ids:
        return []
    placeholders = ",".join("?" for _ in chunk_ids)
    rows = conn.execute(
        f"SELECT id, source, page, content, via_ocr FROM chunks WHERE id IN ({placeholders})",
        chunk_ids,
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


def _citation_for(row: sqlite3.Row) -> str:
    """retrieve.Hit.citation() ile BİREBİR aynı biçim -- yeniden üretilmez."""
    return Hit(
        score=0.0, source=row["source"], page=row["page"],
        content=row["content"], via_ocr=bool(row["via_ocr"]),
    ).citation()


# --------------------------------------------------------------------------- terim havuzu

def _corpus_terms(
    conn: sqlite3.Connection,
) -> tuple[dict[int, list[tuple[str, str]]], dict[str, int]]:
    """TEK geçişte: chunk_id -> [(ham, token)] ve token -> doküman frekansı.

    `distinctive_terms` her çağrısında korpus df'sini yeniden hesaplıyor
    (fidelity.py'de kayıtlı: tek bir iddia için birkaç milisaniye). Quiz onu
    chunk BAŞINA çağırdığı için maliyet ölçüldü: 61 chunk'lık üretim
    korpusunda 0.11 sn. Küme başına yeniden hesaplansaydı 10 kat olurdu --
    bu yüzden tek geçiş burada yapılır ve sonuç aşağıya taşınır.

    En NADİR terim en iyi boşluktur; df bu sıralamayı verir (§12.4).
    """
    by_chunk: dict[int, list[tuple[str, str]]] = {}
    df: dict[str, int] = {}
    for row in conn.execute("SELECT id, content FROM chunks"):
        terms = distinctive_terms(conn, row["content"])  # metin içinde tekilleştirilmiş
        by_chunk[row["id"]] = terms
        for _raw, token in terms:
            df[token] = df.get(token, 0) + 1
    return by_chunk, df


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _scatter_key(text: str) -> str:
    """Deterministik ama alfabetik OLMAYAN sıralama anahtarı.

    Neden gerekli (kuru koşumda görüldü): çeldirici havuzu (df, alfabetik) ile
    sıralanınca df=1 olan onlarca terim arasında ilk üç HEP "A" ile başlıyordu
    -- şıklar ['After', 'Apple', 'Approach', 'Internet'] çıktı ve doğru cevap
    tek başına göze battı. Aynı sorun şık sırasında da var: alfabetik sıra
    doğru cevabı sistematik olarak belli bir konuma iter.

    `hash()` KULLANILMAZ: PYTHONHASHSEED süreç başına rastgeledir, aynı korpus
    farklı koşumlarda farklı quiz üretirdi (determinizm sözleşmesi, §9.4).
    sha256 hem deterministik hem dağınıktır.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pick_blank_term(
    conn: sqlite3.Connection, sentence: str, df: dict[str, int]
) -> Optional[tuple[str, str]]:
    """Cümlenin boşaltılacak terimi: EN NADİR ayırt edici terim.

    "Ayırt edici" tanımı fidelity.distinctive_terms'ten gelir (tek doğruluk
    kaynağı, CLAUDE.md §1.3): rakam taşıyan ya da cümle başı olmayan büyük harf
    taşıyan, korpusta seyrek geçen terim. Bu tanım quiz için de DOĞRU tanımdır
    ve gevşetilmedi: sıradan bir Türkçe çekimi ("yaklaştıkça") boşaltmak,
    eşanlamlısı da doğru olan bir soru üretir ve TAM EŞLEŞME puanlaması onu
    haksız yere yanlış sayardı (§12.6 -- eşanlamlı sözlüğü reddedildi).

    Eşitlikte alfabetik en küçük token kazanır (determinizm).
    """
    candidates = distinctive_terms(conn, sentence)
    if not candidates:
        return None
    return min(candidates, key=lambda rt: (df.get(rt[1], 0), rt[1]))


def _blank_out(sentence: str, raw_term: str) -> str:
    """Terimin cümledeki İLK geçtiği yeri boşlukla değiştirir (ham yazımla)."""
    return sentence.replace(raw_term, _BLANK, 1)


def _distractors(
    answer_raw: str,
    pool: list[tuple[str, int]],
    source_text: str,
    count: int,
) -> list[str]:
    """Çeldiriciler: BAŞKA kümelerin gerçek korpus terimleri (§12.5).

    Üç filtre:
      1. Cevabın kendisi (küçük harfe indirgenmiş karşılaştırma) elenir.
      2. Soru chunk'ının metninde GEÇEN terim elenir -- STUDIO_PLAN §6.3'ün
         "çeldirici kaynak chunk'ta doğru cevap olarak geçiyorsa ELENİR"
         kuralı; bu, çeldiricinin YANLIŞ olduğunun doğrulamasıdır.
      3. BİÇİM eşleşmesi tercih edilir: cevap rakam taşıyorsa rakamlı
         adaylar öne alınır. Aksi halde şıklardan biri (tek sayısal seçenek)
         göze batar ve soru cevabın kendisini ele verir.

    Havuz sırası: df ARTAN (en nadir terim en makul çeldirici), eşitlikte
    içerik hash'i (bkz. _scatter_key) -- deterministik ama alfabetik değil.
    """
    answer_lower = answer_raw.lower()
    source_lower = source_text.lower()
    same_shape: list[str] = []
    other_shape: list[str] = []
    seen: set[str] = set()
    for raw, _df in pool:
        lowered = raw.lower()
        if lowered == answer_lower or lowered in seen:
            continue
        if lowered in source_lower:
            continue
        seen.add(lowered)
        if _has_digit(raw) == _has_digit(answer_raw):
            same_shape.append(raw)
        else:
            other_shape.append(raw)
    return (same_shape + other_shape)[:count]


# --------------------------------------------------------------------------- LLM (yalnızca short_answer)

_QUESTION_PROMPT = """Sen yerel bir belge asistanısın. Aşağıdaki belge parçasına \
dayanarak Türkçe TEK bir soru ve o sorunun cevabını yaz.

Kurallar:
- Cevabı yalnızca bu parçadan çıkarılabilecek bir soru sor.
- Kendi bilgini ekleme, sayı uydurma.
- Kaynak numarası, dosya adı veya [Kaynak: ...] etiketi YAZMA.
- Cevap en fazla 2 cümle olsun.
- Tam olarak iki satır yaz, başka hiçbir şey yazma:
SORU: <soru cümlesi>
CEVAP: <cevap>

Parça:
{context}"""

_SORU_RE = re.compile(r"^\s*SORU\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_CEVAP_RE = re.compile(r"^\s*CEVAP\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _generate_short_answer(client, context: str) -> Optional[tuple[str, str]]:
    """(soru, referans cevap) döner; model biçimi tutturamazsa None."""
    response = client.complete_chat(
        [
            {"role": "system", "content": _QUESTION_PROMPT.format(context=context)},
            {"role": "user", "content": "Soruyu ve cevabını yaz."},
        ]
    )
    text = (response.choices[0].message.content or "").strip()
    question = _SORU_RE.search(text)
    answer = _CEVAP_RE.search(text)
    if question is None or answer is None:
        return None
    q, a = question.group(1).strip(" *_`\""), answer.group(1).strip(" *_`\"")
    return (q, a) if q and a else None


# --------------------------------------------------------------------------- soru kurucular

def _build_blank_question(
    conn: sqlite3.Connection,
    topic: Topic,
    rows: list[sqlite3.Row],
    df: dict[str, int],
    used: set[str],
    pool: list[tuple[str, int]],
    multiple_choice: bool,
) -> Optional[dict]:
    """multiple_choice / fill_blank: korpus cümlesinde bir terimi boşaltır."""
    for row in rows:
        for sentence in _candidate_sentences(row["content"]):
            if sentence in used:
                continue
            picked = _pick_blank_term(conn, sentence, df)
            if picked is None:
                continue
            raw_term, _token = picked
            choices: list[str] = []
            if multiple_choice:
                distractors = _distractors(
                    raw_term, pool, row["content"], config.QUIZ_CHOICE_COUNT - 1
                )
                if len(distractors) < config.QUIZ_CHOICE_COUNT - 1:
                    continue  # yeterli çeldirici yok -> bu tip kurulamaz
                # Doğru şıkkın konumu sabit olmamalı ama RASTGELE de olmamalı
                # (determinizm): şıklar içerik hash'iyle sıralanır.
                choices = sorted([raw_term] + distractors, key=_scatter_key)
            used.add(sentence)
            return {
                "type": "multiple_choice" if multiple_choice else "fill_blank",
                "topic_id": topic.id,
                "prompt": _blank_out(sentence, raw_term),
                "choices": choices,
                "answer": raw_term,
                "chunk_id": row["id"],
                "source": row["source"],
                "citation": _citation_for(row),
                "evidence": sentence,
            }
    return None


def _build_true_false_question(
    topic: Topic,
    rows: list[sqlite3.Row],
    used: set[str],
    documents_by_source: dict[str, str],
) -> Optional[dict]:
    """true_false: cümle + KAYNAK ATFI. Doğruluk değeri DOĞRULANABİLİR (§12.4).

    Doğru varyant: cümle gerçekten o belgeden -> cevap "true".
    Yanlış varyant: aynı cümle BAŞKA bir belgeye atfedilir -> cevap "false",
    ve bu yanlışlık metadata'dan kesindir (cümlenin hangi chunk'tan geldiğini
    biliyoruz), bir entailment yargısı DEĞİL.

    Bu kurgu, ölçümle ELENEN sayısal-mutasyon kurgusunun yerine geçti: "130"u
    "260" yapıp korpusta aranan biçim eval.db'de 7 kümenin yalnızca 1'inde
    soru üretebiliyordu ve rag.db'de bir URL kimliğini mutasyona uğratıyordu
    (§12.4 ölçüm tablosu). Kaynak atfı 7/7 ve 10/10 kapsıyor -- üstelik bu
    ürünün asıl iddiasını ("hangi belge ne diyor") sınıyor.

    Yanlış atıf için başka belge yoksa (tek belgelik korpus) None döner.
    """
    is_true = topic.id % 2 == 0
    for row in rows:
        for sentence in _candidate_sentences(row["content"]):
            if sentence in used:
                continue
            real_source = row["source"]
            if is_true:
                claimed = real_source
            else:
                others = sorted(s for s in documents_by_source if s != real_source)
                if not others:
                    return None
                # Deterministik ama kümeye göre değişen seçim: en makul yanlış
                # atıf, alfabetik ilk BAŞKA belgedir; küme kimliği ile kaydırılır
                # ki tüm sorular aynı belgeyi suçlamasın.
                claimed = others[topic.id % len(others)]
                if sentence in documents_by_source[claimed]:
                    continue  # cümle o belgede de geçiyor -> "yanlış" DOĞRULANAMAZ
            used.add(sentence)
            return {
                "type": "true_false",
                "topic_id": topic.id,
                "prompt": f"«{sentence}» — Bu bilgi {claimed} belgesinde geçiyor.",
                "choices": ["true", "false"],
                "answer": "true" if is_true else "false",
                "chunk_id": row["id"],
                "source": real_source,
                "citation": _citation_for(row),
                "evidence": sentence,
            }
    return None


def _evidence_for(row: sqlite3.Row) -> str:
    """short_answer'ın kullanıcıya gösterilen GEREKÇESİ: chunk'ın ilk düzgün
    cümlesi, yoksa chunk metninin kendisi.

    DİKKAT: bu, sadakat kapısına giden metin DEĞİLDİR. short_answer'da kapıya
    modelin REFERANS CEVABI gider (§12.7) -- hallüsinasyon riski taşıyan tek
    metin odur; chunk'ın kendi cümlesini bağlamak totolojidir.
    """
    sentences = _candidate_sentences(row["content"])
    return sentences[0] if sentences else row["content"]


def _claim_of(question: dict) -> tuple[str, str]:
    """Sorunun sadakat kapısına giden iddiası: (node_path eki, metin).

    Tip başına DEĞİŞİR ve bu kasıtlıdır (§12.7): kapı, modelin UYDURMUŞ
    olabileceği metni korumalıdır.
      short_answer -> `answer`   (metni model yazdı)
      diğer üçü    -> `evidence` (metin korpustan BİREBİR alındı; bağlanması
                      cümlenin gerçekten korpusta olduğunun tutarlılık
                      kontrolüdür, bu yüzden neredeyse her zaman grounded çıkar
                      -- quiz'in fidelity_score'u YAPISI GEREĞİ yüksektir ve
                      asıl oynayan bileşen short_answer iddialarıdır)
    """
    if question["type"] == "short_answer":
        return "answer", question["answer"]
    return "evidence", question["evidence"]


def _build_short_answer_question(
    client, conn: sqlite3.Connection, topic: Topic, rows: list[sqlite3.Row]
) -> Optional[dict]:
    """short_answer: TEK LLM çağrısı. Bağlam kümenin merkezine en yakın
    chunk'ıdır (Topic.chunk_ids zaten o sırada)."""
    if not rows:
        return None
    row = rows[0]
    hit = Hit(score=0.0, source=row["source"], page=row["page"],
              content=row["content"], via_ocr=bool(row["via_ocr"]))
    generated = _generate_short_answer(client, build_context([hit]))
    if generated is None:
        return None
    question, answer = generated
    return {
        "type": "short_answer",
        "topic_id": topic.id,
        "prompt": question,
        "choices": [],
        "answer": answer,
        "chunk_id": row["id"],
        "source": row["source"],
        "citation": _citation_for(row),
        "evidence": _evidence_for(row),
    }


# Küme index'ine göre TİP DENEME SIRASI: kurulabilen ilk tip seçilir, hiçbir
# küme sorusuz kalmaz (§12.3).
#
# TABLO ÖLÇÜMLE ŞEKİLLENDİ, tek satırlık bir rotasyon YETMEDİ. Dört tipin
# kurulabilirliği çok farklı (§12.4 sondası):
#   multiple_choice / fill_blank : cümlede AYIRT EDİCİ terim gerekir --
#       eval.db'de 7 kümenin 2'sinde, rag.db'de 10 kümenin 6'sında var
#   true_false                   : yalnızca DÜZGÜN bir cümle gerekir
#   short_answer                 : her zaman kurulur (tek LLM çağrısı)
# Son ikisi "her zaman kurulabilir" sınıfında olduğu için, tek bir rotasyonda
# hangisi önce gelirse MC/FB'nin kurulamadığı HER kümeyi o kapıyor. Ölçüldü:
# true_false önde -> eval.db'de 7 sorunun 5'i true_false; short_answer önde ->
# 7 sorunun 6'sı short_answer. Tablo, ikisinin yedeklik sırasını küme index'ine
# göre DEĞİŞTİREREK dengeyi kuruyor (eval.db: 3 TF / 3 SA / 1 FB).
_TYPE_ORDERS = (
    ("multiple_choice", "fill_blank", "true_false", "short_answer"),
    ("fill_blank", "multiple_choice", "short_answer", "true_false"),
    ("true_false", "multiple_choice", "fill_blank", "short_answer"),
    ("short_answer", "fill_blank", "multiple_choice", "true_false"),
)


# --------------------------------------------------------------------------- üretici

class QuizGenerator:
    kind = "quiz"

    def generate(self, ctx: GenerationContext) -> GeneratedArtifact:
        conn = ctx.conn
        topics = sorted(ctx.topics, key=lambda t: t.id)
        client = models.get_chat_client(max_tokens=config.ARTIFACT_QUESTION_MAX_TOKENS)

        terms_by_chunk, df = _corpus_terms(conn)
        chunk_rows_by_topic = {t.id: _chunk_rows(conn, t.chunk_ids) for t in topics}

        # Belge metinleri (true_false doğrulaması) ve küme dışı terim havuzu
        # (çeldiriciler) -- ikisi de deterministik, korpustan.
        documents_by_source: dict[str, str] = {}
        for row in conn.execute("SELECT source, content FROM chunks"):
            documents_by_source[row["source"]] = (
                documents_by_source.get(row["source"], "") + " " + row["content"]
            )

        used_sentences: set[str] = set()
        questions: list[dict] = []
        limit = min(
            len(topics) * config.QUIZ_QUESTIONS_PER_TOPIC, config.QUIZ_MAX_QUESTIONS
        )

        for index, topic in enumerate(topics):
            if len(questions) >= limit:
                break
            rows = chunk_rows_by_topic[topic.id]
            pool = self._distractor_pool(terms_by_chunk, set(topic.chunk_ids), df)

            question = None
            for kind in _TYPE_ORDERS[index % len(_TYPE_ORDERS)]:
                if kind in ("multiple_choice", "fill_blank"):
                    question = _build_blank_question(
                        conn, topic, rows, df, used_sentences, pool,
                        multiple_choice=(kind == "multiple_choice"),
                    )
                elif kind == "true_false":
                    question = _build_true_false_question(
                        topic, rows, used_sentences, documents_by_source
                    )
                else:
                    question = _build_short_answer_question(client, conn, topic, rows)
                if question is not None:
                    break

            ctx.emit(
                "progress",
                {
                    "pct": round((index + 1) * 100 / len(topics)),
                    "detail": f"{index + 1}/{len(topics)} küme için soru üretildi",
                },
            )
            if question is not None:
                questions.append(question)

        # Sadakat: sorunun MODELDEN gelmiş olabilecek metni korpusa bağlanır
        # (§12.7, `_claim_of`). true_false'un YANLIŞ varyantında KULLANICIYA
        # GÖSTERİLEN ifade kasten yanlıştır; onu bağlamak yanlış bir iddiayı
        # "grounded" diye kaydetmek olurdu -- bağlanan, o sorunun dayandığı
        # korpus cümlesidir.
        gate_input = [(f"q{i}", _claim_of(q)[1]) for i, q in enumerate(questions)]
        bindings = {b.node_path: b for b in bind_claims(conn, gate_input)}

        kept: list[dict] = []
        dropped_payload: list[dict] = []
        for i, question in enumerate(questions):
            binding = bindings[f"q{i}"]
            unverified: list[str] = []
            if binding.verdict == "grounded":
                unverified = unverified_terms(
                    conn, _claim_of(question)[1], [question["chunk_id"]]
                )
            reason = should_drop(binding, unverified)
            if reason is None:
                kept.append(question)
            else:
                dropped_payload.append(
                    {
                        "topic_id": question["topic_id"],
                        # DOĞRULANAMAYAN METNİN KENDİSİ -- soru gövdesi değil.
                        # Raporun `dropped` alanıyla aynı anlam: "kapıdan
                        # geçemeyen metin". Soru gövdesini yazmak, hangi metnin
                        # düştüğünü kayıttan SİLERDİ (§12.7): short_answer'da
                        # düşen şey modelin REFERANS CEVABIDIR, sorusu değil.
                        "text": _claim_of(question)[1],
                        "prompt": question["prompt"],
                        "reason": reason,
                        "score": binding.score,
                        "terms": unverified if reason == "unverified_terms" else [],
                    }
                )

        for i, question in enumerate(kept):
            question["id"] = f"q{i}"

        payload = {
            "kind": "quiz",
            "questions": kept,
            "dropped": dropped_payload,
        }

        claims: list[tuple[str, str]] = []
        for i, question in enumerate(kept):
            field, text = _claim_of(question)
            claims.append((f"/questions/{i}/{field}", text))
        for i, item in enumerate(dropped_payload):
            claims.append((f"/dropped/{i}", item["text"]))

        return GeneratedArtifact(
            title=_quiz_title(conn, ctx.scope, ctx.document_id),
            payload=payload,
            claims=claims,
        )

    @staticmethod
    def _distractor_pool(
        terms_by_chunk: dict[int, list[tuple[str, str]]],
        own_chunk_ids: set[int],
        df: dict[str, int],
    ) -> list[tuple[str, int]]:
        """Bu kümenin DIŞINDAKİ chunk'ların ayırt edici terimleri, df artan.

        "Embedding uzayında yakın ama farklı chunk'lardan" (STUDIO_PLAN §6.3)
        kuralının uygulaması: kümeler zaten embedding uzayının bölütleri, yani
        başka bir kümenin terimi tanım gereği "yakın ama farklı".
        """
        seen: set[str] = set()
        pool: list[tuple[str, int]] = []
        for chunk_id, terms in terms_by_chunk.items():
            if chunk_id in own_chunk_ids:
                continue
            for raw, token in terms:
                if token in seen:
                    continue
                seen.add(token)
                pool.append((raw, df.get(token, 0)))
        pool.sort(key=lambda rd: (rd[1], _scatter_key(rd[0])))
        return pool


def _quiz_title(conn: sqlite3.Connection, scope: str, document_id: Optional[int]) -> str:
    if scope == "document" and document_id is not None:
        row = conn.execute(
            "SELECT filename FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is not None:
            return f"{row['filename']} Quiz"
    return "Korpus Quiz"


# --------------------------------------------------------------------------- puanlama

_PUNCT_RE = re.compile(r"[^0-9a-zçğıöşü\s-]+")


def _normalize_answer(text: str) -> str:
    """Cevap karşılaştırması için normalleştirme.

    İ->i, I->ı elle eşlenir: düz str.lower() 'İ' için BİRLEŞEN NOKTA üretir ve
    karşılaştırma sessizce başarısız olur (aynı tuzak fidelity._term_lower'da
    kayıtlı). Sonra noktalama atılır, boşluklar sadeleşir.
    """
    lowered = (text or "").replace("İ", "i").replace("I", "ı").lower()
    return " ".join(_PUNCT_RE.sub(" ", lowered).split())


def score_attempt(payload: dict, answers: dict[str, str]) -> dict:
    """Bir denemeyi puanlar (§12.8). İŞ MANTIĞI BURADA -- backend yalnızca yüzey.

    Veritabanı bağlantısı ALMAZ: cevap anahtarı, atıf ve gerekçe zaten
    `payload_json`'ın içinde (render'ın tek girdisi olması kuralının aynısı,
    §10.5). short_answer benzerliği için yalnızca embedding modeli gerekir.

    İki puanlama sınıfı kasıtlı olarak AYRI tutulur:

      DETERMİNİSTİK (multiple_choice / true_false / fill_blank)
        Normalize edilmiş TAM EŞLEŞME. `correct` bool.

      YAKLAŞIK (short_answer)
        Kullanıcının cevabı ile referans cevap arasındaki HAM COSINE.
        `correct` her zaman None'dır ve bu sayı toplam skora KATILMAZ --
        STUDIO_PLAN §6.3: "puan bir eşik değil benzerlik skoru olarak
        gösterilir, kullanıcı kendi doğrulamasını yapar". Bir eşik uydurup
        doğru/yanlış demek, ölçülmemiş bir kararı ölçülmüş gibi sunmak olurdu.

    DİKKAT -- bu cosine `Hit.score` DEĞİLDİR: iki CEVAP arasındaki simetrik
    benzerliktir (ikisi de is_query=False ile embed edilir), sorgu->chunk
    asimetrik benzerliği değil. DESIGN_SYSTEM §1.2 güven bantlarıyla
    RENKLENDİRİLEMEZ (o bantlar sorgu->chunk için kalibre edildi, §12.8).
    """
    questions = payload.get("questions", [])
    short_answer_pairs: list[tuple[int, str, str]] = []
    results: list[dict] = []

    for index, question in enumerate(questions):
        given = answers.get(question["id"])
        result = {
            "question_id": question["id"],
            "type": question["type"],
            "given": given,
            "expected": question["answer"],
            "correct": None,
            "similarity": None,
            "chunk_id": question.get("chunk_id"),
            "citation": question.get("citation"),
            "evidence": question.get("evidence", ""),
        }
        if question["type"] == "short_answer":
            if given:
                short_answer_pairs.append((index, given, question["answer"]))
        else:
            result["correct"] = (
                given is not None
                and _normalize_answer(given) == _normalize_answer(question["answer"])
            )
        results.append(result)

    if short_answer_pairs:
        texts = [text for _i, given, reference in short_answer_pairs for text in (given, reference)]
        vectors = models.embed_texts(texts, is_query=False)
        for offset, (index, _given, _reference) in enumerate(short_answer_pairs):
            results[index]["similarity"] = _cosine(
                vectors[2 * offset], vectors[2 * offset + 1]
            )

    deterministic = [r for r in results if r["correct"] is not None]
    correct_count = sum(1 for r in deterministic if r["correct"])
    return {
        "results": results,
        "score": (correct_count / len(deterministic)) if deterministic else None,
        "correct_count": correct_count,
        "deterministic_total": len(deterministic),
        "similarity_total": sum(1 for r in results if r["type"] == "short_answer"),
    }


def _cosine(a: list[float], b: list[float]) -> float:
    """İki vektör arasındaki ham cosine. numpy'siz: iki vektörlük bir hesap
    için matris altyapısı kurmanın gerekçesi yok."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


# --------------------------------------------------------------------------- markdown export

_TRUE_FALSE_LABEL = {"true": "Doğru", "false": "Yanlış"}


def to_markdown(payload: dict) -> str:
    """payload_json'dan markdown üretir (§12.9): sorular + ayrı cevap anahtarı.

    Cevap anahtarı AYRI bölümdedir ki çıktı çalışma kâğıdı olarak da
    kullanılabilsin. Düşürülen soruların METNİ girmez, yalnızca SAYISI.
    Hiçbir http(s):// üretilmez (soru cümlesi seçiminde URL taşıyan cümleler
    zaten eleniyor, §12.4).
    """
    questions = payload.get("questions", [])
    lines: list[str] = ["## Sorular", ""]

    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. {question['prompt']}")
        for choice in question.get("choices", []):
            lines.append(f"    - {_TRUE_FALSE_LABEL.get(choice, choice)}")
        lines.append("")

    lines.append("## Cevap Anahtarı")
    lines.append("")
    for index, question in enumerate(questions, start=1):
        answer = _TRUE_FALSE_LABEL.get(question["answer"], question["answer"])
        lines.append(f"{index}. {answer}  {question.get('citation', '')}".rstrip())
    lines.append("")

    dropped = payload.get("dropped", [])
    if dropped:
        lines.append("---")
        lines.append("")
        lines.append(
            f"*{len(dropped)} soru cevap anahtarı kaynağa yeterince bağlanamadığı "
            f"için quiz'e alınmadı; metinleri gösterilmez.*"
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


register(QuizGenerator())
