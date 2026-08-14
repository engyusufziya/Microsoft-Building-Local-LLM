"""
Studio artefaktları için CRUD katmanı (`artifacts` / `artifact_claims` tabloları).

rag/store.py'nin üslubunu izler: bağlantıyı parametre alır, kendi bağlantısını
açmaz, `with conn:` ile transaction kullanır. `quiz_attempts` CRUD'u burada
YOK (Faz 4) -- tablo yalnızca şema göçü olarak Faz 1'de oluşturuldu.

Yazma işlemleri store.clear_cache() ÇAĞIRMAZ: artefakt tabloları embedding
matrisini etkilemez, önbelleği düşürmek gereksiz bir retrieval yavaşlaması
olurdu (FEATURE_SPEC.md §9.7).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional, Sequence

from .fidelity import ClaimBinding


def create_artifact(
    conn: sqlite3.Connection,
    *,
    kind: str,
    scope: str,
    document_id: Optional[int],
    title: str,
    params: dict,
    payload: dict,
    corpus_fingerprint: str,
    fidelity_score: Optional[float],
    generation_ms: Optional[int],
    claims: Sequence[ClaimBinding],
) -> int:
    """Artefaktı ve iddialarını TEK transaction'da yazar, artifacts.id döndürür.

    İddia yazımı patlarsa yarım artefakt kalmaz (upsert_document'ın deseni).
    params/payload JSON'a ensure_ascii=False ile serileştirilir (repo Türkçe;
    kaçışlı JSON okunamaz hale gelir).
    """
    created_at = datetime.now().isoformat(timespec="seconds")
    params_json = json.dumps(params, ensure_ascii=False)
    payload_json = json.dumps(payload, ensure_ascii=False)

    with conn:
        cur = conn.execute(
            """
            INSERT INTO artifacts
                (kind, scope, document_id, title, params_json, payload_json,
                 corpus_fingerprint, fidelity_score, generation_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind, scope, document_id, title, params_json, payload_json,
                corpus_fingerprint, fidelity_score, generation_ms, created_at,
            ),
        )
        artifact_id = int(cur.lastrowid)

        if claims:
            conn.executemany(
                """
                INSERT INTO artifact_claims
                    (artifact_id, node_path, claim_text, chunk_id, score, verdict)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (artifact_id, c.node_path, c.claim_text, c.chunk_id, c.score, c.verdict)
                    for c in claims
                ],
            )

    return artifact_id


def list_artifacts(
    conn: sqlite3.Connection,
    kind: Optional[str] = None,
    scope: Optional[str] = None,
) -> list[dict]:
    """Artefaktları listeler -- payload_json SEÇİLMEZ (bir mind map payload'ı
    büyür ve liste görünümünde hiç kullanılmaz). Sıralama: created_at
    azalan, eşitlikte id azalan.
    """
    query = """
        SELECT id, kind, scope, document_id, title, corpus_fingerprint,
               fidelity_score, generation_ms, created_at
        FROM artifacts
        WHERE 1=1
    """
    args: list = []
    if kind is not None:
        query += " AND kind = ?"
        args.append(kind)
    if scope is not None:
        query += " AND scope = ?"
        args.append(scope)
    query += " ORDER BY created_at DESC, id DESC"

    cur = conn.execute(query, args)
    return [_row_to_summary(r) for r in cur.fetchall()]


def get_artifact(conn: sqlite3.Connection, artifact_id: int) -> Optional[dict]:
    """Tek artefaktı payload + iddialarıyla birlikte döndürür; yoksa None."""
    row = conn.execute(
        """
        SELECT id, kind, scope, document_id, title, params_json, payload_json,
               corpus_fingerprint, fidelity_score, generation_ms, created_at
        FROM artifacts WHERE id = ?
        """,
        (artifact_id,),
    ).fetchone()
    if row is None:
        return None

    result = _row_to_summary(row)
    result["params"] = json.loads(row["params_json"])
    result["payload"] = json.loads(row["payload_json"])

    claim_rows = conn.execute(
        """
        SELECT node_path, claim_text, chunk_id, score, verdict
        FROM artifact_claims WHERE artifact_id = ?
        ORDER BY id
        """,
        (artifact_id,),
    ).fetchall()
    result["claims"] = [
        {
            "node_path": r["node_path"],
            "claim_text": r["claim_text"],
            "chunk_id": r["chunk_id"],
            "score": r["score"],
            "verdict": r["verdict"],
        }
        for r in claim_rows
    ]
    return result


def delete_artifact(conn: sqlite3.Connection, artifact_id: int) -> bool:
    """Artefaktı siler. artifact_claims/quiz_attempts ON DELETE CASCADE ile gider
    (PRAGMA foreign_keys = ON zaten store.connect()'te açık).
    """
    with conn:
        cur = conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        return cur.rowcount > 0


def _row_to_summary(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "scope": row["scope"],
        "document_id": row["document_id"],
        "title": row["title"],
        "corpus_fingerprint": row["corpus_fingerprint"],
        "fidelity_score": row["fidelity_score"],
        "generation_ms": row["generation_ms"],
        "created_at": row["created_at"],
    }
