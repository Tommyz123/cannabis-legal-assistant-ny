"""Comprehensive Evaluation Script for Cannabis Law Assistant.

This script runs a set of predefined test cases against the AgentCore to calculate
quantitative metrics:
1. Intent Classification Accuracy
2. Retrieval Hit Rate (Recall based on keywords)
3. Reviewer Detection Rate (for Strategy Review)
4. Latency (Response Time)

Generates a detailed report: REAL_EVALUATION_REPORT.md
"""

import os
import time
import json
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

from src.agent import AgentCore, ConversationManager, IntentClassifier, StrategyReviewer
from src.retrieval import RetrievalPipeline

# ---------------------------------------------------------------------------
# Test Data Configuration
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    id: str
    category: str
    input_text: str
    expected_intent: str
    expected_keywords: List[str] = None 
    expected_violations: List[str] = None 
    history: List[dict] = None

TEST_SUITE = [
    # --- Category: General Law Retrieval ---
    TestCase(
        id="RET-01",
        category="Retrieval",
        input_text="大麻产品的包装标签必须包含哪些信息？",
        expected_intent="general_query",
        expected_keywords=["label", "warning", "symbol", "packaging", "THC"]
    ),
    TestCase(
        id="RET-02",
        category="Retrieval",
        input_text="零售药房距离学校需要保持多远？",
        expected_intent="general_query",
        expected_keywords=["500", "feet", "school", "distance"]
    ),
    TestCase(
        id="RET-03",
        category="Retrieval",
        input_text="违规销售给未成年人的罚款是多少？",
        expected_intent="general_query",
        expected_keywords=["penalty", "fine", "civil", "license"]
    ),
    TestCase(
        id="RET-04",
        category="Retrieval",
        input_text="什么是BioTrack追踪系统？",
        expected_intent="general_query",
        expected_keywords=["traceability", "inventory", "seed-to-sale", "track"]
    ),
    
    # --- Category: Strategy Review (Compliance) ---
    TestCase(
        id="REV-01",
        category="Review",
        input_text="帮我审查这个广告文案：Get high with NYC's best weed!",
        expected_intent="strategy_review",
        expected_violations=["prohibited_slang"]
    ),
    TestCase(
        id="REV-02",
        category="Review",
        input_text="审查广告：Our cannabis cures insomnia and anxiety instantly.",
        expected_intent="strategy_review",
        expected_violations=["medical_claim"]
    ),
    TestCase(
        id="REV-03",
        category="Review",
        input_text="Review this ad: Kids love our yummy gummy bears with cartoons.",
        expected_intent="strategy_review",
        expected_violations=["cartoon_element"]
    ),
    TestCase(
        id="REV-04",
        category="Review",
        input_text="审查文案：Licensed dispensary, 21+ only, open late.",
        expected_intent="strategy_review",
        expected_violations=[] # Expect Compliant
    ),

    # --- Category: Edge Cases / Intent ---
    TestCase(
        id="EDG-01",
        category="Edge",
        input_text="今天天气怎么样？",
        expected_intent="general_query",
        expected_keywords=[] # Expect no specific law keywords, system should handle gracefully
    ),
    TestCase(
        id="EDG-02",
        category="Edge",
        input_text="market price",
        expected_intent="general_query",
        expected_keywords=[] 
    ),
]

# ---------------------------------------------------------------------------
# Evaluation Logic
# ---------------------------------------------------------------------------

def build_agent() -> AgentCore:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not found. Tests may fail.")
    
    try:
        llm_client = OpenAI(api_key=api_key)
    except Exception:
        llm_client = None
        
    return AgentCore(
        retrieval_pipeline=RetrievalPipeline(openai_client=llm_client),
        intent_classifier=IntentClassifier(openai_client=llm_client),
        conversation_manager=ConversationManager(),
        strategy_reviewer=StrategyReviewer(),
        llm_client=llm_client,
    )

