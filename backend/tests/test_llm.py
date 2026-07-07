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
    monkeypatch.setattr(llm.settings, "openai_api_key", "")  # force offline
    out = llm.generate_answer("q", ["the most relevant passage"], "rag")
    assert "offline mode" in out.lower()
    assert "most relevant passage" in out


def test_offline_generate_rag_no_context():
    out = llm.generate_answer("q", [], "rag")
    assert "could not find" in out.lower()


def test_offline_generate_direct_mode_notes_missing_key(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
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
        data = [types.SimpleNamespace(embedding=[float(len(t)), 1.0]) for t in input]
        return types.SimpleNamespace(data=data)

    _install_fake_openai(monkeypatch, embed=fake_embed)
    out = llm.embed_texts(["ab", "cde"])
    assert out == [[2.0, 1.0], [3.0, 1.0]]


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
