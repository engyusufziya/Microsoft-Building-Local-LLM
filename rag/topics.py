"""
Embedding kümeleme: mind map yapısı ve quiz kapsam örneklemesinin ORTAK temeli.

Bu modül hiçbir LLM çağrısı yapmaz ve tamamen deterministiktir -- etiketleme
(tek LLM adımı) Faz 3'e ait (FEATURE_SPEC.md §9.4). scipy/scikit-learn kurulu
değil ve kurulmayacak (CLAUDE.md, requirements.txt sabit); bu yüzden algoritma
saf numpy: agglomerative kümeleme, average linkage, benzerlik ölçüsü cosine.

    python -m rag.topics             # 'data' fixture'larıyla ingest edilmiş
                                        veritabanında kümeleri yazdırır
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np

from . import config, store


class InsufficientCorpusError(RuntimeError):
    """Kümeleme için yeterli chunk yok."""


@dataclass(frozen=True)
class Topic:
    id: int                  # 0..n-1, boyuta göre AZALAN sırada atanır
    chunk_ids: list[int]     # chunks.id; merkeze yakınlıkta AZALAN sıra
    centroid: np.ndarray     # (D,) float32, L2-normalize
    size: int                # len(chunk_ids)


def topic_similarity(a: Topic, b: Topic) -> float:
    """İki küme merkezi arasındaki HAM cosine. Faz 3 kenar eşiği için.

    Merkezler zaten L2-normalize olduğu için nokta çarpımı doğrudan cosine'dır.
    """
    return float(np.dot(a.centroid, b.centroid))


def _cluster_centroid(matrix: np.ndarray, rows: list[int]) -> np.ndarray:
    """Küme üyelerinin ortalaması, yeniden L2-normalize edilmiş.

    `matrix[rows]` fantezi indeksleme YENİ (yazılabilir) bir dizi üretir --
    salt okunur `matrix`'in kendisine hiçbir zaman yazılmaz.
    """
    vec = matrix[rows].mean(axis=0).astype(np.float32)
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def cluster_corpus(
    conn,
    max_clusters: int | None = None,
    min_cluster_size: int | None = None,
) -> list[Topic]:
    """Korpustaki tüm chunk'ları anlamsal kümelere ayırır.

    Algoritma (deterministik, saf numpy):
      1. store.load_matrix(conn) -> (N x D L2-normalize matris, meta).
      2. Agglomerative, average linkage, cosine benzerlik -- matris zaten
         normalize olduğu için M @ M.T tek çarpımda tam benzerlik matrisidir.
      3. Kesme: küme sayısı min(max_clusters, N // min_cluster_size) değerine
         inince durulur.
      4. min_cluster_size altında kalan artık kümeler, merkezi en yakın olan
         kümeye EMİLİR (atılmaz -- atmak korpusun bir kısmını haritadan
         sessizce yok ederdi).
      5. Merkez = küme üyelerinin ortalaması, sonra yeniden L2-normalize.

    Determinizm: aynı korpus her zaman aynı Topic listesini üretir (aynı
    id'ler, aynı sıra). Bağlantı çözümü (eşit benzerlikte iki çift) chunk
    id'sine göre kararlaştırılır -- her adımda adaylar en küçük chunk id'ye
    göre sıralanıp taranır, ilk (yani en küçük id'li) maksimum kazanır.
    """
    max_clusters = config.TOPIC_MAX_CLUSTERS if max_clusters is None else max_clusters
    min_cluster_size = (
        config.TOPIC_MIN_CLUSTER_SIZE if min_cluster_size is None else min_cluster_size
    )

    matrix, meta = store.load_matrix(conn)
    n = matrix.shape[0]
    if n == 0 or n < min_cluster_size:
        raise InsufficientCorpusError(
            f"Kümeleme için yeterli chunk yok: N={n}, gereken en az {min_cluster_size}."
        )

    target_k = max(1, min(max_clusters, n // min_cluster_size))
    chunk_ids = [m["id"] for m in meta]  # matrix satırı i -> chunk_ids[i] (load_matrix ORDER BY id)

    # Ham benzerlik matrisi -- matrise ASLA yazılmaz, yalnızca çarpımda
    # okunur; çıktı zaten yeni ve yazılabilir bir dizidir.
    raw_sim = matrix @ matrix.T  # (N, N) float32

    # key -> matrix satır indeksleri listesi. Başlangıçta her chunk kendi
    # tekil kümesi.
    clusters: dict[int, list[int]] = {i: [i] for i in range(n)}
    next_key = n

    def cluster_min_id(rows: list[int]) -> int:
        return min(chunk_ids[r] for r in rows)

    def cluster_sim(a_rows: list[int], b_rows: list[int]) -> float:
        return float(raw_sim[np.ix_(a_rows, b_rows)].mean())

    while len(clusters) > target_k:
        keys = sorted(clusters.keys(), key=lambda k: cluster_min_id(clusters[k]))
        best_pair = None
        best_sim = -2.0
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ka, kb = keys[i], keys[j]
                s = cluster_sim(clusters[ka], clusters[kb])
                if s > best_sim:
                    best_sim = s
                    best_pair = (ka, kb)
        ka, kb = best_pair
        merged_rows = clusters.pop(ka) + clusters.pop(kb)
        clusters[next_key] = merged_rows
        next_key += 1

    # 4. adım: min_cluster_size altında kalan kümeleri en yakın kümeye emer.
    # N >= min_cluster_size zaten garanti (üstteki erken kontrol), bu yüzden
    # döngü tek bir kümeye inince o küme kesinlikle yeterli boyuttadır.
    while len(clusters) > 1:
        undersized = [k for k, rows in clusters.items() if len(rows) < min_cluster_size]
        if not undersized:
            break
        target_key = min(undersized, key=lambda k: cluster_min_id(clusters[k]))
        target_rows = clusters[target_key]
        target_centroid = _cluster_centroid(matrix, target_rows)

        best_key = None
        best_sim = -2.0
        for k in sorted(clusters.keys(), key=lambda k: cluster_min_id(clusters[k])):
            if k == target_key:
                continue
            s = float(np.dot(target_centroid, _cluster_centroid(matrix, clusters[k])))
            if s > best_sim:
                best_sim = s
                best_key = k

        clusters[best_key] = clusters[best_key] + clusters.pop(target_key)

    # Topic.id: boyuta göre AZALAN, eşitlikte en küçük chunk id'ye göre.
    ordered_rows = sorted(
        clusters.values(), key=lambda rows: (-len(rows), cluster_min_id(rows))
    )

    topics: list[Topic] = []
    for tid, rows in enumerate(ordered_rows):
        centroid = _cluster_centroid(matrix, rows)
        sims_to_centroid = matrix[rows] @ centroid
        member_order = sorted(
            range(len(rows)),
            key=lambda i: (-float(sims_to_centroid[i]), chunk_ids[rows[i]]),
        )
        ordered_chunk_ids = [chunk_ids[rows[i]] for i in member_order]
        topics.append(
            Topic(id=tid, chunk_ids=ordered_chunk_ids, centroid=centroid, size=len(rows))
        )

    return topics


# --------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    """Elle doğrulama için: kümeleri kaynak belge dağılımıyla yazdırır."""
    conn = store.connect()
    try:
        topics = cluster_corpus(conn)
        rows_by_id = {
            r["id"]: r for r in conn.execute("SELECT id, source FROM chunks")
        }
        print(f"{len(topics)} küme bulundu.\n")
        for t in topics:
            sources = sorted({rows_by_id[cid]["source"] for cid in t.chunk_ids})
            print(f"Küme {t.id}  boyut={t.size}  kaynaklar={sources}")
            for cid in t.chunk_ids:
                row = conn.execute(
                    "SELECT source, content FROM chunks WHERE id = ?", (cid,)
                ).fetchone()
                print(f"    #{cid} [{row['source']}] {row['content'][:60]!r}")
            print()
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
