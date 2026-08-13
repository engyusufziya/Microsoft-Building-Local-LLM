"""
Cevap üretimi: retrieval + system prompt + yerel LLM.

Halüsinasyona karşı savunma iki katmanlı:
  1. Skor eşiği (config.MIN_SCORE) — konu dışı soruda LLM hiç çağrılmaz.
  2. System prompt — konu yakın ama cevabı olmayan soruda modelin reddetmesi.
Neden tek katman yetmiyor, config.MIN_SCORE yorumunda açıklanmış.

Kaynak listesi getirilen chunk'ların metadata'sından KOD TARAFINDA üretilir;
modelin kaynak uydurmasına izin verilmez.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, Literal, Optional, Union

from . import config, models, retrieve

SYSTEM_PROMPT = """Sen yerel bir belge asistanısın. Kullanıcının sorusunu SADECE aşağıda \
verilen bağlamı kullanarak Türkçe cevapla.

Kurallar:
- Yalnızca bağlamdaki bilgiyi kullan. Kendi bilgini ekleme, tahmin yürütme.
- Bağlam soruyla ilgili görünse bile sorunun cevabı bağlamda yoksa \
tam olarak şunu yaz: "{no_answer}"
- Cevabın en fazla 3 cümle olsun.
- Kendini tekrar etme.
- Kaynak numarası veya dosya adı yazma; onları sistem ekliyor.

Bağlam:
{context}"""


@dataclass
class Answer:
    text: str
    hits: list = field(default_factory=list)
    answered: bool = True

    @property
    def sources(self) -> list[str]:
        """Getirilen chunk'lardan tekrarsız kaynak atıfları (sıra korunur)."""
        seen, out = set(), []
        for hit in self.hits:
            c = hit.citation()
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def formatted(self) -> str:
        """Cevap + kaynak satırı."""
        if not self.answered or not self.sources:
            return self.text
        return f"{self.text}\n\n{' '.join(self.sources)}"


def answer_query(
    question: str,
    k: Optional[int] = None,
    min_score: Optional[float] = None,
    model: Optional[str] = None,
    conn=None,
) -> Answer:
    """Soruyu cevaplar. Bağlam bulunamazsa LLM'i hiç çağırmaz."""
    question = (question or "").strip()
    if not question:
        return Answer("Lütfen bir soru yazın.", [], answered=False)

    min_score = config.MIN_SCORE if min_score is None else min_score
    hits = retrieve.get_top_chunks(question, k=k, min_score=min_score, conn=conn)

    # 1. katman: hiçbir chunk eşiği geçemedi -> soru korpusun konusu dışında.
    if not hits:
        return Answer(config.NO_ANSWER_TEXT, [], answered=False)

    prompt = SYSTEM_PROMPT.format(
        no_answer=config.NO_ANSWER_TEXT,
        context=retrieve.build_context(hits),
    )
    client = models.get_chat_client(model)
    response = client.complete_chat(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ]
    )
    text = (response.choices[0].message.content or "").strip()

    # 2. katman: model bağlamda cevap olmadığını söyledi -> kaynak gösterme.
    refused = config.NO_ANSWER_TEXT.rstrip(".").lower() in text.lower()
    return Answer(text or config.NO_ANSWER_TEXT, [] if refused else hits, answered=not refused)


# --------------------------------------------------------------------------- streaming
#
# Backend (Faz 4.3, docs/FEATURE_SPEC.md §3.1) bu olayları SSE'ye çevirir.
# rag/ paketi HTTP/SSE'den habersiz kalır; wire format'a çevirme backend'in işi.
#
# answer_query'den kasıtlı olarak ayrı bir fonksiyon: mevcut davranış
# (eval/run_eval.py buna bağlı) hiçbir şekilde değişmemeli.


@dataclass
class RetrievalEvent:
    """SSE 'retrieval' olayı. ESKİ + YENİ hepsi (eşik altı dahil) döner --

    Inspector'ın eşik çizgisini aynı sohbet akışında çizebilmesi için.
    passed_threshold hesaplaması BURADA değil, backend'de yapılır (ChunkHit
    şemasına çevrilirken) -- rag.retrieve.Hit'e alan eklenmez, motor sade kalır.
    """

    hits: list  # rag.retrieve.Hit listesi, skora göre azalan
    threshold: float
    passed_count: int
    rejected_count: int
    elapsed_ms: int


@dataclass
class TokenEvent:
    text: str


@dataclass
class DoneEvent:
    answered: bool
    reason: Optional[Literal["below_threshold", "llm_refused"]]
    sources: list[str]
    elapsed_ms: int
    token_count: int


StreamEvent = Union[RetrievalEvent, TokenEvent, DoneEvent]


def answer_query_stream(
    question: str,
    k: Optional[int] = None,
    min_score: Optional[float] = None,
    model: Optional[str] = None,
    conn=None,
) -> Iterator[StreamEvent]:
    """answer_query'nin streaming karşılığı. Üç olay sırayla:

    RetrievalEvent -> (below_threshold ise burada biter) -> TokenEvent* -> DoneEvent

    reason değerleri (docs/FEATURE_SPEC.md §3.2):
      None              -> normal cevap, token'lar aktı
      "below_threshold" -> hiçbir chunk eşiği geçemedi, LLM hiç çağrılmadı
      "llm_refused"      -> LLM token akıttı ama bağlamda cevap yok dedi;
                            frontend akan metni yerelleştirilmiş metinle değiştirir
    """
    t0 = time.time()
    question = (question or "").strip()
    min_score = config.MIN_SCORE if min_score is None else min_score

    # Eşik altındakiler de gerekli (Inspector eşik çizgisini çizer) -> filtresiz çek.
    all_hits = retrieve.get_top_chunks(question, k=k, min_score=None, conn=conn)
    passed = [h for h in all_hits if h.score >= min_score]

    yield RetrievalEvent(
        hits=all_hits,
        threshold=min_score,
        passed_count=len(passed),
        rejected_count=len(all_hits) - len(passed),
        elapsed_ms=int((time.time() - t0) * 1000),
    )

    # 1. katman kısa devresi: hiçbir chunk eşiği geçemedi -> LLM'e hiç gitme.
    if not passed:
        yield DoneEvent(
            answered=False,
            reason="below_threshold",
            sources=[],
            elapsed_ms=int((time.time() - t0) * 1000),
            token_count=0,
        )
        return

    prompt = SYSTEM_PROMPT.format(
        no_answer=config.NO_ANSWER_TEXT,
        context=retrieve.build_context(passed),
    )
    client = models.get_chat_client(model)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    parts: list[str] = []
    token_count = 0
    for chunk in client.complete_streaming_chat(messages):
        if not chunk.choices:  # ÖLÇÜLDÜ: akışta boş chunk.choices geliyor
            continue
        content = chunk.choices[0].delta.content
        if content:
            parts.append(content)
            token_count += 1
            yield TokenEvent(text=content)

    text = "".join(parts).strip()

    # 2. katman: model bağlamda cevap olmadığını söyledi -> kaynak gösterme.
    refused = config.NO_ANSWER_TEXT.rstrip(".").lower() in text.lower()
    sources = [] if refused else Answer(text, passed).sources

    yield DoneEvent(
        answered=not refused,
        reason="llm_refused" if refused else None,
        sources=sources,
        elapsed_ms=int((time.time() - t0) * 1000),
        token_count=token_count,
    )
