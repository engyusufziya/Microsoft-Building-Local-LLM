"""
Zihin Haritası Üreteci -- Studio Faz 3 (FEATURE_SPEC.md §11).

HARİTAYI LLM ÇİZMEZ. Yapı embedding'lerden deterministik çıkar (rag/topics.py);
LLM'in tek işi kümelere isim vermektir. Gerekçe (STUDIO_PLAN §6.1): LLM'e
"korpusu haritala" demek düğümlerin belgede gerçekten var olup olmadığını
doğrulanamaz kılar. Küme yaklaşımında her düğüm ZATEN bir chunk kümesidir --
hallüsinasyon yapısal olarak imkânsız, yalnızca ETİKET yanlış olabilir ve o da
tıklanarak doğrulanır.

Faz 2'nin iki katmanlı savunması (bind_claims + unverified_terms/should_drop)
etiketlere OLDUĞU GİBİ uygulanır. Rapordan FARKI: kapıdan geçemeyen etiket
düğümü YOK ETMEZ -- düğüm korpusun gerçek bir parçasıdır, silinmesi
rag/topics.py'nin "artık kümeyi atma, emil" kuralının (kümeleri sessizce yok
etme) aynı ihlali olurdu. Bunun yerine etiket, korpustan türeyen DETERMİNİSTİK
ada düşer (topics.topic_title) ve modelin önerisi payload["dropped"]'a sebebiyle
yazılır.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Optional

from .. import config, models
from ..retrieve import Hit, build_context
from ..topics import Topic, topic_similarity, topic_title
from .base import GeneratedArtifact, GenerationContext, register
from .fidelity import bind_claims, should_drop, unverified_terms

# --------------------------------------------------------------------------- etiket temizleme

# Modelin prompt'a rağmen ürettiği süslemeler: markdown vurgusu, tırnak,
# "Konu:" gibi önek, sondaki noktalama. Rapor tarafında AYNI sorun kayda
# geçmişti (PROJE_DURUMU "Görülen kozmetik kusur") -- orada cümleler düz metin
# basıldığı için yıldızlar ekranda görünüyordu. Etiket bir düğüm adı olduğu
# için burada temizlik zorunlu: "**Chunking**" bir konu adı değildir.
_LABEL_PREFIX_RE = re.compile(r"^\s*(?:konu|başlık|ortak konu|cevap)\s*:\s*", re.IGNORECASE)
_LABEL_STRIP_CHARS = " \t\"'`*_#.:;,-–—"

# Prompt "en fazla 5 kelime" diyor. Daha uzun bir çıktı, modelin biçimi
# tutturamadığı anlamına gelir ve bir SVG düğümünde okunmaz; sayı prompt
# metninin kendisiyle aynı yerde durur (rag/answer.py'nin "en fazla 3 cümle"
# deseni -- config sabiti olmaz).
_LABEL_MAX_WORDS = 5


def _clean_label(raw: str) -> str:
    """Ham LLM çıktısını düğüm etiketine indirger; biçim tutmuyorsa boş döner.

    Yalnızca İLK satır alınır (model bazen açıklama satırı ekliyor), önek ve
    süsleme kırpılır. Sonuç boşsa ya da _LABEL_MAX_WORDS'ten uzunsa etiket
    GEÇERSİZDİR -- çağıran taraf deterministik yedeğe düşer.
    """
    first_line = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
    cleaned = _LABEL_PREFIX_RE.sub("", first_line).strip(_LABEL_STRIP_CHARS)
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned or len(cleaned.split()) > _LABEL_MAX_WORDS:
        return ""
    return cleaned


# --------------------------------------------------------------------------- prompt

# REDDEDİLEN KURAL -- ÖLÇÜLDÜ, İŞE YARAMADI (§11.4): prompt'a "CÜMLE DÜZENİ
# kullan, Her Kelimeyi Büyük Harfle Başlatma" maddesi eklendi ve aynı korpusta
# yeniden koşuldu. Model kuralı YOK SAYDI; üstelik bir etiketi "Embedding ve
# Benzerlik Analizi"nden "Embedding Ve Benzerlik Analizi"ne çevirerek daha da
# Başlık Düzenine soktu. Düşen etiket sayısı 3/7'de kaldı. Madde geri alındı --
# işlemeyen bir kuralı prompt'ta tutmak, çalıştığını ima eder. Sorun kapının
# ÇAĞRILMA biçiminde çözüldü (unverified_terms(..., is_title=True)).
_LABEL_PROMPT = """Sen yerel bir belge asistanısın. Aşağıdaki belge parçalarının \
ORTAK konusunu Türkçe bir başlık olarak yaz.

