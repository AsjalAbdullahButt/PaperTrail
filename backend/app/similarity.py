"""Vector similarity helpers (pure functions, easy to unit-test)."""
from __future__ import annotations

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors, in [-1, 1].

    Returns 0.0 if either vector is all zeros (undefined direction).
    """
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def top_k_by_similarity(
    query_vec: list[float],
    candidates: list[tuple[int, list[float]]],
    k: int,
) -> list[tuple[int, float]]:
    """Rank ``(id, vector)`` candidates against ``query_vec``.

    Returns the top ``k`` as ``(id, similarity)`` sorted descending. Uses a
    single vectorized NumPy matmul for speed.
    """
    if not candidates or k <= 0:
        return []

    ids = [cid for cid, _ in candidates]
    matrix = np.asarray([vec for _, vec in candidates], dtype=np.float64)
    q = np.asarray(query_vec, dtype=np.float64)

    q_norm = np.linalg.norm(q)
    row_norms = np.linalg.norm(matrix, axis=1)
    denom = row_norms * q_norm
    # Avoid divide-by-zero; zero-norm rows get similarity 0.
    scores = np.zeros(len(ids), dtype=np.float64)
    nonzero = denom > 0
    scores[nonzero] = (matrix[nonzero] @ q) / denom[nonzero]

    order = np.argsort(-scores)[:k]
    return [(ids[i], float(scores[i])) for i in order]
