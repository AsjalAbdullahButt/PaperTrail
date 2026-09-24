# Hybrid Retrieval and Ranking

## Why hybrid search

A purely dense (embedding-based) retriever is good at matching meaning but can miss queries that hinge on an exact keyword, code identifier, or proper noun that the embedding model does not weight heavily. A purely sparse (keyword-based) retriever has the opposite weakness. PaperTrail's retrieval module, `hybrid_retrieve` in `backend/app/services/retriever.py`, fuses both signals so that both "meaning" queries and exact-keyword queries retrieve well.

## The three signals

For a given query, PaperTrail computes three scores per candidate chunk and combines them:

1. **Dense score** — cosine similarity between the query embedding and the chunk embedding. Both vectors are normalized with NumPy, and a zero-norm vector (which would make cosine similarity undefined) is treated as a similarity of 0.0 rather than raising an error.
2. **Sparse score** — a BM25 lexical relevance score computed by `services/bm25_index.py` over the same chunk text.
3. **Importance boost** — a per-chunk importance score (see below) that nudges generally more informative chunks upward regardless of the specific query.

These three signals are combined with fixed weights: the dense score contributes a weight of 0.6, the sparse (BM25) score contributes a weight of 0.4, and the importance score is applied as an additional boost with a weight of 0.2 on top of the fused dense+sparse score. These constants are named `DENSE_WEIGHT`, `SPARSE_WEIGHT`, and `IMPORTANCE_BOOST` in the retriever module.

## Approximate nearest neighbor indexing

For the dense side, PaperTrail prefers the `usearch` library to build an approximate nearest-neighbor (ANN) index, because a brute-force scan over every chunk's embedding does not scale well as a user's corpus grows. If `usearch` cannot be imported in a given environment, the retriever falls back to `scipy`'s `cKDTree` for exact nearest-neighbor search. Building an ANN index for every single query would be wasteful, so each user's retrieval corpus (both the sparse BM25 index and the dense ANN index) is cached in-process, using the same cache-invalidation hook as the query-response cache — the index is only rebuilt when the user's underlying chunk set actually changes.

## Importance scoring

`services/importance.py` implements `score_chunks`, a pure-Python (no scikit-learn dependency) importance signal that blends a TF-IDF-style informativeness measure — how distinctive a chunk's vocabulary is relative to the rest of the same document, after excluding a hand-maintained English stopword list — with a positional prior that down-weights chunks sitting at the very start or very end of a document, on the theory that boilerplate (like a title page or footer) tends to cluster there. The raw blended score is then min-max normalized into the range [0, 1] across the chunks of a single document; if every chunk in a document would score identically, the normalizer assigns them all 0.5 rather than dividing by zero. The same importance scores feed `extract_highlights`, which is used to generate a short, extractive preview of a document's most representative sentences.

## Query-scoped safety ceiling

To keep a single query bounded in cost, retrieval enforces a hard ceiling, `MAX_QUERY_CHUNKS` (default 5000), on how many of a user's chunks a single query will ever scan. Above that many stored chunks, PaperTrail's documented recommendation is to move to a dedicated vector database rather than relying on the in-memory brute-force/ANN hybrid scan described above.

## What retrieval returns

`hybrid_retrieve` returns fully annotated results: each hit carries its chunk id, its page number, its section heading, the fused `ranked_score`, and the individual dense and sparse sub-scores. Beyond ranking, calling `hybrid_retrieve` also has a side effect — it records that the returned chunks were retrieved, incrementing a per-chunk `retrieved_count` and updating a per-user coverage table. This retrieval-coverage data is what powers PaperTrail's analytics dashboard and its per-document "coverage heatmap," which shows which parts of a user's library are frequently retrieved versus which parts have never been surfaced by any query.
