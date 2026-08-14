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

import difflib
import time
from dataclasses import dataclass, field
from typing import Iterator, Literal, Optional, Union

from .query_router import RouteKind

from . import config, models, query_router, retrieve, store

# 2. katman reddetme tespiti eşiği. rag/config.py::NO_ANSWER_TEXT'in ölçülen
# kırılganlığının (phi-4-mini Q13: "yüklediğiniz" -> "yüklendiğiniz" tek harf
# farkı tespiti kaçırdı) düzeltmesi -- bkz. is_refusal(). Kalibrasyon:
#   gerçek reddetme varyantları (birebir / tipo / cümle içine gömülü) -> 0.833-1.000
#   alakasız ama "belgelerde"/"yok" geçen kontrollü cevaplar          -> 0.00-0.667
# 0.80, ikisi arasındaki boşluğa (aynı MIN_SCORE'un kalibrasyon mantığı gibi)
# yerleştirildi.
#
# ÖLÇÜLDÜ -- İKİNCİ TUR (bir SYSTEM_PROMPT gevşetme denemesi sırasında,
# daha uzun/doğal cümleli cevaplarla test edilirken bulundu -- deneme
# halüsinasyon riski nedeniyle GERİ ALINDI, ama bu tespit hatası KENDİ
# BAŞINA gerçek ve bağımsızdı): "sum of ALL matching blocks" metriği UZUN
# cevaplarda YANLIŞ POZİTİF üretti (tamamen alakalı ve doğru bir cevap
# "reddetme" sayıldı). Neden: Türkçe'de "belge"/"bilgi" gibi ortak alt
# diziler, uzun bir metinde dağınık onlarca küçük (1-6 karakterlik) parça
# olarak eşleşip toplamda hedefin uzunluğunu (36 karakter) aşabiliyor --
# eşleşmenin TEK BİR BLOK olması gerekmiyordu, bu da metnin GERÇEKTEN ret
# cümlesini üretip üretmediğinden bağımsız bir sinyaldi. Düzeltme: yalnızca
# EN BÜYÜK 3 eşleşen bloğun toplamı kullanılır (min blok boyutu 3) --
# gerçek bir yeniden üretim (birebir ya da tek harflik çekim farkıyla) az
# sayıda BÜYÜK bloğa bölünür, alakasız bir metindeyse yalnızca çok sayıda
# KÜÇÜK parça birikir. Kısa cevaplarda (mevcut SYSTEM_PROMPT'un ürettiği
# tipik 3 cümlelik çıktı) bu senaryo nadirdir ama düzeltme genel olarak
# daha doğru; geri alınmadı.
_REFUSAL_MATCH_THRESHOLD = 0.80
_REFUSAL_TOP_BLOCKS = 3
_REFUSAL_MIN_BLOCK_SIZE = 3


