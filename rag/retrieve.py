"""
Retrieval: soruyu embed et, saklanan chunk'larla cosine benzerliği hesapla,
en yakın k tanesini döndür.

Matris store.load_matrix() tarafından L2-normalize edilmiş geldiği için cosine
tek bir matris-vektör çarpımına iner.

    python -m rag.retrieve "RAG kaç adımdan oluşur?"
    python -m rag.retrieve --calibrate
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

import numpy as np

from . import config, models, store


@dataclass
class Hit:
    score: float
    source: str
    page: int
    content: str
    via_ocr: bool = False

    def citation(self) -> str:
        """Kaynak etiketi: [Kaynak: dosya.pdf s.4]. Markdown fixture'larında sayfa yok."""
        if self.page:
            return f"[Kaynak: {self.source} s.{self.page}]"
        return f"[Kaynak: {self.source}]"


def embed_query(query: str) -> np.ndarray:
    """Sorguyu normalize edilmiş bir vektöre çevirir."""
    vector = np.asarray(models.embed_texts([query], is_query=True)[0], dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def get_top_chunks(
    query: str,
    k: int = None,
    min_score: Optional[float] = None,
    conn=None,
) -> list[Hit]:
    """Sorguya en benzer chunk'ları döndürür.

    min_score verilirse eşiğin altındaki sonuçlar elenir. Boş liste dönmesi
    "bu soruya belgelerden cevap yok" anlamına gelir ve çağıran taraf LLM'i
    hiç çağırmadan kısa devre yapabilir.
    """
    k = k or config.TOP_K
    query = (query or "").strip()
    if not query:
        return []

    own_conn = conn is None
    conn = conn or store.connect()
    try:
        matrix, meta = store.load_matrix(conn)
        if matrix.shape[0] == 0:
            return []

        scores = matrix @ embed_query(query)

        # k en büyüğü kısmi sıralamayla al, sonra kendi içinde sırala.
        top_idx = np.argpartition(scores, -min(k, len(scores)))[-min(k, len(scores)):]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

        hits = []
        for i in top_idx:
            score = float(scores[i])
            if min_score is not None and score < min_score:
                continue
            row = meta[int(i)]
            hits.append(
                Hit(
                    score=score,
                    source=row["source"],
                    page=row["page"],
                    content=row["content"],
                    via_ocr=bool(row.get("via_ocr")),
                )
            )
        return hits
    finally:
        if own_conn:
            conn.close()


def build_context(hits: list[Hit]) -> str:
    """Bulunan chunk'ları numaralandırılmış, kaynak etiketli bir bağlam bloğuna çevirir."""
    blocks = []
    for i, hit in enumerate(hits, 1):
        blocks.append(f"[{i}] {hit.citation()}\n{hit.content}")
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- CLI

# Eşik kalibrasyonu için: ilk üçü belgelerde cevabı olan, son üçü olmayan sorular.
CALIBRATION_QUERIES = [
    ("RAG kaç adımdan oluşur ve bu adımlar nelerdir?", True),
    ("Cosine similarity neyi ölçer?", True),
    ("Foundry Local hangi donanımları kullanabilir?", True),
    ("SQLite'ta veri nasıl saklanır?", True),
    ("Chroma ve FAISS'ten hangisi daha hızlıdır?", False),
    ("Foundry Local'da model fine-tuning nasıl yapılır?", False),
    ("İstanbul'un nüfusu kaçtır?", False),
]


def _calibrate(conn) -> None:
    """Alakalı ve alakasız soruların skor aralıklarını yan yana koyar.

    min_score bu iki grubun arasındaki boşluğa yerleştirilmeli.
    """
    relevant, irrelevant = [], []
    for query, is_relevant in CALIBRATION_QUERIES:
        hits = get_top_chunks(query, conn=conn)
        if not hits:
            print(f"  (sonuç yok) {query}")
            continue
        top = hits[0].score
        (relevant if is_relevant else irrelevant).append(top)
        mark = "+" if is_relevant else "-"
        print(f"  [{mark}] en yüksek={top:.4f}  {query}")
        for hit in hits:
            print(f"        {hit.score:.4f}  {hit.source} s.{hit.page}  {hit.content[:70]}...")
        print()

    if relevant and irrelevant:
        lo, hi = min(relevant), max(irrelevant)
        print(f"  Alakalı soruların en düşük skoru : {lo:.4f}")
        print(f"  Alakasız soruların en yüksek skoru: {hi:.4f}")
        if lo > hi:
            print(f"  -> Ayrım net. Önerilen MIN_SCORE: {(lo + hi) / 2:.3f} "
                  f"(şu an {config.MIN_SCORE})")
        else:
            print(f"  -> UYARI: gruplar örtüşüyor, tek bir eşik ikisini ayıramaz. "
                  f"Şu anki MIN_SCORE={config.MIN_SCORE}")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    conn = store.connect()
    try:
        if not argv or "--calibrate" in argv:
            print("=== Eşik kalibrasyonu ===\n")
            _calibrate(conn)
            return 0

        query = " ".join(argv)
        hits = get_top_chunks(query, conn=conn)
        print(f"Soru: {query}\n")
        if not hits:
            print("  Sonuç yok (veritabanı boş olabilir).")
        for hit in hits:
            print(f"  {hit.score:.4f}  {hit.citation()}")
            print(f"          {hit.content[:150]}...\n")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
