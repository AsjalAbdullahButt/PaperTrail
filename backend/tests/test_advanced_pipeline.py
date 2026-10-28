"""Optional NLP pipeline stages: re-ranking, NLI grounding, abstention, HyDE,
contextual chunk headers, and their exposure through the query API.

The heavy models are stubbed, so these tests need neither the network nor
sentence-transformers.
"""
from __future__ import annotations

import pytest

import app.routers.query as query_router
from app.config import settings
from app.ingestion import contextualize_chunk
from app.schemas import QueryOptions
from app.services import abstention, nli_guard, pipeline_options, reranker
from ._helpers import upload_text_doc

from conftest import requires_db


# ------------------------------ re-ranker ------------------------------ #
def test_rerank_orders_by_cross_encoder_score_and_keeps_fields(monkeypatch):
    class Stub:
        def predict(self, pairs, show_progress_bar=False):
            return [0.1 if "irrelevant" in p[1] else 5.0 for p in pairs]

    monkeypatch.setattr(reranker, "_model", lambda: Stub())
    items = [{"text": "irrelevant text", "chunk_id": "a"}, {"text": "the answer", "chunk_id": "b"}]
    out = reranker.rerank("q", items, top_k=1)
    assert [i["chunk_id"] for i in out] == ["b"]
    assert out[0]["rerank_score"] == 5.0
    assert "rerank_score" not in items[0]  # inputs are not mutated


def test_rerank_empty_input():
    assert reranker.rerank("q", [], 5) == []


# ------------------------------ abstention ----------------------------- #
def test_signal_uses_rerank_probability_when_present_else_dense():
    assert abstention.retrieval_signal([]) == 0.0
    dense = [{"similarity_score": 0.42}]
    assert abstention.retrieval_signal(dense) == 0.42 and abstention.signal_kind(dense) == "dense"
    rr = [{"similarity_score": 0.9, "rerank_score": 0.0}]
    assert abstention.retrieval_signal(rr) == 0.5 and abstention.signal_kind(rr) == "rerank"


def test_should_abstain_respects_enabled_flag_and_zero_threshold(monkeypatch):
    low = [{"similarity_score": 0.1}]
    monkeypatch.setattr(settings, "abstain_threshold", 0.3)
    assert abstention.should_abstain(low, enabled=True) is True
    assert abstention.should_abstain(low, enabled=False) is False
    monkeypatch.setattr(settings, "abstain_threshold", 0.0)  # uncalibrated => never abstain
    assert abstention.should_abstain(low, enabled=True) is False
    assert abstention.should_abstain([{"similarity_score": 0.9}], enabled=True) is False


# ------------------------------ NLI guard ------------------------------ #
def test_answer_sentences_strips_markup_citations_and_short_fragments():
    answer = "## Heading\nThe model uses **eight** attention heads [1].\n- Okay.\n- It trains on WMT data 【2】."
    sents = nli_guard.answer_sentences(answer)
    assert sents == ["The model uses eight attention heads.", "It trains on WMT data."]


def test_check_answer_nli_flags_unentailed_sentences(monkeypatch):
    torch = pytest.importorskip("torch")

    class Tok:
        def __call__(self, premises, hypotheses, **kw):
            flags = [("eight" in p and "eight" in h) for p, h in zip(premises, hypotheses)]
            return {"flags": torch.tensor(flags)}

    class Out:
        def __init__(self, logits):
            self.logits = logits

    class Model:
        def __call__(self, flags):
            # columns: contradiction, entailment, neutral
            logits = torch.where(flags.unsqueeze(1), torch.tensor([[-4.0, 4.0, 0.0]]), torch.tensor([[0.0, -4.0, 4.0]]))
            return Out(logits)

    monkeypatch.setattr(nli_guard, "_load", lambda: (Tok(), Model(), 1, 0))
    chunks = [{"chunk_id": "c1", "text": "The base model employs eight attention heads in each layer."}]
    res = nli_guard.check_answer_nli(
        "The base model has eight attention heads. It was trained on a thousand GPUs for years.", chunks
    )
    assert [r["supported"] for r in res] == [True, False]
    assert res[0]["source_chunk_id"] == "c1" and res[0]["label"] == "entailed"
    assert res[1]["source_chunk_id"] is None and res[1]["label"] == "neutral"