def is_refusal(text: str) -> bool:
    """Modelin config.NO_ANSWER_TEXT'i (anlamca) üretip üretmediğini kontrol eder.

    Birebir alt dize eşleşmesi (`NO_ANSWER_TEXT in text`) KIRILGANDIR --
    ÖLÇÜLDÜ (eval/results.json, phi-4-mini Q13): model "Bu bilgi
    YÜKLENDİĞİNİZ belgelerde yok" yazdı (doğrusu "yüklediğiniz"), tek harflik
    çekim farkı tespiti kaçırdı ve arkasına uydurma içerik eklendi -- 2.
    katman savunma (bkz. modül docstring'i) sessizce devre dışı kaldı.

    Bunun yerine NO_ANSWER_TEXT'in cevap içinde NE KADARININ birkaç BÜYÜK
    bloğa (difflib.SequenceMatcher, en büyük 3 blok) yayıldığını ölçer --
    karakter bazlı küçük sapmalara (çekim, büyük/küçük harf, model
    reddetmeden önce/sonra ekstra kelime eklemesi) dayanıklıdır. TÜM
    eşleşen parçaları (bkz. yukarı yorum) DEĞİL yalnızca en büyük birkaçını
    toplamak kasıtlı: uzun, alakasız bir cevapta biriken onlarca küçük
    tesadüfi örtüşmenin toplamı yanlış pozitif üretebiliyordu (kalibrasyon:
    yukarı bkz.).

    Kasıtlı olarak yapılandırılmış çıktı (response_format) KULLANMIYOR: Foundry
    Local runtime'ının SDK alanlarını sessizce yok saydığı zaten ölçüldü
    (rag/config.py TEMPERATURE/TOP_P notu) -- response_format'ın güvenilir
    çalışacağı doğrulanmadan üzerine bir savunma katmanı kurmak riskli olurdu.
    """
    target = config.NO_ANSWER_TEXT.rstrip(".").strip().lower()
    candidate = (text or "").strip().lower()
    if not candidate:
        return False
    sm = difflib.SequenceMatcher(None, target, candidate, autojunk=False)
    blocks = sorted(
        (b.size for b in sm.get_matching_blocks() if b.size >= _REFUSAL_MIN_BLOCK_SIZE),
        reverse=True,
    )
    coverage = sum(blocks[:_REFUSAL_TOP_BLOCKS]) / len(target)
    return coverage >= _REFUSAL_MATCH_THRESHOLD


# DENENDİ VE GERİ ALINDI (kullanıcı isteği: cevapların "birebir alıntı
# yapıştırma" gibi hissettirmemesi). BEŞ farklı gevşetme denendi -- sondan
# başa: (1) "kendi cümlelerinle anlat" + serbest uzunluk, (2) + somut "neyi
# doldurma" örneği, (3) + few-shot ters örnek, (4) grounding kuralını en öne
# alıp 4 cümle tavanı, (5) ORİJİNAL METNE dokunmadan yalnızca TEK satır ekleme
# ("birebir kopyalamak zorunda değilsin"). BEŞİ DE aynı ölçülebilir
# halüsinasyonu üretti: eval Q12 tuzak sorusu ("Chroma mı FAISS mi daha
# hızlı?", bağlamda [belge_07] İKİSİNİN ADI DA GEÇMİYOR) her seferinde
# "FAISS genellikle daha hızlı çalışır..." diye UYDURULDU.
#
# Kontrol turu KANITLADI ki bu, retrieval'ın (belge_07, ANN search konusunda
# güçlü ama isim vermeyen bir bağlam getiriyor) zorlaştırdığı bir soru değil:
# AYNI korpusla, AŞAĞIDAKİ ORİJİNAL prompt doğru şekilde reddediyor. Yani
# "birebir kopyalamak zorunda değilsin" izninin KENDİSİ -- ne kadar minimal
# eklenirse eklensin -- bu 7B modelde "adı geçmeyen ama konuyla ilgili bir
# şeyi kendi bilgimle tamamlayabilirim" sızıntısına yol açıyor.
#
# Karar: SYSTEM_PROMPT değişmedi. Halüsinasyon riski, ifade özgürlüğü UX
# tercihinden daha ağır basar -- bu projenin tek garantisi budur. Kullanıcıya
# bu ölçümle birlikte raporlandı; farklı bir mekanizma (örn. modeli
# değiştirmek, response_format/yapılandırılmış çıktı, ya da post-processing)
# istenirse yeniden değerlendirilebilir.
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

