"""Tests for the pure cosine-similarity helpers."""
import math

from app.similarity import cosine_similarity, top_k_by_similarity


def test_identical_vectors_similarity_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_orthogonal_vectors_similarity_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_opposite_vectors_similarity_is_negative_one():
    assert math.isclose(cosine_similarity([1.0, 1.0], [-1.0, -1.0]), -1.0)


def test_zero_vector_is_safe():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_scale_invariance():
    a = [1.0, 2.0, 3.0]
    b = [2.0, 4.0, 6.0]  # same direction, different magnitude
    assert math.isclose(cosine_similarity(a, b), 1.0)


def test_top_k_ranks_by_similarity():
    query = [1.0, 0.0]
    candidates = [
        (10, [1.0, 0.0]),   # identical -> highest
        (20, [0.9, 0.1]),   # close
        (30, [0.0, 1.0]),   # orthogonal -> lowest
    ]
    ranked = top_k_by_similarity(query, candidates, k=2)
    assert [cid for cid, _ in ranked] == [10, 20]
    assert ranked[0][1] >= ranked[1][1]