# ------------------------- options + capabilities ---------------------- #
def test_resolve_uses_server_defaults_then_request_overrides(monkeypatch):
    monkeypatch.setattr(reranker, "available", lambda: True)
    monkeypatch.setattr(nli_guard, "available", lambda: True)
    monkeypatch.setattr(settings, "rerank_enabled", False)
    cfg = pipeline_options.resolve(None)
    assert (cfg.rerank, cfg.expansion, cfg.grounding, cfg.abstain, cfg.customised) == (False, "none", "lexical", False, False)
    cfg = pipeline_options.resolve(QueryOptions(rerank=True, grounding="nli", expansion="hyde", abstain=True))
    assert (cfg.rerank, cfg.expansion, cfg.grounding, cfg.abstain, cfg.customised) == (True, "hyde", "nli", True, True)


def test_resolve_degrades_gracefully_when_libraries_missing(monkeypatch):
    monkeypatch.setattr(reranker, "available", lambda: False)
    monkeypatch.setattr(nli_guard, "available", lambda: False)
    cfg = pipeline_options.resolve(QueryOptions(rerank=True, grounding="nli"))
    assert cfg.rerank is False and cfg.grounding == "lexical"
    assert len(cfg.notes) == 2


def test_contextualize_chunk_prepends_title_and_section():
    assert contextualize_chunk("It uses 8 heads.", "Transformer", "3.2 Attention") == "Transformer | 3.2 Attention\nIt uses 8 heads."
    assert contextualize_chunk("text", "Title", None) == "Title\ntext"
    assert contextualize_chunk("text", "", None) == "text"


# ------------------------------ API level ------------------------------ #
@requires_db
def test_capabilities_endpoint(client):
    res = client.get("/api/query/capabilities")
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"rerank", "expansion", "grounding", "abstain", "contextual_chunk_headers"}
    assert body["grounding"]["options"][0] == "lexical"


@requires_db
def test_query_with_rerank_nli_and_abstain_options(client, monkeypatch):
    upload_text_doc(client, "facts.txt", "The capital of the fictional country Zubrowka is Lutz. Lutz hosts the grand hotel.")
    monkeypatch.setattr(reranker, "available", lambda: True)
    monkeypatch.setattr(nli_guard, "available", lambda: True)
    monkeypatch.setattr(
        "app.services.reranker.rerank",
        lambda query, items, top_k: [{**it, "rerank_score": 3.0} for it in items][:top_k],
    )
    monkeypatch.setattr(
        query_router, "check_answer_nli",
        lambda answer, chunks: [{"sentence": "Lutz is the capital.", "supported": True, "entailment": 0.97,
                                 "contradiction": 0.01, "label": "entailed", "source_chunk_id": chunks[0]["chunk_id"]}],
    )
    res = client.post("/api/query", json={
        "question": "What is the capital of Zubrowka?", "mode": "rag",
        "options": {"rerank": True, "grounding": "nli"},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["pipeline"]["reranked"] is True and body["pipeline"]["grounding_method"] == "nli"
    assert body["sources"][0]["rerank_score"] == 3.0 and body["sources"][0]["rerank_prob"] > 0.9
    assert body["grounding"][0]["label"] == "entailed" and body["unsupported_sentences"] == []
    assert body["abstained"] is False


@requires_db
def test_query_abstains_below_threshold_without_calling_the_generator(client, monkeypatch):
    upload_text_doc(client, "facts.txt", "The capital of the fictional country Zubrowka is Lutz.")
    monkeypatch.setattr(settings, "abstain_threshold", 0.99)  # nothing can clear this

    def boom(*a, **k):
        raise AssertionError("generator must not run when abstaining")

    monkeypatch.setattr(query_router.llm, "generate_rag_answer_with_followups", boom)
    res = client.post("/api/query", json={
        "question": "What is the capital of Zubrowka?", "mode": "rag", "options": {"abstain": True},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["abstained"] is True and "could not find" in body["answer"].lower()
    assert len(body["sources"]) >= 1  # the user can still see what was retrieved


@requires_db
def test_query_hyde_expansion_is_passed_to_the_retriever(client, monkeypatch):
    upload_text_doc(client, "facts.txt", "The capital of the fictional country Zubrowka is Lutz.")
    monkeypatch.setattr(query_router, "hyde_passage", lambda q: "Lutz is the capital city of Zubrowka.")
    seen = {}
    real = query_router.hybrid_retrieve

    def spy(*a, **kw):
        seen["expanded_query"] = kw.get("expanded_query")
        return real(*a, **kw)

    monkeypatch.setattr(query_router, "hybrid_retrieve", spy)
    res = client.post("/api/query", json={
        "question": "What is the capital of Zubrowka?", "mode": "rag", "options": {"expansion": "hyde"},
    })
    assert res.status_code == 200
    assert seen["expanded_query"] == "Lutz is the capital city of Zubrowka."
    assert res.json()["pipeline"]["expansion"] == "hyde"
