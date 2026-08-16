"""
Rapor Üreteci -- Studio Faz 2, hattan geçen İLK gerçek artefakt
(FEATURE_SPEC.md §10).

Bölüm planı SABİT, LLM seçmez (§10.3): Yönetici Özeti (EN SON üretilir ama
diziye index 0 olarak yazılır) + Temel Bulgular (1 LLM çağrısı) + küme başına
Detaylı Analiz (küme sayısı kadar LLM çağrısı) + deterministik Tablolar +
deterministik Kaynaklar.

Her bölüm nesri modelden gelir ve TEK savunma noktasından (fidelity.py) iki
katmanda geçer: ham cosine bağlama (bind_claims) + terim desteği
(unverified_terms/should_drop). Bağlanamayan/doğrulanamayan cümle rapordan
ÇIKARILIR; METNİ değil, yalnızca SAYISI ve düşürme sebebi payload["dropped"]'a
gider (§10.5/§10.6). `retrieve.get_top_chunks()` ÇAĞRILMAZ -- bölüm bağlamı
kümeden gelir (§10.4); yalnızca `retrieve.build_context`/`retrieve.Hit`
(pure formatting) yeniden kullanılır.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from typing import Optional

from .. import config, models
from ..retrieve import Hit, build_context
from ..topics import Topic
from .base import GeneratedArtifact, GenerationContext, register
from .fidelity import bind_claims, should_drop, unverified_terms

# --------------------------------------------------------------------------- metin biçimlendirme

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_CITATION_TAG_RE = re.compile(r"\[Kaynak:[^\]]*\]")


def _strip_citations(text: str) -> str:
    """Prompt satır içi [Kaynak: ...] etiketini YASAKLAR ama sızarsa temizler --
    cümlelere bölünmeden ÖNCE (§10 kritik nokta: atıflar citations'tan
    deterministik geliyor, model kendi atıf biçimini üretmemeli)."""
    return _CITATION_TAG_RE.sub("", text)


def _split_paragraphs(raw_text: str) -> list[list[str]]:
    """Ham LLM çıktısını paragraf -> cümle listesine çevirir."""
    text = _strip_citations(raw_text or "").strip()
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    result = []
    for para in paragraphs:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(para) if s.strip()]
        if sentences:
            result.append(sentences)
    return result


# --------------------------------------------------------------------------- örnekleme / bağlam

def _sample_evenly(chunk_ids: list[int], limit: int) -> list[int]:
    """Küme chunk'ları limiti aşarsa eşit aralıklı örnekler; ilk N ALINMAZ.

    store.get_document_chunks'ın özetleme yolundaki ("belgeyi eşit aralıklı
    örnekle, ilk/son korunur") AYNI algoritması -- SUMMARY_MAX_CHUNKS zaten bu
    problemi çözüyor (§10.4), yeni bir sabit eklenmez. store.py'ye dokunma
    yetkim olmadığı için algoritma burada (küçük, saf bir yardımcı olarak)
    tekrarlanır.
    """
    if limit <= 0 or len(chunk_ids) <= limit:
        return list(chunk_ids)
    if limit == 1:
        return [chunk_ids[0]]
    step = (len(chunk_ids) - 1) / (limit - 1)
    picked = sorted({int(round(i * step)) for i in range(limit)})
    return [chunk_ids[i] for i in picked]


def _fetch_chunks(conn: sqlite3.Connection, chunk_ids: list[int]) -> list[sqlite3.Row]:
    """chunk_ids sırasını KORUYARAK satırları döner (SQL IN sırayı garanti etmez)."""
    if not chunk_ids:
        return []
    placeholders = ",".join("?" for _ in chunk_ids)
    rows = conn.execute(
        f"SELECT id, source, page, content, via_ocr FROM chunks WHERE id IN ({placeholders})",
        chunk_ids,
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


def _context_for(conn: sqlite3.Connection, chunk_ids: list[int]) -> tuple[str, list[int]]:
    """Bir bölümün model bağlamını kurar: eşit aralıklı örnekle, retrieve.build_context
    ile AYNI numaralandırılmış/kaynak etiketli biçime çevir (§10.4).

    Döner: (bağlam metni, GERÇEKTEN örneklenen chunk id'leri).
    """
    sampled = _sample_evenly(chunk_ids, config.SUMMARY_MAX_CHUNKS)
    rows = _fetch_chunks(conn, sampled)
    hits = [
        Hit(score=0.0, source=r["source"], page=r["page"], content=r["content"],
            via_ocr=bool(r["via_ocr"]))
        for r in rows
    ]
    return build_context(hits), [r["id"] for r in rows]


def _dedupe_preserve_order(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# --------------------------------------------------------------------------- promptlar
#
# "en fazla N cümle" sınırı SYSTEM_PROMPT (rag/answer.py) deseninin aynısı:
# doğrudan prompt metnine gömülür, config sabiti olmaz (o da öyle).

_SECTION_PROMPT = """Sen yerel bir belge asistanısın. Aşağıdaki bağlamı kullanarak \
Türkçe, en fazla 6 cümlelik bir rapor bölümü yaz.

Kurallar:
- Yalnızca bağlamdaki bilgiyi kullan. Kendi bilgini ekleme, tahmin yürütme, sayı uydurma.
- Bölüm başlığı YAZMA -- başlık ayrıca ekleniyor.
- Kaynak numarası, dosya adı veya [Kaynak: ...] etiketi YAZMA; atıflar sistem \
tarafından ayrıca ekleniyor.
- Düz nesir yaz; madde işareti veya numaralandırma kullanma.
- Kendini tekrar etme.

Bağlam:
{context}"""

_EXEC_PROMPT = """Sen yerel bir belge asistanısın. Aşağıda bir raporun ÖNCEDEN \
üretilmiş bölümleri var. Bunlara dayanarak Türkçe, en fazla 4 cümlelik bir \
"Yönetici Özeti" yaz.

Kurallar:
- Yalnızca aşağıdaki bölümlerde geçen bilgiyi kullan; yeni bir bilgi ekleme.
- Bölüm başlığı YAZMA -- başlık ayrıca ekleniyor.
- Kaynak numarası, dosya adı veya [Kaynak: ...] etiketi YAZMA.
- Düz nesir yaz; madde işareti kullanma.
- Kendini tekrar etme.

Rapor bölümleri:
{sections_text}"""


def _generate_section_text(client, context: str) -> str:
    response = client.complete_chat(
        [
            {"role": "system", "content": _SECTION_PROMPT.format(context=context)},
            {"role": "user", "content": "Bu bölümü yaz."},
        ]
    )
    return (response.choices[0].message.content or "").strip()


def _generate_exec_text(client, sections_text: str) -> str:
    response = client.complete_chat(
        [
            {"role": "system", "content": _EXEC_PROMPT.format(sections_text=sections_text)},
            {"role": "user", "content": "Yönetici özetini yaz."},
        ]
    )
    return (response.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------- sadakat: bağla + düşürme kararı

def _bind_and_filter(
    conn: sqlite3.Connection,
    entries: list[tuple[str, list[int], list[list[str]]]],
) -> tuple[list[tuple[str, int, int, str, Optional[int]]], list[dict]]:
    """Bir grup bölümün (section_id, context_chunk_ids, paragraphs) üçlülerini
    TEK bir bind_claims çağrısında bağlar, ikinci katmandan geçirir.

    Döner:
      kept  -- (section_id, paragraf_idx, cümle_idx, cümle, bound_chunk_id) listesi
      dropped -- {"section_id", "text", "reason", "score", "terms"} sözlük listesi,
                 KEŞİF SIRASINDA (bölüm sırası, sonra paragraf, sonra cümle).
    """
    flat: list[tuple[str, str, str, int, int]] = []
    context_by_section: dict[str, list[int]] = {}
    for section_id, context_ids, paragraphs in entries:
        context_by_section[section_id] = context_ids
        for pi, sentences in enumerate(paragraphs):
            for si, sentence in enumerate(sentences):
                flat.append((f"{section_id}:{pi}:{si}", section_id, sentence, pi, si))

    if not flat:
        return [], []

    bindings = bind_claims(conn, [(key, sentence) for key, _, sentence, _, _ in flat])
    binding_by_key = {b.node_path: b for b in bindings}

    kept: list[tuple[str, int, int, str, Optional[int]]] = []
    dropped: list[dict] = []
    for key, section_id, sentence, pi, si in flat:
        binding = binding_by_key[key]
        unverified: list[str] = []
        if binding.verdict == "grounded":
            ctx_ids = context_by_section[section_id]
            if not ctx_ids:
                # §10.6: context_chunk_ids boşsa bağlanan chunk kullanılır --
                # katman sessizce kapanmaz.
                ctx_ids = [binding.chunk_id] if binding.chunk_id is not None else []
            unverified = unverified_terms(conn, sentence, ctx_ids)
        reason = should_drop(binding, unverified)
        if reason is None:
            kept.append((section_id, pi, si, sentence, binding.chunk_id))
        else:
            dropped.append(
                {
                    "section_id": section_id,
                    "text": sentence,
                    "reason": reason,
                    "score": binding.score,
                    "terms": unverified if reason == "unverified_terms" else [],
                }
            )
    return kept, dropped


def _group_kept_paragraphs(
    kept: list[tuple[str, int, int, str, Optional[int]]]
) -> dict[str, list[list[str]]]:
    """kept listesini section_id -> paragraf(cümle listesi) sözlüğüne çevirir.

    Düşürülen cümleler zaten kept'te yok; bir paragrafın TÜM cümleleri
    düşmüşse o paragraf boş kalmaz -- payload'da HİÇ görünmez (anlamsız
    boş yapı üretilmez, CLAUDE.md §2.2).
    """
    by_section: dict[str, dict[int, dict[int, str]]] = {}
    for section_id, pi, si, sentence, _chunk_id in kept:
        by_section.setdefault(section_id, {}).setdefault(pi, {})[si] = sentence

    result: dict[str, list[list[str]]] = {}
    for section_id, paras in by_section.items():
        ordered = []
        for pi in sorted(paras):
            sentences = [paras[pi][si] for si in sorted(paras[pi])]
            if sentences:
                ordered.append(sentences)
        result[section_id] = ordered
    return result


# --------------------------------------------------------------------------- deterministik parçalar

def _all_chunk_sources(conn: sqlite3.Connection) -> dict[int, str]:
    return {row["id"]: row["source"] for row in conn.execute("SELECT id, source FROM chunks")}


def _detail_title(topic: Topic, sources_by_chunk: dict[int, str]) -> str:
    """§10.3: 'detail-{k}' başlığı, kümenin en çok chunk katkısı yapan
    belgesinden türetilir: '{belge_adı} ({n} bölüm)'. Eşitlikte deterministik
    olarak alfabetik en küçük belge adı kazanır."""
    counts = Counter(sources_by_chunk[cid] for cid in topic.chunk_ids if cid in sources_by_chunk)
    if not counts:
        return f"Küme {topic.id}"
    top_source, n = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return f"{top_source} ({n} bölüm)"


def _coverage_table(topics: list[Topic], sources_by_chunk: dict[int, str]) -> dict:
    """§10.7: TEK deterministik tablo -- belge x konu kapsama matrisi. LLM görmez."""
    sources = sorted(set(sources_by_chunk.values()))
    columns = ["Belge"] + [f"K{t.id}" for t in topics]
    rows = []
    for source in sources:
        row: list = [source]
        for topic in topics:
            count = sum(1 for cid in topic.chunk_ids if sources_by_chunk.get(cid) == source)
            row.append(count)
        rows.append(row)
    return {"id": "coverage", "title": "Belge × Konu Kapsama", "columns": columns, "rows": rows}


def _citations_from(conn: sqlite3.Connection, bound_chunk_ids: list[Optional[int]]) -> list[dict]:
    """§10.8: citations yalnızca RAPORA GİREN iddiaların bağlandığı BENZERSİZ
    chunk'lardan türer. Biçim retrieve.Hit.citation() ile BİREBİR AYNI (yeniden
    üretilmez). Sıra: source alfabetik, sonra page artan."""
    unique_ids = sorted({cid for cid in bound_chunk_ids if cid is not None})
    rows = _fetch_chunks(conn, unique_ids)
    items = []
    for row in rows:
        hit = Hit(score=0.0, source=row["source"], page=row["page"], content=row["content"],
                   via_ocr=bool(row["via_ocr"]))
        items.append(
            {"chunk_id": row["id"], "source": row["source"], "page": row["page"],
             "citation": hit.citation()}
        )
    items.sort(key=lambda it: (it["source"], it["page"] or 0))
    return items


def _report_title(conn: sqlite3.Connection, scope: str, document_id: Optional[int]) -> str:
    if scope == "document" and document_id is not None:
        row = conn.execute(
            "SELECT filename FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is not None:
            return f"{row['filename']} Raporu"
    return "Korpus Raporu"


# --------------------------------------------------------------------------- üretici

class ReportGenerator:
    kind = "report"

    def generate(self, ctx: GenerationContext) -> GeneratedArtifact:
        conn = ctx.conn
        topics = sorted(ctx.topics, key=lambda t: t.id)  # §10.3: küme sırasında (Topic.id artan)
        client = models.get_chat_client(max_tokens=config.ARTIFACT_SECTION_MAX_TOKENS)

        # LLM çağrısı başına ilerleme: findings + küme başına detay + exec.
        # 12 çağrı dakikalar sürüyor (§10.2), bu yüzden `progress` zorunlu.
        # Ölçek §9.5'te DONDURULDU: 0-100 TAM SAYI (/api/documents'ın 0.0-1.0'ı
        # DEĞİL) -- iki akış birleştirilmez.
        total_sections = 1 + len(topics) + 1
        written = 0

        def _section_written() -> None:
            nonlocal written
            written += 1
            ctx.emit(
                "progress",
                {
                    "pct": round(written * 100 / total_sections),
                    "detail": f"{written}/{total_sections} bölüm yazıldı",
                },
            )

        # 1) Temel Bulgular: her kümenin merkeze en yakın 1. chunk'ı (§10.4).
        findings_ctx_text, findings_ctx_ids = _context_for(
            conn, [t.chunk_ids[0] for t in topics]
        )
        findings_paragraphs = _split_paragraphs(_generate_section_text(client, findings_ctx_text))
        _section_written()

        # 2) Detaylı Analiz: küme başına, kümenin TÜM chunk'ları (§10.4).
        sources_by_chunk = _all_chunk_sources(conn)
        detail_entries: list[tuple[str, list[int], list[list[str]]]] = []
        detail_titles: dict[str, str] = {}
        detail_topic_id: dict[str, int] = {}
        for topic in topics:
            section_id = f"detail-{topic.id}"
            ctx_text, ctx_ids = _context_for(conn, topic.chunk_ids)
            paragraphs = _split_paragraphs(_generate_section_text(client, ctx_text))
            _section_written()
            detail_entries.append((section_id, ctx_ids, paragraphs))
            detail_titles[section_id] = _detail_title(topic, sources_by_chunk)
            detail_topic_id[section_id] = topic.id

        # 3) Sadakat (findings + details): tek toplu bind_claims çağrısı.
        pre_entries = [("findings", findings_ctx_ids, findings_paragraphs)] + detail_entries
        pre_kept, pre_dropped = _bind_and_filter(conn, pre_entries)
        pre_kept_paragraphs = _group_kept_paragraphs(pre_kept)

        # 4) Yönetici Özeti: EN SON üretilir, girdisi diğer bölümlerin
        # ÜRETİLMİŞ (ve zaten sadakatten geçmiş) metnidir -- chunk bağlamı yok.
        section_titles = {"findings": "Temel Bulgular", **detail_titles}
        section_order = ["findings"] + [sid for sid, _, _ in detail_entries]
        sections_text_parts = []
        for section_id in section_order:
            paras = pre_kept_paragraphs.get(section_id, [])
            if not paras:
                continue
            body = "\n".join(" ".join(sentences) for sentences in paras)
            sections_text_parts.append(f"{section_titles[section_id]}\n{body}")
        sections_text = "\n\n".join(sections_text_parts)

        exec_ctx_ids = _dedupe_preserve_order(
            findings_ctx_ids + [cid for _, ctx_ids, _ in detail_entries for cid in ctx_ids]
        )
        exec_paragraphs = _split_paragraphs(_generate_exec_text(client, sections_text))
        _section_written()

        exec_kept, exec_dropped = _bind_and_filter(
            conn, [("exec", exec_ctx_ids, exec_paragraphs)]
        )
        exec_kept_paragraphs = _group_kept_paragraphs(exec_kept)

        # 5) Final montaj: sections dizisi HER ZAMAN exec (index 0) ile başlar.
        final_order = ["exec", "findings"] + [sid for sid, _, _ in detail_entries]
        section_meta = {
            "exec": ("executive_summary", "Yönetici Özeti", None, exec_ctx_ids),
            "findings": ("key_findings", "Temel Bulgular", None, findings_ctx_ids),
        }
        for section_id, ctx_ids, _paragraphs in detail_entries:
            section_meta[section_id] = (
                "detailed_analysis", detail_titles[section_id],
                detail_topic_id[section_id], ctx_ids,
            )
        kept_paragraphs_by_section = {**pre_kept_paragraphs, **exec_kept_paragraphs}

        sections_payload = []
        for section_id in final_order:
            kind, title, topic_id, ctx_ids = section_meta[section_id]
            paragraphs = kept_paragraphs_by_section.get(section_id, [])
            sections_payload.append(
                {
                    "id": section_id,
                    "kind": kind,
                    "title": title,
                    "topic_id": topic_id,
                    "context_chunk_ids": ctx_ids,
                    "paragraphs": [{"sentences": sentences} for sentences in paragraphs],
                }
            )

        dropped_by_section: dict[str, list[dict]] = {}
        for item in pre_dropped + exec_dropped:
            dropped_by_section.setdefault(item["section_id"], []).append(item)
        dropped_payload = []
        for section_id in final_order:
            dropped_payload.extend(dropped_by_section.get(section_id, []))

        # 6) Tablolar (deterministik, LLM görmez).
        tables_payload = [_coverage_table(topics, sources_by_chunk)]

        # 7) Atıflar: yalnızca RAPORA GİREN iddiaların bağlandığı chunk'lar.
        bound_chunk_ids = [chunk_id for *_rest, chunk_id in (pre_kept + exec_kept)]
        citations_payload = _citations_from(conn, bound_chunk_ids)

        payload = {
            "kind": "report",
            "outline": [
                "executive_summary", "key_findings", "detailed_analysis",
                "tables", "citations",
            ],
            "sections": sections_payload,
            "tables": tables_payload,
            "citations": citations_payload,
            "dropped": dropped_payload,
        }

        # 8) Claims: TÜM iddialar (rapora giren + düşürülen) -- node_path FİNAL
        # dizi konumuna göre. base.py 4. adımda bunları TEKRAR bağlar (kasıtlı,
        # bkz. modül docstring'i); burada YALNIZCA doğru node_path üretilir.
        claims: list[tuple[str, str]] = []
        for i, section in enumerate(sections_payload):
            for j, paragraph in enumerate(section["paragraphs"]):
                for k, sentence in enumerate(paragraph["sentences"]):
                    claims.append((f"/sections/{i}/paragraphs/{j}/sentences/{k}", sentence))
        for i, item in enumerate(dropped_payload):
            claims.append((f"/dropped/{i}", item["text"]))

        title = _report_title(conn, ctx.scope, ctx.document_id)
        return GeneratedArtifact(title=title, payload=payload, claims=claims)


# --------------------------------------------------------------------------- markdown export

def to_markdown(payload: dict) -> str:
    """payload_json'dan markdown üretir (§10.11: rota yalnızca çağırır, iş
    mantığı burada). Düşürülen iddiaların METNİ gövdeye GİRMEZ, yalnızca
    SAYISI dipnot olur. Hiçbir http(s):// üretilmez."""
    lines: list[str] = []

    for section in payload.get("sections", []):
        lines.append(f"## {section['title']}")
        lines.append("")
        for paragraph in section.get("paragraphs", []):
            sentences = paragraph.get("sentences", [])
            if sentences:
                lines.append(" ".join(sentences))
                lines.append("")

    tables = payload.get("tables", [])
    if tables:
        lines.append("## Tablolar")
        lines.append("")
        for table in tables:
            lines.append(f"### {table['title']}")
            lines.append("")
            columns = table.get("columns", [])
            lines.append("| " + " | ".join(str(c) for c in columns) + " |")
            lines.append("|" + "|".join("---" for _ in columns) + "|")
            for row in table.get("rows", []):
                lines.append("| " + " | ".join(str(v) for v in row) + " |")
            lines.append("")

    citations = payload.get("citations", [])
    if citations:
        lines.append("## Kaynaklar")
        lines.append("")
        for citation in citations:
            lines.append(f"- {citation['citation']}")
        lines.append("")

    dropped = payload.get("dropped", [])
    if dropped:
        lines.append("---")
        lines.append("")
        lines.append(
            f"*{len(dropped)} iddia kaynağa yeterince bağlanamadığı için rapordan "
            f"çıkarıldı; metinleri gösterilmez.*"
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


register(ReportGenerator())
