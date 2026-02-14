"""Unit tests for AgentCore graph orchestration."""

from __future__ import annotations

from src.agent.conversation import ConversationManager
from src.agent.core import AgentCore
from src.agent.intent import IntentClassifier
from src.agent.reviewer import ReviewResult, StrategyReviewer
from src.retrieval.pipeline import ChunkResult


class StubRetrieval:
    def translate_if_chinese(self, text: str) -> tuple[str, str]:
        return text, text

    def search(self, query_en: str, top_k: int = 3, min_score: float = 0.0) -> list[ChunkResult]:
        return [
            ChunkResult(
                chunk_id="c1",
                text=f"context for {query_en}",
                score=0.5,
                file_name="law.md",
                domain="ads",
                section_title="Part 129",
                time_sensitive=True,
                deadline_note="Deadline note",
            )
        ][:top_k]

    def build_context(self, chunks: list[ChunkResult]) -> tuple[str, list[str]]:
        return "joined context", ["warning from retrieval"] if chunks else []


class StubIntentClassifier(IntentClassifier):
    def __init__(self, fixed_intent: str):
        self.fixed_intent = fixed_intent

    def classify(self, user_input: str, history: list[dict]) -> str:
        return self.fixed_intent


class StubReviewer(StrategyReviewer):
    def review(self, content: str, context_chunks: list[dict]) -> ReviewResult:
        if "违规" in content:
            return ReviewResult(
                violations=[
                    {
                        "type": "prohibited_slang",
                        "detail": "detected slang",
                        "suggestion": "remove slang",
                    }
                ],
                compliance_score="不合规",
                reminders=self.REMINDERS.copy(),
            )
        return ReviewResult(violations=[], compliance_score="合规", reminders=self.REMINDERS.copy())


def _build_core(intent: str) -> tuple[AgentCore, str]:
    conversation = ConversationManager()
    session_id = conversation.create_session()
    core = AgentCore(
        retrieval_pipeline=StubRetrieval(),
        intent_classifier=StubIntentClassifier(intent),
        conversation_manager=conversation,
        strategy_reviewer=StubReviewer(),
    )
    return core, session_id


def test_process_general_query():
    core, session_id = _build_core("general_query")
    response = core.process(session_id, "大麻包装要求")
    assert response.intent == "general_query"


def test_process_strategy_review():
    core, session_id = _build_core("strategy_review")
    response = core.process(session_id, "请审查这个违规文案")
    assert response.intent == "strategy_review"


def test_process_records_history():
    core, session_id = _build_core("general_query")
    core.process(session_id, "hello")
    history = core.conversation.get_history(session_id, max_turns=10)
    assert len(history) == 2


def test_process_includes_sources():
    core, session_id = _build_core("general_query")
    response = core.process(session_id, "hello")
    assert response.sources
    assert response.sources[0].file_name == "law.md"


def test_process_includes_warnings():
    core, session_id = _build_core("general_query")
    response = core.process(session_id, "hello")
    assert "warning from retrieval" in response.warnings


def test_agent_response_structure():
    core, session_id = _build_core("general_query")
    response = core.process(session_id, "hello")
    assert hasattr(response, "intent")
    assert hasattr(response, "answer")
    assert hasattr(response, "sources")
    assert hasattr(response, "warnings")
    assert hasattr(response, "suggestions")


def test_graph_routing_general():
    core, session_id = _build_core("general_query")
    response = core.process(session_id, "hello")
    assert response.intent == "general_query"
    assert "审查结论" not in response.answer


def test_graph_routing_review():
    core, session_id = _build_core("strategy_review")
    response = core.process(session_id, "请审查这个违规文案")
    assert response.intent == "strategy_review"
    assert "审查结论" in response.answer
