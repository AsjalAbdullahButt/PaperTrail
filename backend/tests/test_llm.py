"""Tests for llm.py: deterministic offline path and mocked OpenAI path."""
from __future__ import annotations

import sys
import types

import app.llm as llm


# --------------------------- offline fallback --------------------------- #
def test_offline_embed_is_deterministic_and_normalized():
    a = llm.embed_texts(["hello world"])
    b = llm.embed_texts(["hello world"])
    assert a == b  # deterministic
    norm = sum(v * v for v in a[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-9  # L2-normalized


def test_offline_embed_empty_input():
    assert llm.embed_texts([]) == []


def test_offline_generate_rag_uses_top_context(monkeypatch):
    # Force the offline path: clear BOTH providers (a Groq key alone still
    # routes chat generation to Groq).
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm.settings, "groq_api_key", "")
    out = llm.generate_answer("q", ["the most relevant passage"], "rag")
    assert "offline mode" in out.lower()
    assert "most relevant passage" in out


def test_offline_generate_rag_no_context():
    out = llm.generate_answer("q", [], "rag")
    assert "could not find" in out.lower()


def test_offline_generate_direct_mode_notes_missing_key(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm.settings, "groq_api_key", "")
    out = llm.generate_answer("what is 2+2?", [], "direct")
    assert "offline mode" in out.lower()


# ----------------------------- OpenAI path ------------------------------ #
def _install_fake_openai(monkeypatch, *, embed=None, chat=None):
    """Install a fake `openai` module exposing the API surface llm.py uses."""
    fake = types.ModuleType("openai")

    class FakeClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.embeddings = types.SimpleNamespace(create=embed)
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=chat)
            )

    fake.OpenAI = FakeClient
    monkeypatch.setitem(sys.modules, "openai", fake)
    # A key that passes settings.openai_ready.
    monkeypatch.setattr(llm.settings, "openai_api_key", "sk-test-realish-key")


def test_openai_embed_path(monkeypatch):
    def fake_embed(model, input):
        data = [
            types.SimpleNamespace(embedding=[float(len(t)), 1.0], index=i)
            for i, t in enumerate(input)
        ]
        return types.SimpleNamespace(data=data)

    _install_fake_openai(monkeypatch, embed=fake_embed)
    out = llm.embed_texts(["ab", "cde"])
    assert out == [[2.0, 1.0], [3.0, 1.0]]


def test_openai_embed_realigns_out_of_order_response(monkeypatch):
    """Chunk<->embedding alignment must not depend on API response ordering.

    The API returns each item with an `index`; if items come back shuffled we
    must reorder by index, otherwise embeddings get paired with the wrong text.
    """
    def fake_embed(model, input):
        data = [
            types.SimpleNamespace(embedding=[float(i)], index=i)
            for i, _ in enumerate(input)
        ]
        # Return them in reverse order to simulate an out-of-order response.
        return types.SimpleNamespace(data=list(reversed(data)))

    _install_fake_openai(monkeypatch, embed=fake_embed)
    out = llm.embed_texts(["a", "b", "c"])
    assert out == [[0.0], [1.0], [2.0]]


def test_openai_generate_path(monkeypatch):
    def fake_chat(model, messages, temperature):
        msg = types.SimpleNamespace(content="grounded answer [1]")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    _install_fake_openai(monkeypatch, chat=fake_chat)
    out = llm.generate_answer("q", ["ctx"], "rag")
    assert out == "grounded answer [1]"


