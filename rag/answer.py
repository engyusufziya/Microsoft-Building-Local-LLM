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

from dataclasses import dataclass, field
from typing import Optional

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
