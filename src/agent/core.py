"""Agent core orchestration with LangGraph-compatible routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from src.retrieval.pipeline import ChunkResult, RetrievalPipeline

from .conversation import ConversationManager
from .intent import IntentClassifier
from .prompts import GENERAL_QUERY_PROMPT, SYSTEM_BASE
from .reviewer import ReviewResult, StrategyReviewer

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


@dataclass
class SourceRef:
    """Reference to one source section."""

    file_name: str
    domain: str
    section_title: str


@dataclass
class AgentResponse:
    """Final response structure returned by AgentCore."""

    intent: str
    answer: str
    sources: list[SourceRef]
    warnings: list[str]
    suggestions: list[str]


class AgentState(TypedDict):
    """Agent state used by graph routing."""

    user_input: str
    user_input_en: str
    session_id: str
    history: list[dict]
    intent: str
    chunks: list[ChunkResult]
    context: str
    warnings: list[str]
    answer: str
    sources: list[SourceRef]
    suggestions: list[str]
    review_result: ReviewResult | None


class _FallbackCompiledGraph:
    """Small fallback graph runner when langgraph is unavailable."""

    def __init__(self, core: "AgentCore") -> None:
        self.core = core

    def invoke(self, state: AgentState) -> AgentState:
        current = state.copy()
        current.update(self.core.intent_node(current))
        route = self.core.route_by_intent(current)
        if route == "query_node":
            current.update(self.core.query_node(current))
        else:
            current.update(self.core.review_node(current))
        current.update(self.core.response_node(current))
        return current


class AgentCore:
    """Orchestrates intent, retrieval/review, and response formatting."""

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        intent_classifier: IntentClassifier,
        conversation_manager: ConversationManager,
        strategy_reviewer: StrategyReviewer,
        llm_client: Any | None = None,
    ) -> None:
        self.retrieval = retrieval_pipeline
        self.intent_classifier = intent_classifier
        self.conversation = conversation_manager
        self.reviewer = strategy_reviewer
        self.llm_client = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> "CompiledStateGraph | _FallbackCompiledGraph":
        try:
            from langgraph.graph import END, START, StateGraph  # pylint: disable=import-outside-toplevel
        except ImportError:
            return _FallbackCompiledGraph(self)

        graph = StateGraph(AgentState)
        graph.add_node("intent_node", self.intent_node)
        graph.add_node("query_node", self.query_node)
        graph.add_node("review_node", self.review_node)
        graph.add_node("response_node", self.response_node)
        graph.add_edge(START, "intent_node")
        graph.add_conditional_edges(
            "intent_node",
            self.route_by_intent,
            {"query_node": "query_node", "review_node": "review_node"},
        )
        graph.add_edge("query_node", "response_node")
        graph.add_edge("review_node", "response_node")
        graph.add_edge("response_node", END)
        return graph.compile()

    @staticmethod
    def _chunk_to_source(chunk: ChunkResult) -> SourceRef:
        return SourceRef(
            file_name=chunk.file_name,
            domain=chunk.domain,
            section_title=chunk.section_title,
        )

    @staticmethod
    def _build_retrieval_input(user_input: str, history: list[dict]) -> str:
        """Enrich short follow-up queries with context from the last user turn."""
        if len(user_input.strip()) < 15 and history:
            last_user = next(
                (m["content"] for m in reversed(history) if m["role"] == "user"),
                None,
            )
            if last_user:
                return f"{last_user[:50]} {user_input}"
        return user_input

    @staticmethod
    def _is_refusal(answer: str) -> bool:
        """Return True if the answer is an off-topic refusal with no legal content."""
        refusal_phrases = ("无法回答", "我无法回答", "不能回答", "超出我的")
        return any(phrase in answer for phrase in refusal_phrases)

    def route_by_intent(self, state: AgentState) -> str:
        return "review_node" if state["intent"] == "strategy_review" else "query_node"

    def intent_node(self, state: AgentState) -> dict:
        intent = self.intent_classifier.classify(state["user_input"], state["history"])
        return {"intent": intent}

    def _generate_general_answer(self, state: AgentState) -> str:
        if self.llm_client is None:
            if state["context"]:
                return f"基于检索内容的结论：{state['context'][:200]}"
            return "未检索到可回答该问题的法规内容。"

        user_prompt = GENERAL_QUERY_PROMPT.format(
            context=state["context"],
            question=state["user_input"],
        )
        response = self.llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()

    def query_node(self, state: AgentState) -> dict:
        retrieval_input = self._build_retrieval_input(state["user_input"], state["history"])
        _, query_en = self.retrieval.translate_if_chinese(retrieval_input)
        chunks = self.retrieval.search(query_en, top_k=8, min_score=0.015)
        context, warnings = self.retrieval.build_context(chunks)
        answer = self._generate_general_answer({**state, "user_input_en": query_en, "context": context})
        sources = [] if self._is_refusal(answer) else [self._chunk_to_source(chunk) for chunk in chunks]
        return {
            "user_input_en": query_en,
            "chunks": chunks,
            "context": context,
            "warnings": warnings,
            "answer": answer,
            "sources": sources,
            "suggestions": [],
            "review_result": None,
        }

    def review_node(self, state: AgentState) -> dict:
        _, query_en = self.retrieval.translate_if_chinese(state["user_input"])
        chunks = self.retrieval.search(query_en, top_k=8, min_score=0.015)
        _, warnings = self.retrieval.build_context(chunks)
        context_chunks = [
            {
                "text": chunk.text,
                "metadata": {
                    "file_name": chunk.file_name,
                    "domain": chunk.domain,
                    "section_title": chunk.section_title,
                },
            }
            for chunk in chunks
        ]
        review_result = self.reviewer.review(state["user_input"], context_chunks)
        violation_lines = [item["detail"] for item in review_result.violations]
        answer = (
            f"审查结论：{review_result.compliance_score}\n"
            + ("\n".join(violation_lines) if violation_lines else "未发现明显违规点。")
        )
        sources = [self._chunk_to_source(chunk) for chunk in chunks]
        suggestions = [item["suggestion"] for item in review_result.violations]
        merged_warnings = warnings + review_result.reminders
        return {
            "user_input_en": query_en,
            "chunks": chunks,
            "warnings": merged_warnings,
            "answer": answer,
            "sources": sources,
            "suggestions": suggestions,
            "review_result": review_result,
        }

    def response_node(self, state: AgentState) -> dict:
        self.conversation.add_message(
            state["session_id"],
            "user",
            state["user_input"],
            intent=state["intent"],
        )
        self.conversation.add_message(
            state["session_id"],
            "assistant",
            state["answer"],
            intent=state["intent"],
        )
        return {"intent": state["intent"]}

    def process(self, session_id: str, user_input: str) -> AgentResponse:
        """Process one user query through the graph."""
        history = self.conversation.get_history(session_id, max_turns=5)
        initial_state: AgentState = {
            "user_input": user_input,
            "user_input_en": "",
            "session_id": session_id,
            "history": history,
            "intent": "",
            "chunks": [],
            "context": "",
            "warnings": [],
            "answer": "",
            "sources": [],
            "suggestions": [],
            "review_result": None,
        }
        final_state = self.graph.invoke(initial_state)
        return AgentResponse(
            intent=final_state["intent"],
            answer=final_state["answer"],
            sources=final_state["sources"],
            warnings=final_state["warnings"],
            suggestions=final_state["suggestions"],
        )
