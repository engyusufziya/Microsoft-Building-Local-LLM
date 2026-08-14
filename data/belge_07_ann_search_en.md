# Approximate Nearest Neighbor Search

Vector databases rarely compare a query against every stored embedding one by
one; at large scale this brute-force approach becomes too slow. Instead, most
systems use Approximate Nearest Neighbor (ANN) search, which trades a small
amount of accuracy for a large gain in speed.

A widely used ANN technique is HNSW (Hierarchical Navigable Small World
graphs). It organizes vectors into layered graphs: the top layer has few
nodes and long-range links for fast traversal, while lower layers have more
nodes and shorter links for fine-grained accuracy. A search starts at the top
layer and descends, narrowing in on the closest vectors at each level.

ANN search is a reasonable default for small, single-machine corpora like
this project's SQLite-backed store: brute-force cosine similarity over a few
thousand chunks still completes in milliseconds, so the accuracy-speed
tradeoff of ANN is not yet necessary. It becomes worth adopting once the
corpus grows past roughly one hundred thousand vectors, where a linear scan
would noticeably slow down every query.
