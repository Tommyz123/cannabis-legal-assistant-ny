"""In-memory conversation state manager."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class ConversationManager:
    """Manage chat history by session id with FIFO truncation."""

    def __init__(self, max_messages: int = 10) -> None:
        self.max_messages = max_messages
        self.sessions: dict[str, list[dict]] = {}

    def create_session(self) -> str:
        """Create and return a new UUID session id."""
        session_id = str(uuid4())
        self.sessions[session_id] = []
        return session_id

    def add_message(self, session_id: str, role: str, content: str, intent: str | None = None) -> None:
        """Append one message and enforce FIFO capacity."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if intent is not None:
            message["intent"] = intent
        self.sessions[session_id].append(message)
        overflow = len(self.sessions[session_id]) - self.max_messages
        if overflow > 0:
            del self.sessions[session_id][:overflow]

    def get_history(self, session_id: str, max_turns: int = 5) -> list[dict]:
        """Return up to the latest max_turns messages for a session."""
        messages = self.sessions.get(session_id, [])
        if max_turns <= 0:
            return []
        return messages[-max_turns:]

    def clear_session(self, session_id: str) -> None:
        """Clear one session history."""
        self.sessions.pop(session_id, None)
