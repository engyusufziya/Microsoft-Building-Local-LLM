"""
Sadakat kapısı (fidelity gate) -- Studio hattının TEK savunma noktası.

Her iddia bir chunk'a bağlanır, bağ HAM COSINE ile ölçülür (retrieval'la aynı
asimetrik embed yolu -- USE_QUERY_INSTRUCTION sözleşmesi burada da geçerli,
aksi halde skorlar Hit.score ile karşılaştırılabilir olmaz), ölçüden bir
`verdict` türetilir.

DİKKAT: `verdict` bantları DESIGN_SYSTEM §1.2'nin (§ScoreBadge) bantlarıyla
AYNI DEĞİL -- §1.2 "bu chunk ne kadar alakalı" sorusunu, verdict "bu iddia
belgede var mı" sorusunu cevaplıyor. Birini diğerinden türetmeye çalışmak
ikisini de bozar (FEATURE_SPEC.md §9.6).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from .. import config, models, store

# verdict_for içinde literal yazılmaz -- FIDELITY_MIN_SCORE'a bağlı türev bir
# genişlik, bağımsız bir ayar noktası değil (tek tüketicisi bu fonksiyon).
# Bu yüzden config'e taşınmadı.
_WEAK_BAND_WIDTH = 0.10


@dataclass(frozen=True)
class ClaimBinding:
    node_path: str
    claim_text: str
    chunk_id: Optional[int]   # bağlanamadıysa (korpus boşsa) None
    score: Optional[float]    # HAM COSINE; bağlanamadıysa None
    verdict: str               # 'grounded' | 'weak' | 'unsupported'


def verdict_for(score: Optional[float]) -> str:
    """Ham cosine skorundan verdict türetir (FIDELITY_MIN_SCORE = 0.45).

        grounded    : score >= FIDELITY_MIN_SCORE            (>= 0.45)
        weak        : score >= FIDELITY_MIN_SCORE - 0.10      (0.35 - 0.45)
        unsupported : altı, veya score is None                (< 0.35)
    """
    if score is None:
        return "unsupported"
    if score >= config.FIDELITY_MIN_SCORE:
        return "grounded"
    if score >= config.FIDELITY_MIN_SCORE - _WEAK_BAND_WIDTH:
        return "weak"
    return "unsupported"


def bind_claims(
    conn: sqlite3.Connection, claims: Sequence[tuple[str, str]]
) -> list[ClaimBinding]:
    """Her (node_path, claim_text) iddiasını en yakın chunk'a bağlar.

    İddia metinleri models.embed_texts(..., is_query=True) ile embed edilir,
    store.load_matrix() matrisiyle çarpılır, en yüksek cosine'ı veren chunk
    seçilir. Skor OLDUĞU GİBİ yazılır -- yeniden ölçeklenmez, germe yok.

    Korpus boşsa (matrix shape (0, 0)) hiçbir iddia bağlanamaz; hepsi
    chunk_id=None, score=None, verdict='unsupported' olarak döner.
    """
    if not claims:
        return []

    matrix, meta = store.load_matrix(conn)
    if matrix.shape[0] == 0:
        return [
            ClaimBinding(node_path, claim_text, None, None, verdict_for(None))
            for node_path, claim_text in claims
        ]

    texts = [claim_text for _, claim_text in claims]
    vectors = models.embed_texts(texts, is_query=True)

    bindings: list[ClaimBinding] = []
    for (node_path, claim_text), vector in zip(claims, vectors):
        v = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(v))
        if norm:
            v = v / norm
        sims = matrix @ v
        best_idx = int(np.argmax(sims))
        score = float(sims[best_idx])
        chunk_id = int(meta[best_idx]["id"])
        bindings.append(
            ClaimBinding(node_path, claim_text, chunk_id, score, verdict_for(score))
        )
    return bindings


def fidelity_score(bindings: Sequence[ClaimBinding]) -> Optional[float]:
    """grounded iddia sayısı / toplam iddia sayısı -- BİR ORANDIR, benzerlik değil.

    İddia yoksa None döner (1.0 ya da 0.0 değil): iddiasız bir artefaktın
    sadakati ölçülemez, 1.0 yazmak mükemmel bir skor uydurmak olurdu.
    """
    if not bindings:
        return None
    grounded = sum(1 for b in bindings if b.verdict == "grounded")
    return grounded / len(bindings)