Kurallar:
- En fazla 5 kelime.
- Yalnızca başlığı yaz; cümle kurma, açıklama ekleme, noktalama koyma.
- Yalnızca bağlamdaki bilgiyi kullan; kendi bilgini ekleme.
- Kaynak numarası, dosya adı veya [Kaynak: ...] etiketi YAZMA.

Bağlam:
{context}"""


def _generate_label(client, context: str) -> str:
    response = client.complete_chat(
        [
            {"role": "system", "content": _LABEL_PROMPT.format(context=context)},
            {"role": "user", "content": "Ortak konu başlığını yaz."},
        ]
    )
    return (response.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------- korpus okuma

def _chunk_rows(conn: sqlite3.Connection, chunk_ids: list[int]) -> list[sqlite3.Row]:
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


def _label_context(conn: sqlite3.Connection, topic: Topic) -> tuple[str, list[int]]:
    """Etiket çağrısının bağlamı: merkeze EN YAKIN ilk N chunk (§11.4).

    Sıra `Topic.chunk_ids`'ten gelir -- rag/topics.py onu merkeze yakınlıkta
    AZALAN sırada üretiyor, yani ilk N zaten "merkeze en yakın N"dir. Biçim
    retrieve.build_context ile aynı (numaralı, kaynak etiketli).
    """
    picked = topic.chunk_ids[: config.MINDMAP_LABEL_CONTEXT_CHUNKS]
    rows = _chunk_rows(conn, picked)
    hits = [
        Hit(score=0.0, source=r["source"], page=r["page"], content=r["content"],
            via_ocr=bool(r["via_ocr"]))
        for r in rows
    ]
    return build_context(hits), [r["id"] for r in rows]


def _node_citations(conn: sqlite3.Connection, chunk_ids: list[int]) -> list[dict]:
    """Düğümün TÜM chunk'larının kaynak etiketleri (§11.5: "her düğüm kaynağa
    tıklanabilir"). Biçim retrieve.Hit.citation() ile birebir aynı; sıra kaynak
    adı, sonra sayfa."""
    items = []
    for row in _chunk_rows(conn, sorted(chunk_ids)):
        hit = Hit(score=0.0, source=row["source"], page=row["page"],
                  content=row["content"], via_ocr=bool(row["via_ocr"]))
        items.append(
            {"chunk_id": row["id"], "source": row["source"], "page": row["page"],
             "citation": hit.citation()}
        )
    items.sort(key=lambda it: (it["source"], it["page"] or 0))
    return items


def _all_chunk_sources(conn: sqlite3.Connection) -> dict[int, str]:
    return {row["id"]: row["source"] for row in conn.execute("SELECT id, source FROM chunks")}


def _map_title(conn: sqlite3.Connection, scope: str, document_id: Optional[int]) -> str:
    if scope == "document" and document_id is not None:
        row = conn.execute(
            "SELECT filename FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is not None:
            return f"{row['filename']} Zihin Haritası"
    return "Korpus Zihin Haritası"


# --------------------------------------------------------------------------- kenarlar

def _edges(topics: list[Topic]) -> list[dict]:
    """Küme merkezleri arası HAM cosine eşiği aşan çiftler (§11.6).

    `weight` HAM COSINE'dır ve yeniden ölçeklenmez (AGENTS.md §1.1'in aynı
    gerekçesi: gösterilen sayı ölçülen sayı olmalı). Sıra deterministik:
    ağırlık azalan, eşitlikte düğüm kimliği artan.

    Hiç kenar çıkmaması HATA DEĞİLDİR -- kümeler gerçekten uzaksa harita
    yıldız olarak çizilir (bkz. config.MINDMAP_EDGE_MIN_SIMILARITY ölçümü).
    """
    edges = []
    for i in range(len(topics)):
        for j in range(i + 1, len(topics)):
            weight = topic_similarity(topics[i], topics[j])
            if weight > config.MINDMAP_EDGE_MIN_SIMILARITY:
                edges.append(
                    {
                        "from": f"n{topics[i].id}",
                        "to": f"n{topics[j].id}",
                        "relation": "related",
                        "weight": weight,
                    }
                )
    edges.sort(key=lambda e: (-e["weight"], e["from"], e["to"]))
    return edges


# --------------------------------------------------------------------------- üretici

class MindMapGenerator:
    kind = "mindmap"

    def generate(self, ctx: GenerationContext) -> GeneratedArtifact:
        conn = ctx.conn
        topics = sorted(ctx.topics, key=lambda t: t.id)
        client = models.get_chat_client(max_tokens=config.ARTIFACT_LABEL_MAX_TOKENS)
        sources_by_chunk = _all_chunk_sources(conn)

        # 1) Küme başına TEK LLM çağrısı: etiket. `pct` ölçeği §9.5'te
        # dondurulmuş 0-100 TAM SAYIDIR.
        proposals: list[tuple[Topic, str, list[int]]] = []
        for index, topic in enumerate(topics, start=1):
            context_text, context_ids = _label_context(conn, topic)
            label = _clean_label(_generate_label(client, context_text))
            proposals.append((topic, label, context_ids))
            ctx.emit(
                "progress",
                {
                    "pct": round(index * 100 / len(topics)),
                    "detail": f"{index}/{len(topics)} küme etiketlendi",
                },
            )

        # 2) Sadakat: yalnızca BİÇİMİ geçerli etiketler kapıya girer. Biçimi
        # bozuk etiket kapıya hiç sokulmaz -- bind_claims'e boş dize vermek
        # anlamsız bir skor üretirdi.
        gate_input = [
            (f"topic-{topic.id}", label) for topic, label, _ in proposals if label
        ]
        bindings = {b.node_path: b for b in bind_claims(conn, gate_input)}

        accepted: dict[int, str] = {}
        dropped_payload: list[dict] = []
        for topic, label, context_ids in proposals:
            if not label:
                dropped_payload.append(
                    {
                        "topic_id": topic.id,
                        "text": "",
                        "reason": "label_invalid",
                        "score": None,
                        "terms": [],
                    }
                )
                continue

            binding = bindings[f"topic-{topic.id}"]
            unverified: list[str] = []
            if binding.verdict == "grounded":
                ids = context_ids or (
                    [binding.chunk_id] if binding.chunk_id is not None else []
                )
                # is_title=True: etiket bir BAŞLIKTIR, büyük harfi süslemedir
                # (§11.4 ölçümü). Rakam kolu çalışmaya devam eder -- uydurma
                # model kimliği ("GPT-4 mimarisi") hâlâ yakalanır.
                unverified = unverified_terms(conn, label, ids, is_title=True)
            reason = should_drop(binding, unverified)
            if reason is None:
                accepted[topic.id] = label
            else:
                dropped_payload.append(
                    {
                        "topic_id": topic.id,
                        "text": label,
                        "reason": reason,
                        "score": binding.score,
                        "terms": unverified if reason == "unverified_terms" else [],
                    }
                )

        # 3) Düğümler. nodes[0] KÖK'tür ve LLM üretimi DEĞİLDİR (korpus
        # metadatası) -- bu yüzden iddiası da yoktur.
        total_chunks = sum(t.size for t in topics)
        nodes: list[dict] = [
            {
                "id": "root",
                "label": _map_title(conn, ctx.scope, ctx.document_id),
                "kind": "root",
                "parent": None,
                "topic_id": None,
                "chunk_ids": [],
                "size": total_chunks,
                "label_source": "corpus",
                "citations": [],
            }
        ]
        for topic in topics:
            model_label = accepted.get(topic.id)
            nodes.append(
                {
                    "id": f"n{topic.id}",
                    "label": model_label or topic_title(topic, sources_by_chunk),
                    "kind": "topic",
                    "parent": "root",
                    "topic_id": topic.id,
                    "chunk_ids": list(topic.chunk_ids),
                    "size": topic.size,
                    # DÜRÜSTLÜK ALANI: etiketi model mi önerdi, yoksa kapıdan
                    # geçemediği için korpustan mı türetildi? Arayüz bunu
                    # göstermek zorunda (§11.5).
                    "label_source": "model" if model_label else "fallback",
                    "citations": _node_citations(conn, topic.chunk_ids),
                }
            )

        payload = {
            "kind": "mindmap",
            "nodes": nodes,
            "edges": _edges(topics),
            "dropped": dropped_payload,
        }

        # 4) Claims: yalnızca MODEL etiketleri iddiadır. Yedek etiket korpustan
        # deterministik türüyor (topics.topic_title) -- onu "iddia" sayıp
        # sadakat oranına katmak, ölçülmemiş bir şeyi ölçülmüş göstermek olurdu.
        claims: list[tuple[str, str]] = []
        for index, node in enumerate(nodes):
            if node["label_source"] == "model":
                claims.append((f"/nodes/{index}/label", node["label"]))
        for index, item in enumerate(dropped_payload):
            if item["text"]:
                claims.append((f"/dropped/{index}", item["text"]))

        return GeneratedArtifact(
            title=_map_title(conn, ctx.scope, ctx.document_id),
            payload=payload,
            claims=claims,
        )


# --------------------------------------------------------------------------- markdown export

def to_markdown(payload: dict) -> str:
    """payload_json'dan markdown üretir (§11.8). Rota yalnızca çağırır.

    Düşürülen etiketlerin METNİ gövdeye girmez, yalnızca SAYISI dipnot olur --
    rapor export'unun (§10.11) aynı kuralı. Hiçbir http(s):// üretilmez.
    """
    nodes = payload.get("nodes", [])
    by_id = {node["id"]: node for node in nodes}
    lines: list[str] = []

    root = next((n for n in nodes if n.get("kind") == "root"), None)
    if root is not None:
        lines.append(f"## {root['label']}")
        lines.append("")

    for node in nodes:
        if node.get("kind") == "root":
            continue
        suffix = " *(korpustan türetilmiş ad)*" if node.get("label_source") == "fallback" else ""
        lines.append(f"- **{node['label']}**{suffix} — {node['size']} bölüm")
        for citation in node.get("citations", []):
            lines.append(f"    - {citation['citation']}")
    lines.append("")

    edges = payload.get("edges", [])
    if edges:
        lines.append("## İlişkiler")
        lines.append("")
        for edge in edges:
            source = by_id.get(edge["from"], {}).get("label", edge["from"])
            target = by_id.get(edge["to"], {}).get("label", edge["to"])
            lines.append(f"- {source} — {target} ({edge['weight']:.4f})")
        lines.append("")

    dropped = payload.get("dropped", [])
    if dropped:
        lines.append("---")
        lines.append("")
        lines.append(
            f"*{len(dropped)} etiket önerisi kaynağa yeterince bağlanamadığı için "
            f"haritaya alınmadı; ilgili düğümler korpustan türetilmiş adla "
            f"gösteriliyor.*"
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


register(MindMapGenerator())
