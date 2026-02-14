"""Evaluation script: re-runs all 14 test scenarios from EVALUATION_REPORT.md."""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

from src.agent import AgentCore, ConversationManager, IntentClassifier, StrategyReviewer
from src.retrieval import RetrievalPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEPARATOR = "=" * 70


def build_agent() -> AgentCore:
    load_dotenv()
    llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return AgentCore(
        retrieval_pipeline=RetrievalPipeline(),
        intent_classifier=IntentClassifier(),
        conversation_manager=ConversationManager(),
        strategy_reviewer=StrategyReviewer(),
        llm_client=llm_client,
    )


def run_test(agent: AgentCore, label: str, session_id: str, user_input: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"[{label}] 输入: {user_input}")
    print("-" * 70)
    try:
        resp = agent.process(session_id, user_input)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"错误: {exc}")
        return

    print(f"意图: {resp.intent}")
    print(f"\n回答:\n{resp.answer}")

    if resp.sources:
        print("\n来源:")
        for i, s in enumerate(resp.sources, 1):
            print(f"  {i}. {s.file_name} | {s.section_title}")

    if resp.warnings:
        print("\n警告/提醒:")
        for w in resp.warnings:
            print(f"  - {w}")

    if resp.suggestions:
        print("\n建议:")
        for sg in resp.suggestions:
            print(f"  - {sg}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("Cannabis Law Assistant — 场景评估（对照 EVALUATION_REPORT.md）")
    print(SEPARATOR)
    print("初始化 Agent...")
    agent = build_agent()
    print("Agent 初始化完成。\n")

    # ------------------------------------------------------------------
    # Section 1: 法规问答准确性测试（5 题）
    # ------------------------------------------------------------------
    print("\n" + SEPARATOR)
    print("【第一部分】法规问答准确性测试（Q1–Q5）")
    print(SEPARATOR)

    run_test(agent, "Q1", agent.conversation.create_session(),
             "大麻产品的包装标签必须包含哪些信息？")
    time.sleep(1)

    run_test(agent, "Q2", agent.conversation.create_session(),
             "零售药房距离学校需要保持多远？")
    time.sleep(1)

    run_test(agent, "Q3", agent.conversation.create_session(),
             "我开一家大麻零售店大概需要多少钱？")
    time.sleep(1)

    run_test(agent, "Q4", agent.conversation.create_session(),
             "违规销售给未成年人的罚款是多少？")
    time.sleep(1)

    run_test(agent, "Q5", agent.conversation.create_session(),
             "BioTrack追踪系统是什么？")
    time.sleep(1)

    # ------------------------------------------------------------------
    # Section 2: 广告营销合规审查测试（3 题）
    # ------------------------------------------------------------------
    print("\n\n" + SEPARATOR)
    print("【第二部分】广告营销合规审查测试（AD1–AD3）")
    print(SEPARATOR)

    run_test(agent, "AD1", agent.conversation.create_session(),
             "帮我审查这个广告文案：Get high with NYC's best weed!")
    time.sleep(1)

    run_test(agent, "AD2", agent.conversation.create_session(),
             "帮我审查这个广告：Our cannabis cures insomnia and anxiety")
    time.sleep(1)

    run_test(agent, "AD3", agent.conversation.create_session(),
             "帮我审查这个广告：Licensed NYC dispensary. Adults 21+ only. Lab-tested products.")
    time.sleep(1)

    # ------------------------------------------------------------------
    # Section 3: 多轮对话连贯性测试
    # ------------------------------------------------------------------
    print("\n\n" + SEPARATOR)
    print("【第三部分】多轮对话连贯性测试（MULTI 1–3，同一 session）")
    print(SEPARATOR)

    sid_multi = agent.conversation.create_session()
    run_test(agent, "MULTI-1", sid_multi, "大麻零售许可证怎么申请？")
    time.sleep(1)
    run_test(agent, "MULTI-2", sid_multi, "申请费用大概多少？")
    time.sleep(1)
    run_test(agent, "MULTI-3", sid_multi, "需要多长时间才能拿到？")
    time.sleep(1)

    # ------------------------------------------------------------------
    # Section 4: 边界情况测试（3 题）
    # ------------------------------------------------------------------
    print("\n\n" + SEPARATOR)
    print("【第四部分】边界情况测试（EDGE1–EDGE3）")
    print(SEPARATOR)

    run_test(agent, "EDGE1", agent.conversation.create_session(),
             "cannabis packaging requirements and 大麻税率是多少")
    time.sleep(1)

    run_test(agent, "EDGE2", agent.conversation.create_session(),
             "今天天气怎么样？")
    time.sleep(1)

    run_test(agent, "EDGE3", agent.conversation.create_session(),
             "怎么办")

    print(f"\n\n{SEPARATOR}")
    print("评估完成。请对照 EVALUATION_REPORT.md 进行人工评分。")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
