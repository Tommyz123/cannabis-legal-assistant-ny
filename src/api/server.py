"""FastAPI server for Cannabis Law Assistant."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import AgentCore, ConversationManager, IntentClassifier, StrategyReviewer
from src.retrieval import RetrievalPipeline


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: Optional[str] = None


class ChatResponse(BaseModel):
    intent: str
    answer: str
    sources: list[dict]
    warnings: list[str]
    suggestions: list[str]


class SessionResponse(BaseModel):
    session_id: str


def _build_agent() -> AgentCore:
    retrieval = RetrievalPipeline()
    intent = IntentClassifier()
    conversation = ConversationManager()
    reviewer = StrategyReviewer()
    return AgentCore(
        retrieval_pipeline=retrieval,
        intent_classifier=intent,
        conversation_manager=conversation,
        strategy_reviewer=reviewer,
    )


def create_app(agent: AgentCore | None = None, conversation: ConversationManager | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if application.state.agent is None:
            application.state.agent = _build_agent()
            application.state.conversation = application.state.agent.conversation
        yield

    app_instance = FastAPI(title="Cannabis Law Assistant API", lifespan=lifespan)
    app_instance.state.agent = agent
    app_instance.state.conversation = conversation or (agent.conversation if agent else None)

    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app_instance.get("/api/health")
    async def health() -> dict:
        return {"status": "healthy"}

    @app_instance.post("/api/session", response_model=SessionResponse)
    async def create_session() -> SessionResponse:
        conv = app_instance.state.conversation
        if conv is None:
            raise HTTPException(status_code=500, detail="Conversation manager not initialized")
        return SessionResponse(session_id=conv.create_session())

    @app_instance.delete("/api/session/{session_id}")
    async def delete_session(session_id: str) -> dict:
        conv = app_instance.state.conversation
        if conv is None:
            raise HTTPException(status_code=500, detail="Conversation manager not initialized")
        conv.clear_session(session_id)
        return {"status": "ok"}

    @app_instance.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        if not request.message:
            raise HTTPException(status_code=400, detail="message is required")
        agent_core = app_instance.state.agent
        if agent_core is None:
            raise HTTPException(status_code=500, detail="Agent not initialized")
        result = agent_core.process(request.session_id, request.message)
        return ChatResponse(
            intent=result.intent,
            answer=result.answer,
            sources=[
                {
                    "file_name": item.file_name,
                    "domain": item.domain,
                    "section_title": item.section_title,
                }
                for item in result.sources
            ],
            warnings=result.warnings,
            suggestions=result.suggestions,
        )

    return app_instance


app = create_app()