def evaluate_case(agent: AgentCore, case: TestCase) -> Dict[str, Any]:
    session_id = agent.conversation.create_session()
    
    # Pre-fill history if needed
    if case.history:
        for msg in case.history:
            agent.conversation.add_message(session_id, msg["role"], msg["content"])

    start_time = time.perf_counter()
    try:
        response = agent.process(session_id, case.input_text)
        latency = time.perf_counter() - start_time
        success = True
        error_msg = ""
    except Exception as e:
        latency = time.perf_counter() - start_time
        response = None
        success = False
        error_msg = str(e)
        return {
            "id": case.id,
            "success": False,
            "error": error_msg,
            "latency": latency
        }

    # 1. Check Intent
    intent_match = (response.intent == case.expected_intent)

    # 2. Check Retrieval / Content
    retrieval_hit = False
    details = ""
    
    if case.category == "Retrieval":
        # Check if ANY expected keyword appears in sources OR answer
        combined_text = (response.answer + " " + " ".join([s.section_title + " " + s.file_name for s in response.sources])).lower()
        missing_keywords = []
        hits = 0
        for kw in case.expected_keywords:
            if kw.lower() in combined_text:
                hits += 1
            else:
                missing_keywords.append(kw)
        
        if not case.expected_keywords:
            retrieval_hit = True
        elif hits > 0:
            retrieval_hit = True
        else:
            retrieval_hit = False
            details = f"Missing keywords: {missing_keywords}"

    elif case.category == "Review":
        # Check violations
        violation_map = {
            "prohibited_slang": ["俚语", "slang"],
            "medical_claim": ["医疗", "medical", "cure", "treat"],
            "cartoon_element": ["卡通", "cartoon", "child", "kid"]
        }
        
        detected = True
        for expected_v in case.expected_violations:
            keywords = violation_map.get(expected_v, [])
            if not any(k in response.answer for k in keywords):
                detected = False
                details += f"Failed to detect {expected_v}. "
        
        if not case.expected_violations and "不合规" not in response.answer:
             detected = True
        elif not case.expected_violations and "不合规" in response.answer:
             detected = False
             details += "False positive: found violations when none expected."

        retrieval_hit = detected

    elif case.category == "Edge":
         retrieval_hit = True # Pass if no crash

    return {
        "id": case.id,
        "category": case.category,
        "success": success,
        "intent_match": intent_match,
        "task_success": retrieval_hit,
        "latency": latency,
        "details": details,
        "response_preview": response.answer[:100] if response else ""
    }

def generate_report(results: List[Dict[str, Any]]):
    total = len(results)
    if total == 0:
        print("No results to generate report.")
        return

    intent_correct = sum(1 for r in results if r["intent_match"])
    task_correct = sum(1 for r in results if r["task_success"])
    avg_latency = statistics.mean([r["latency"] for r in results])
    
    categories = set(r["category"] for r in results)
    cat_stats = {}
    for cat in categories:
        cat_items = [r for r in results if r["category"] == cat]
        cat_stats[cat] = {
            "count": len(cat_items),
            "intent_acc": sum(1 for r in cat_items if r["intent_match"]) / len(cat_items),
            "task_acc": sum(1 for r in cat_items if r["task_success"]) / len(cat_items),
            "avg_lat": statistics.mean([r["latency"] for r in cat_items])
        }

    report = f"""# REAL_EVALUATION_REPORT
    
**Date:** {time.strftime("%Y-%m-%d")}
**Evaluator:** Automated Benchmarking Script
**Total Test Cases:** {total}

## 1. Executive Summary

| Metric | Score | Evaluation |
| :--- | :--- | :--- |
| **Intent Accuracy** | {intent_correct/total:.1%} | {"✅ Excellent" if intent_correct/total > 0.9 else "⚠️ Needs Improvement"} |
| **Retrieval/Task Accuracy** | {task_correct/total:.1%} | {"✅ Production Ready" if task_correct/total > 0.8 else "⚠️ Optimization Needed"} |
| **Avg Latency (End-to-End)** | {avg_latency:.2f}s | {"✅ Fast" if avg_latency < 3 else "⚠️ Slow (Optimization Recommended)"} |

## 2. Category Breakdown

| Category | Count | Intent Acc | Task Acc | Avg Latency |
| :--- | :--- | :--- | :--- | :--- |
"""
    for cat, stats in cat_stats.items():
        report += f"| {cat} | {stats['count']} | {stats['intent_acc']:.1%} | {stats['task_acc']:.1%} | {stats['avg_lat']:.2f}s |\n"

    report += "\n## 3. Detailed Results\n\n"
    for r in results:
        status = "✅ PASS" if (r["intent_match"] and r["task_success"]) else "❌ FAIL"
        report += f"### [{r['id']}] {r['category']} - {status}\n"
        report += f"- **Intent Match:** {'Yes' if r['intent_match'] else 'No'}\n"
        report += f"- **Task Success:** {'Yes' if r['task_success'] else 'No'}\n"
        report += f"- **Latency:** {r['latency']:.2f}s\n"
        if r['details']:
            report += f"- **Failure Details:** {r['details']}\n"
        preview = r['response_preview'].replace('\\n', ' ')
        report += f"- **Response Preview:** {preview}...\n\n"

    with open("REAL_EVALUATION_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print(report)

def main():
    print("Starting Comprehensive Evaluation...")
    agent = build_agent()
    results = []
    
    for case in TEST_SUITE:
        print(f"Running {case.id}...", end="", flush=True)
        res = evaluate_case(agent, case)
        results.append(res)
        print(f" Done ({res['latency']:.2f}s)")
        time.sleep(0.5) # Avoid rate limits
        
    generate_report(results)
    print("\nEvaluation Complete. Report saved to REAL_EVALUATION_REPORT.md")

if __name__ == "__main__":
    main()
