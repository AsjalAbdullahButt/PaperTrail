"""Pure pydantic-level schema tests (no database needed)."""
from __future__ import annotations

from app.schemas import MAX_CONVERSATION_TURNS, QueryRequest


def test_conversation_history_truncates_to_max_turns():
    turns = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(8)
    ]
    req = QueryRequest(question="q", conversation_history=turns)
    assert len(req.conversation_history) == MAX_CONVERSATION_TURNS
    # The oldest turns are dropped — the tail (most recent) is kept.
    assert [t.content for t in req.conversation_history] == [f"turn {i}" for i in range(2, 8)]


def test_conversation_history_at_or_under_max_is_unchanged():
    turns = [{"role": "user", "content": f"turn {i}"} for i in range(MAX_CONVERSATION_TURNS)]
    req = QueryRequest(question="q", conversation_history=turns)
    assert len(req.conversation_history) == MAX_CONVERSATION_TURNS


def test_conversation_history_defaults_to_empty_list():
    req = QueryRequest(question="q")
    assert req.conversation_history == []


def test_conversation_history_empty_list_is_backward_compatible():
    without_field = QueryRequest(question="q")
    with_empty_field = QueryRequest(question="q", conversation_history=[])
    assert without_field.conversation_history == with_empty_field.conversation_history == []