def test_openai_failure_falls_back_to_offline(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("api down")

    _install_fake_openai(monkeypatch, embed=boom)
    # Should not raise; falls back to deterministic offline embeddings.
    out = llm.embed_texts(["hello"])
    assert len(out) == 1
    assert abs(sum(v * v for v in out[0]) ** 0.5 - 1.0) < 1e-9


# --------------------- V3 Phase 3: conversation history ------------------ #
def test_build_messages_no_history_matches_old_two_message_shape():
    messages = llm._build_messages("q", ["ctx"], "rag")
    assert [m["role"] for m in messages] == ["system", "user"]


def test_build_messages_empty_history_list_same_as_none():
    with_none = llm._build_messages("q", ["ctx"], "rag", None)
    with_empty = llm._build_messages("q", ["ctx"], "rag", [])
    assert with_none == with_empty


def test_build_messages_history_inserted_between_system_and_new_user_message():
    history = [
        {"role": "user", "content": "What is this document about?"},
        {"role": "assistant", "content": "It's a quarterly report."},
    ]
    messages = llm._build_messages("Tell me more about the first point", ["ctx"], "rag", history)

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[1] == history[0]
    assert messages[2] == history[1]
    assert "Tell me more about the first point" in messages[3]["content"]


def test_generate_answer_threads_history_into_the_hosted_call(monkeypatch):
    captured = {}

    def fake_chat(model, messages, temperature):
        captured["messages"] = messages
        msg = types.SimpleNamespace(content="follow-up answer")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    _install_fake_openai(monkeypatch, chat=fake_chat)
    history = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
    ]
    out = llm.generate_answer("second question", ["ctx"], "rag", history)

    assert out == "follow-up answer"
    roles = [m["role"] for m in captured["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert captured["messages"][-1]["content"].endswith("Question: second question")


# --------------------- V3 Phase 4: document summary ---------------------- #
def test_summarize_document_empty_highlights_returns_empty_without_calling_model(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not call the model with no highlights")

    monkeypatch.setattr(llm, "complete_text", boom)
    assert llm.summarize_document("report.pdf", []) == ""


def test_summarize_document_offline_returns_empty(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm.settings, "groq_api_key", "")
    out = llm.summarize_document("report.pdf", ["Revenue grew this quarter."])
    assert out == ""


def test_summarize_document_uses_top_5_highlights_and_title_in_system_prompt(monkeypatch):
    captured = {}

    def fake_complete_text(prompt, system, temperature=0.3):
        captured["prompt"] = prompt
        captured["system"] = system
        return "A concise summary."

    monkeypatch.setattr(llm, "complete_text", fake_complete_text)
    highlights = [f"highlight {i}" for i in range(8)]
    out = llm.summarize_document("Q3 Report.pdf", highlights)

    assert out == "A concise summary."
    assert "Q3 Report.pdf" in captured["system"]
    assert "highlight 5" not in captured["prompt"]  # only the top 5 are used
    assert "highlight 4" in captured["prompt"]


# --------------------- V3 Phase 6: document comparison -------------------- #
def test_build_compare_messages_groups_passages_by_document():
    chunks_by_doc = {
        "alpha.txt": ["Alpha revenue was 10 million."],
        "beta.txt": ["Beta revenue was 20 million.", "Beta grew fast."],
    }
    messages = llm._build_compare_messages("Compare revenue", chunks_by_doc)
    assert [m["role"] for m in messages] == ["system", "user"]

    user_content = messages[1]["content"]
    assert "Document: alpha.txt" in user_content
    assert "Document: beta.txt" in user_content
    # Global numbering across documents: alpha gets [1], beta gets [2] and [3].
    assert "[1] Alpha revenue was 10 million." in user_content
    assert "[2] Beta revenue was 20 million." in user_content
    assert "[3] Beta grew fast." in user_content
    assert "Compare revenue" in user_content


def test_offline_compare_generate_no_chunks():
    assert "could not find" in llm._offline_compare_generate("q", {}).lower()


def test_generate_compare_answer_offline_lists_each_document(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm.settings, "groq_api_key", "")
    out = llm.generate_compare_answer(
        "Compare", {"alpha.txt": ["Alpha fact."], "beta.txt": ["Beta fact."]}
    )
    assert "alpha.txt" in out
    assert "beta.txt" in out
