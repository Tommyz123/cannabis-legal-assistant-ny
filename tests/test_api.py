"""Unit tests for FastAPI API endpoints."""

from __future__ import annotations

import httpx
import pytest

from src.agent.core import AgentResponse, SourceRef
from src.api.server import create_app


class StubConversation:
    def __init__(self) -> None:
        self.sessions: dict[str, list[dict]] = {}
        self.counter = 0

    def create_session(self) -> str:
        self.counter += 1
        session_id = f"session-{self.counter}"
        self.sessions[session_id] = []
        return session_id

    def clear_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)


class StubAgent:
    def __init__(self, conversation: StubConversation) -> None:
        self.conversation = conversation

    def process(self, session_id: str, message: str) -> AgentResponse:
        return AgentResponse(
            intent="general_query",
            answer=f"echo: {message}",
            sources=[SourceRef(file_name="law.md", domain="ads", section_title="Part 129")],
            warnings=[],
            suggestions=[],
        )


def _build_async_client() -> httpx.AsyncClient:
    conversation = StubConversation()
    app = create_app(agent=StubAgent(conversation), conversation=conversation)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.anyio
async def test_health_endpoint():
    async with _build_async_client() as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.anyio
async def test_create_session():
    async with _build_async_client() as client:
        response = await client.post("/api/session")
    assert response.status_code == 200
    assert "session_id" in response.json()


@pytest.mark.anyio
async def test_chat_endpoint():
    async with _build_async_client() as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        response = await client.post("/api/chat", json={"session_id": session_id, "message": "hello"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "general_query"
    assert payload["answer"] == "echo: hello"
    assert isinstance(payload["sources"], list)


@pytest.mark.anyio
async def test_delete_session():
    async with _build_async_client() as client:
        session_id = (await client.post("/api/session")).json()["session_id"]
        response = await client.delete(f"/api/session/{session_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_chat_missing_session():
    async with _build_async_client() as client:
        response = await client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 400


@pytest.mark.anyio
async def test_cors_headers():
    async with _build_async_client() as client:
        response = await client.options(
            "/api/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
