"""CLI entrypoint for Cannabis Law Assistant."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from src.agent import AgentCore, ConversationManager, IntentClassifier, StrategyReviewer
from src.retrieval import RetrievalPipeline


def _build_agent() -> AgentCore:
    load_dotenv()
    llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    retrieval = RetrievalPipeline()
    intent = IntentClassifier()
    conversation = ConversationManager()
    reviewer = StrategyReviewer()
    return AgentCore(
        retrieval_pipeline=retrieval,
        intent_classifier=intent,
        conversation_manager=conversation,
        strategy_reviewer=reviewer,
        llm_client=llm_client,
    )


def _print_response(response) -> None:
    print("\n结论:")
    print(response.answer)

    if response.sources:
        print("\n来源:")
        for idx, source in enumerate(response.sources, start=1):
            print(f"{idx}. {source.file_name} | {source.domain} | {source.section_title}")

    if response.warnings:
        print("\n警告/提醒:")
        for item in response.warnings:
            print(f"- {item}")

    if response.suggestions:
        print("\n建议:")
        for item in response.suggestions:
            print(f"- {item}")


def main() -> int:
    """Run CLI in single-query mode or interactive mode."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    try:
        agent = _build_agent()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"初始化失败: {exc}")
        return 1

    session_id = agent.conversation.create_session()

    # Single-query mode: python main.py "question"
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
        if not question:
            print("请输入问题。")
            return 1
        try:
            response = agent.process(session_id, question)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"处理失败: {exc}")
            return 1
        _print_response(response)
        return 0

    print("Cannabis Law Assistant 已启动。输入 quit/q/exit/退出 可结束。\n")
    while True:
        try:
            question = input("问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            return 0

        if not question:
            continue
        if question.lower() in {"quit", "q", "exit", "退出"}:
            print("退出。")
            return 0

        try:
            response = agent.process(session_id, question)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"处理失败: {exc}")
            continue
        _print_response(response)
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
