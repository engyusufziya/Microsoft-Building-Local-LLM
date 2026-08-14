"""
Studio artefakt hattının protokolü ve ortak akışı.

Beş adım (seçim, yapı, üretim, sadakat, kayıt) var; 1, 2, 4 ve 5. adımlar
burada TEK KEZ yazılır, modül başına değişen yalnızca 3. adımdır (kayıtlı
ArtifactGenerator.generate).

FAZ 1'DE REGISTRY BOŞTUR: register() hiç çağrılmaz, get_generator() her
`kind` için None döner. generate_artifact bu durumda 1. ve 2. adımları
GERÇEKTEN çalıştırır (bu iki adım Faz 1'de tamamen çalışır durumda), sonra
3. adımda GenerationFailedError fırlatır. Bu ölü kod değil, sistemin gerçek
durumudur: hat kuruludur, üretici henüz takılmamıştır. Faz 2 tek satır
`register(ReportGenerator())` ekler (FEATURE_SPEC.md §9.5).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from .. import store
from ..topics import Topic, cluster_corpus
from .fidelity import bind_claims, fidelity_score
from .store import create_artifact

ProgressCb = Callable[[str, dict], None]


class GenerationFailedError(RuntimeError):
    """3. adım (üretim) başarısız oldu -- ya da (Faz 1'de her zaman) kayıtlı
    üretici yok."""


@dataclass(frozen=True)
class GenerationContext:
    conn: sqlite3.Connection
    scope: str                    # 'corpus' | 'document'
    document_id: Optional[int]
    params: dict
    topics: list[Topic]           # 2. adımın çıktısı, hat tarafından verilir
    emit: ProgressCb


@dataclass(frozen=True)
class GeneratedArtifact:
    title: str
    payload: dict                          # payload_json'a gider
    claims: list[tuple[str, str]]          # (node_path, claim_text)


class ArtifactGenerator(Protocol):
    kind: str

    def generate(self, ctx: GenerationContext) -> GeneratedArtifact: ...


_registry: dict[str, ArtifactGenerator] = {}


def register(generator: ArtifactGenerator) -> None:
    """Bir üretici kaydeder. Faz 1'de HİÇ çağrılmaz -- registry boş kalır."""
    _registry[generator.kind] = generator


def get_generator(kind: str) -> Optional[ArtifactGenerator]:
    """Kayıtlı üreticiyi döndürür; yoksa None (Faz 1'de her zaman None)."""
    return _registry.get(kind)


def generate_artifact(
    conn: sqlite3.Connection,
    *,
    kind: str,
    scope: str,
    document_id: Optional[int],
    params: dict,
    emit: ProgressCb,
) -> int:
    """Beş adımlı Studio hattını çalıştırır, artifacts.id döndürür.

    3. adımda kayıtlı üretici yoksa (Faz 1'in her zamanki durumu)
    GenerationFailedError fırlatır -- 1. ve 2. adımlar buna kadar GERÇEKTEN
    çalışmıştır ve `stage` olayları GERÇEKTEN yayılmıştır.
    """
    start = time.monotonic()

    # 1) Seçim: scope -> hangi belge(ler) kümelenecek.
    emit("stage", {"stage": "selection", "label": "Kaynaklar seçiliyor"})
    if scope == "document" and document_id is not None:
        row = conn.execute(
            "SELECT id FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"document_id={document_id} bulunamadı.")

    # 2) Yapı: embedding kümeleme (rag/topics.py). N < TOPIC_MIN_CLUSTER_SIZE
    # veya boş korpusta InsufficientCorpusError fırlar -- çağıran taraf
    # (backend) bunu akış açılmadan ÖNCE ayrıca kontrol eder.
    emit("stage", {"stage": "clustering", "label": "Konular çıkarılıyor"})
    topics = cluster_corpus(conn)

    ctx = GenerationContext(
        conn=conn,
        scope=scope,
        document_id=document_id,
        params=params,
        topics=topics,
        emit=emit,
    )

    # 3) Üretim: kayıtlı üretici. Faz 1'de registry boş -- burada durur.
    emit("stage", {"stage": "generation", "label": "İçerik üretiliyor"})
    generator = get_generator(kind)
    if generator is None:
        raise GenerationFailedError(
            f"'{kind}' için kayıtlı bir üretici yok (Faz 1'de registry boş; "
            f"bkz. rag/artifacts/base.py::register)."
        )
    generated = generator.generate(ctx)

    # 4) Sadakat: her iddia bir chunk'a bağlanır, KAPI burada.
    emit("stage", {"stage": "fidelity", "label": "Kaynaklar doğrulanıyor"})
    bindings = bind_claims(conn, generated.claims)
    score = fidelity_score(bindings)

    # 5) Kayıt.
    generation_ms = int((time.monotonic() - start) * 1000)
    artifact_id = create_artifact(
        conn,
        kind=kind,
        scope=scope,
        document_id=document_id,
        title=generated.title,
        params=params,
        payload=generated.payload,
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=score,
        generation_ms=generation_ms,
        claims=bindings,
    )
    return artifact_id