# Özetleme yolu ayrı bir prompt kullanır: burada "cevap bağlamda yok" reddi
# ANLAMSIZDIR -- bağlam zaten belgenin kendisidir, görev de onu özetlemektir.
# Ana prompt'un reddetme kuralı buraya konsaydı model özetlemek yerine
# reddedebilirdi.
SUMMARY_PROMPT = """Sen yerel bir belge asistanısın. Aşağıda "{filename}" adlı \
belgeden alınmış bölümler var. Bu belgeyi Türkçe özetle.

Kurallar:
- Yalnızca aşağıdaki bölümlerdeki bilgiyi kullan. Kendi bilgini ekleme.
- Bölümler belge boyunca örneklenmiştir; aradaki kısımları uydurma.
- Özet en fazla 5 cümle olsun.
- Kendini tekrar etme.
- Kaynak numarası veya dosya adı yazma; onları sistem ekliyor.

Belge bölümleri:
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


# --------------------------------------------------------------------------- yönlendirme
#
# Aşağıdaki üç yardımcı, `search` dışındaki iki yolu besler. Ayrıntılı gerekçe
# rag/query_router.py docstring'inde (ölçüm dahil).


def _corpus_answer(conn) -> str:
    """Korpus sorusunu doğrudan veritabanından cevaplar -- LLM çağrılmaz.

    "Kaç belge yükledim" sorusunun cevabı belgelerin İÇİNDE değil, korpusun
    kendisindedir. Buraya LLM sokmak hem gereksiz ~5 sn gecikme ekler hem de
    kesin bir sayıyı uydurulabilir hale getirir.
    """
    docs = store.list_documents(conn)
    if not docs:
        return "Henüz yüklenmiş belge yok."

    stats = store.corpus_stats(conn)
    lines = [
        f"{stats['documents']} belge yüklü "
        f"({stats['pages']} sayfa, {stats['chunks']} bölüm):"
    ]
    for d in docs:
        page_count = d.get("page_count") or 0
        chunk_count = d.get("chunk_count") or 0
        lines.append(f"- {d['filename']} — {page_count} sayfa, {chunk_count} bölüm")
    return "\n".join(lines)


def _resolve_summary_target(route, conn) -> tuple[Optional[str], Optional[str]]:
    """Özetlenecek belgeyi seçer.

    Dönüş: (filename, uyarı_metni). Belge seçilemezse filename None olur ve
    kullanıcıya gösterilecek metin döner -- birden fazla belge varken hangisinin
    kastedildiğini TAHMİN ETMEK yerine sormak doğru davranış.
    """
    docs = store.list_documents(conn)
    if not docs:
        return None, "Henüz yüklenmiş belge yok."
    if route.target:
        return route.target, None
    if len(docs) == 1:
        return docs[0]["filename"], None
    names = ", ".join(d["filename"] for d in docs)
    return None, f"Hangi belgeyi özetlememi istersiniz? Yüklü belgeler: {names}"


def _summary_hits(conn, filename: str) -> list:
    """Özetlenecek belgenin chunk'larını Hit listesine çevirir.

    DİKKAT -- score=0.0 bir benzerlik skoru DEĞİLDİR: bu yolda benzerlik hiç
    hesaplanmaz, chunk'lar belge kimliğinden gelir. Alan yalnızca Hit sözleşmesi
    gerektirdiği için doldurulur. Arayüz özetleme modunda skor rozetlerini
    göstermez (retrieval olayındaki `mode` alanına bakar), böylece uydurma bir
    sayı kullanıcıya gösterilmez.
    """
    rows = store.get_document_chunks(conn, filename, limit=config.SUMMARY_MAX_CHUNKS)
    return [
        retrieve.Hit(
            score=0.0,
            source=r["source"],
            page=r["page"],
            content=r["content"],
            via_ocr=r["via_ocr"],
        )
        for r in rows
    ]


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

    own_conn = conn is None
    conn = conn or store.connect()
    try:
        return _answer_query(question, k, min_score, model, conn)
    finally:
        if own_conn:
            conn.close()


def _answer_query(question, k, min_score, model, conn) -> Answer:
    docs = store.list_documents(conn)
    route = query_router.classify(question, [d["filename"] for d in docs])

    if route.kind == "corpus":
        return Answer(_corpus_answer(conn), [], answered=True)

    if route.kind == "summarize":
        filename, warning = _resolve_summary_target(route, conn)
        if filename is None:
            return Answer(warning, [], answered=False)
        hits = _summary_hits(conn, filename)
        if not hits:
            return Answer(config.NO_ANSWER_TEXT, [], answered=False)
        prompt = SUMMARY_PROMPT.format(
            filename=filename, context=retrieve.build_context(hits)
        )
        client = models.get_chat_client(model)
        response = client.complete_chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ]
        )
        text = (response.choices[0].message.content or "").strip()
        return Answer(text or config.NO_ANSWER_TEXT, hits, answered=bool(text))

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
    refused = is_refusal(text)
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
    # Hangi yoldan gelindi (rag/query_router.py). EK ALAN, mevcut alanların
    # hiçbirini değiştirmez -- FEATURE_SPEC §8'de dondurulan şey alan ADLARI ve
    # `reason` DEĞERLERİ; additive alan sözleşmeyi bozmaz (M1'in --json bayrağı
    # gibi). Varsayılanı "search" olduğu için eski davranış aynen korunur.
    #
    # "summarize" modunda skorlar anlamsızdır (benzerlik hesaplanmaz); arayüz
    # bu alana bakıp skor rozetlerini gizler.
    mode: RouteKind = "search"


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


def _stream_static(text: str, t0: float, mode: RouteKind) -> Iterator[StreamEvent]:
    """LLM'siz bir cevabı normal olay sırasına sokar.

    Wire format'ı korumak için tek parça da olsa TokenEvent olarak gönderilir:
    frontend'in ayrı bir dal açmasına gerek kalmaz, sözleşme aynı kalır.
    """
    yield RetrievalEvent(
        hits=[],
        threshold=0.0,
        passed_count=0,
        rejected_count=0,
        elapsed_ms=int((time.time() - t0) * 1000),
        mode=mode,
    )
    yield TokenEvent(text=text)
    yield DoneEvent(
        answered=True,
        reason=None,
        sources=[],
        elapsed_ms=int((time.time() - t0) * 1000),
        token_count=1,
    )


def _stream_summary(question, route, model, conn, t0: float) -> Iterator[StreamEvent]:
    """Özetleme yolu: benzerlik araması yok, chunk'lar belgeden doğrudan gelir."""
    filename, warning = _resolve_summary_target(route, conn)
    if filename is None:
        # Hangi belge kastedildiği belirsiz -> tahmin etme, sor. Bu geçerli bir
        # asistan cevabıdır (answered=True); yeni bir `reason` değeri
        # gerektirmez, dondurulmuş sözleşme korunur.
        yield from _stream_static(warning, t0, mode="summarize")
        return

    hits = _summary_hits(conn, filename)
    if not hits:
        yield from _stream_static(config.NO_ANSWER_TEXT, t0, mode="summarize")
        return

    yield RetrievalEvent(
        hits=hits,
        threshold=0.0,  # bu yolda eşik kavramı yok; hepsi modele gidiyor
        passed_count=len(hits),
        rejected_count=0,
        elapsed_ms=int((time.time() - t0) * 1000),
        mode="summarize",
    )

    prompt = SUMMARY_PROMPT.format(
        filename=filename, context=retrieve.build_context(hits)
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
    yield DoneEvent(
        answered=bool(text),
        reason=None,
        sources=Answer(text, hits).sources if text else [],
        elapsed_ms=int((time.time() - t0) * 1000),
        token_count=token_count,
    )


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

    # Yönlendirme retrieval'dan ÖNCE: meta sorgular benzerlik aramasına hiç
    # girmez (rag/query_router.py -- ölçüm docstring'de).
    docs = store.list_documents(conn) if conn is not None else []
    route = query_router.classify(question, [d["filename"] for d in docs])

    if route.kind == "corpus":
        yield from _stream_static(_corpus_answer(conn), t0, mode="corpus")
        return

    if route.kind == "summarize":
        yield from _stream_summary(question, route, model, conn, t0)
        return

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
    refused = is_refusal(text)
    sources = [] if refused else Answer(text, passed).sources

    yield DoneEvent(
        answered=not refused,
        reason="llm_refused" if refused else None,
        sources=sources,
        elapsed_ms=int((time.time() - t0) * 1000),
        token_count=token_count,
    )
