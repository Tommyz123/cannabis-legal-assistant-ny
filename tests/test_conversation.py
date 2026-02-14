"""Unit tests for ConversationManager."""

from __future__ import annotations

from uuid import UUID

from src.agent.conversation import ConversationManager


def test_create_session_returns_uuid():
    manager = ConversationManager()
    session_id = manager.create_session()
    assert UUID(session_id)


def test_add_and_get_message():
    manager = ConversationManager()
    session_id = manager.create_session()
    manager.add_message(session_id, "user", "hello")
    history = manager.get_history(session_id)
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"
    assert "timestamp" in history[0]


def test_get_history_max_turns():
    manager = ConversationManager()
    session_id = manager.create_session()
    for idx in range(6):
        manager.add_message(session_id, "user", f"m{idx}")
    history = manager.get_history(session_id, max_turns=3)
    assert [message["content"] for message in history] == ["m3", "m4", "m5"]


def test_conversation_fifo_limit():
    manager = ConversationManager(max_messages=10)
    session_id = manager.create_session()
    for idx in range(12):
        manager.add_message(session_id, "user", f"msg-{idx}")
    history = manager.get_history(session_id, max_turns=20)
    assert len(history) == 10
    assert history[0]["content"] == "msg-2"
    assert history[-1]["content"] == "msg-11"


def test_clear_session():
    manager = ConversationManager()
    session_id = manager.create_session()
    manager.add_message(session_id, "user", "to clear")
    manager.clear_session(session_id)
    assert manager.get_history(session_id) == []


def test_get_history_nonexistent_session():
    manager = ConversationManager()
    assert manager.get_history("nonexistent-session") == []
