"""Accuracy Evaluation Script for Cannabis Law Assistant.

Runs questions from eval/golden_dataset.json, each for N rounds (default 3).
Uses keyword checking + LLM scoring to assess accuracy and consistency.

Usage:
    venv/Scripts/python.exe eval_accuracy.py
    venv/Scripts/python.exe eval_accuracy.py --rounds 5

Output:
    reports/ACCURACY_EVAL_REPORT.md          (latest, always overwritten)
    reports/archive/ACCURACY_EVAL_<ts>.md    (timestamped archive copy)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import time
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from src.agent import AgentCore, ConversationManager, IntentClassifier, StrategyReviewer
from src.retrieval import RetrievalPipeline


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PassCriteria:
    keyword_rate_min: float
    llm_score_min: float
    questions_pass_min: int
    overall_llm_min: float
    consistency_pass_min: int


@dataclass
class TestCase:
    id: str
    category: str
    question: str
    required_keywords: list[str]
    ground_truth: str
    expected_intent: str = "general_query"
    known_issue: bool = False


@dataclass
class RoundResult:
    round_num: int
    answer: str
    intent: str
    sources_count: int
    keyword_hits: list[str]
    keyword_rate: float
    llm_score: int
    intent_match: bool = True


@dataclass
class QuestionResult:
    test_case: TestCase
    rounds: list[RoundResult]
    avg_keyword_rate: float
    avg_llm_score: float
    consistency_rate: float
    passed: bool
    intent_accuracy: float = 1.0


# ---------------------------------------------------------------------------
# Golden dataset loader
# ---------------------------------------------------------------------------

def load_dataset(
    json_path: str = "eval/golden_dataset.json",
) -> tuple[list[TestCase], PassCriteria]:
    """Load test cases and pass criteria from the golden dataset JSON file."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    pc = data["pass_criteria"]
    criteria = PassCriteria(
        keyword_rate_min=pc["keyword_rate_min"],
        llm_score_min=pc["llm_score_min"],
        questions_pass_min=pc["questions_pass_min"],
        overall_llm_min=pc["overall_llm_min"],
        consistency_pass_min=pc["consistency_pass_min"],
    )
    test_cases = [
        TestCase(
            id=tc["id"],
            category=tc["category"],
            question=tc["question"],
            required_keywords=tc["required_keywords"],
            ground_truth=tc["ground_truth"],
            expected_intent=tc.get("expected_intent", "general_query"),
            known_issue=tc.get("known_issue", False),
        )
        for tc in data["test_cases"]
    ]
    return test_cases, criteria


def load_test_cases(json_path: str = "eval/golden_dataset.json") -> list[TestCase]:
    """Backward-compatible wrapper — returns test cases only."""
    test_cases, _ = load_dataset(json_path)
    return test_cases


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------

def build_agent() -> tuple[AgentCore, OpenAI]:
    """Instantiate AgentCore and return (agent, llm_client)."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Check your .env file.")

    llm_client = OpenAI(api_key=api_key)
    agent = AgentCore(
        retrieval_pipeline=RetrievalPipeline(openai_client=llm_client),
        intent_classifier=IntentClassifier(openai_client=llm_client),
        conversation_manager=ConversationManager(),
        strategy_reviewer=StrategyReviewer(),
        llm_client=llm_client,
    )
    return agent, llm_client


# ---------------------------------------------------------------------------
# Keyword check
# ---------------------------------------------------------------------------

def keyword_check(answer: str, keywords: list[str]) -> tuple[list[str], float]:
    """Return (hits, rate) where hits are keywords found in answer (case-insensitive)."""
    if not keywords:
        return [], 1.0
    answer_lower = answer.lower()
    hits = [kw for kw in keywords if kw.lower() in answer_lower]
    return hits, len(hits) / len(keywords)


# ---------------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------------

def llm_judge(answer: str, ground_truth: str, question: str, client: OpenAI) -> int:
    """Score answer 1-5 using GPT-4o-mini. Returns int in [1, 5]."""
    prompt = (
        "You are a legal accuracy evaluator. Score the answer 1-5:\n"
        "5 = fully accurate, all key facts present\n"
        "4 = mostly accurate, minor omission\n"
        "3 = partially correct, key facts present but incomplete\n"
        "2 = significant inaccuracies or major omissions\n"
        "1 = wrong or irrelevant\n\n"
        f"Question: {question}\n\n"
        f"Reference answer: {ground_truth}\n\n"
        f"Actual answer: {answer}\n\n"
        "Reply with just a number 1-5."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=5,
        )
        raw = response.choices[0].message.content.strip()
        score = int(raw[0])
        return max(1, min(5, score))
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# Consistency scoring
# ---------------------------------------------------------------------------

def consistency_score(rounds: list[RoundResult]) -> float:
    """Average pairwise Jaccard similarity of keyword hit sets across rounds."""
    if len(rounds) < 2:
        return 1.0
    sets = [set(r.keyword_hits) for r in rounds]
    pairs = []
    n = len(sets)
    for i in range(n):
        for j in range(i + 1, n):
            union = sets[i] | sets[j]
            inter = sets[i] & sets[j]
            if not union:
                pairs.append(1.0)
            else:
                pairs.append(len(inter) / len(union))
    return statistics.mean(pairs) if pairs else 1.0


# ---------------------------------------------------------------------------
# Per-question runner
# ---------------------------------------------------------------------------

def run_question(
    agent: AgentCore,
    llm_client: OpenAI,
    tc: TestCase,
    n_rounds: int,
    criteria: PassCriteria | None = None,
) -> QuestionResult:
    """Run one test case for n_rounds, each in a fresh session."""
    if criteria is None:
        criteria = PassCriteria(
            keyword_rate_min=0.6,
            llm_score_min=3.0,
            questions_pass_min=15,
            overall_llm_min=3.5,
            consistency_pass_min=16,
        )
    rounds: list[RoundResult] = []

    for rn in range(1, n_rounds + 1):
        session_id = agent.conversation.create_session()
        t0 = time.perf_counter()
        try:
            response = agent.process(session_id, tc.question)
            answer = response.answer
            intent = response.intent
            sources_count = len(response.sources)
        except Exception as exc:
            answer = f"[ERROR: {exc}]"
            intent = "error"
            sources_count = 0
        elapsed = time.perf_counter() - t0

        hits, rate = keyword_check(answer, tc.required_keywords)
        score = llm_judge(answer, tc.ground_truth, tc.question, llm_client)
        intent_match = (intent == tc.expected_intent)

        rr = RoundResult(
            round_num=rn,
            answer=answer,
            intent=intent,
            sources_count=sources_count,
            keyword_hits=hits,
            keyword_rate=rate,
            llm_score=score,
            intent_match=intent_match,
        )
        rounds.append(rr)

        kw_str = f"{len(hits)}/{len(tc.required_keywords)}"
        intent_marker = "✓" if intent_match else f"✗(got={intent})"
        print(
            f"  {tc.id} [{tc.category}] round {rn}/{n_rounds} "
            f"... keyword={kw_str} ({rate:.0%}) llm={score} "
            f"intent={intent_marker} latency={elapsed:.1f}s"
        )

        # Small pause to avoid rate-limit bursts
        time.sleep(1.0)

    avg_kw = statistics.mean(r.keyword_rate for r in rounds)
    avg_llm = statistics.mean(r.llm_score for r in rounds)
    cons = consistency_score(rounds)
    intent_acc = statistics.mean(1.0 if r.intent_match else 0.0 for r in rounds)
    passed = avg_kw >= criteria.keyword_rate_min and avg_llm >= criteria.llm_score_min

    status = "PASS" if passed else "FAIL"
    print(
        f"  {tc.id} RESULT  avg_kw={avg_kw:.0%}  avg_llm={avg_llm:.1f}  "
        f"consistency={cons:.2f}  intent={intent_acc:.0%}  [{status}]"
    )
    return QuestionResult(
        test_case=tc,
        rounds=rounds,
        avg_keyword_rate=avg_kw,
        avg_llm_score=avg_llm,
        consistency_rate=cons,
        passed=passed,
        intent_accuracy=intent_acc,
    )


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def generate_report(
    results: list[QuestionResult],
    n_rounds: int,
    criteria: PassCriteria | None = None,
) -> str:
    """Build the Markdown report, save to fixed path and timestamped archive."""
    if criteria is None:
        criteria = PassCriteria(
            keyword_rate_min=0.6,
            llm_score_min=3.0,
            questions_pass_min=15,
            overall_llm_min=3.5,
            consistency_pass_min=16,
        )

    date_str = time.strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    overall_kw = statistics.mean(r.avg_keyword_rate for r in results)
    overall_llm = statistics.mean(r.avg_llm_score for r in results)
    overall_cons = statistics.mean(r.consistency_rate for r in results)
    cons_pass = sum(1 for r in results if r.consistency_rate >= 0.7)

    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)

    w("# ACCURACY_EVAL_REPORT")
    w()
    w(f"**Date:** {date_str}")
    w(f"**Rounds per question:** {n_rounds}")
    w(f"**Total questions:** {total}")
    w()

    # ── 1. Overview table ────────────────────────────────────────────────
    w("## 1. Overview — All Questions")
    w()
    w("| ID | Category | avg_kw | avg_llm | consistency | intent | Status |")
    w("|----|----------|--------|---------|-------------|--------|--------|")
    for r in results:
        if r.passed:
            s = "✅ PASS"
        elif r.test_case.known_issue:
            s = "❌ FAIL ⚠️known"
        else:
            s = "❌ FAIL"
        w(
            f"| {r.test_case.id} | {r.test_case.category} "
            f"| {r.avg_keyword_rate:.0%} | {r.avg_llm_score:.1f} "
            f"| {r.consistency_rate:.2f} | {r.intent_accuracy:.0%} | {s} |"
        )
    w()

    # ── 2. Overall summary ───────────────────────────────────────────────
    w("## 2. Summary")
    w()
    w("| Metric | Value | Threshold | Result |")
    w("|--------|-------|-----------|--------|")
    kw_ok = "✅" if passed >= criteria.questions_pass_min else "❌"
    llm_ok = "✅" if overall_llm >= criteria.overall_llm_min else "❌"
    cons_ok = "✅" if cons_pass >= criteria.consistency_pass_min else "❌"
    w(f"| Questions passed (kw≥{criteria.keyword_rate_min:.0%} AND llm≥{criteria.llm_score_min:.0f}) "
      f"| {passed}/{total} | ≥{criteria.questions_pass_min}/20 | {kw_ok} |")
    w(f"| Overall avg keyword rate | {overall_kw:.1%} | — | — |")
    w(f"| Overall avg LLM score | {overall_llm:.2f} | ≥{criteria.overall_llm_min} | {llm_ok} |")
    w(f"| Consistency pass (≥0.7) | {cons_pass}/{total} | ≥{criteria.consistency_pass_min}/20 | {cons_ok} |")
    w()

    # ── 3. Category breakdown ────────────────────────────────────────────
    w("## 3. Category Breakdown")
    w()
    categories: dict[str, list[QuestionResult]] = {}
    for r in results:
        cat = r.test_case.category
        categories.setdefault(cat, []).append(r)

    w("| Category | Count | avg_kw | avg_llm | avg_cons | Passed |")
    w("|----------|-------|--------|---------|----------|--------|")
    for cat, cat_results in sorted(categories.items()):
        c_kw = statistics.mean(r.avg_keyword_rate for r in cat_results)
        c_llm = statistics.mean(r.avg_llm_score for r in cat_results)
        c_cons = statistics.mean(r.consistency_rate for r in cat_results)
        c_pass = sum(1 for r in cat_results if r.passed)
        w(
            f"| {cat} | {len(cat_results)} | {c_kw:.0%} | {c_llm:.1f} "
            f"| {c_cons:.2f} | {c_pass}/{len(cat_results)} |"
        )
    w()

    # ── 4. Bottom 3 questions ────────────────────────────────────────────
    w("## 4. Bottom 3 Questions (Worst Performers)")
    w()
    sorted_by_score = sorted(results, key=lambda r: (r.avg_keyword_rate + r.avg_llm_score / 5) / 2)
    bottom3 = sorted_by_score[:3]
    for r in bottom3:
        w(f"### {r.test_case.id} — {r.test_case.category}")
        w(f"- **Question:** {r.test_case.question}")
        w(f"- **avg_kw:** {r.avg_keyword_rate:.0%}  **avg_llm:** {r.avg_llm_score:.1f}  **consistency:** {r.consistency_rate:.2f}")
        w(f"- **Required keywords:** {r.test_case.required_keywords}")
        for rr in r.rounds:
            w(f"- **Round {rr.round_num} hits:** {rr.keyword_hits}  llm={rr.llm_score}")
            w(f"  > Answer preview: {rr.answer[:200].replace(chr(10), ' ')}")
        w()

    # ── 5. Consistency issues ────────────────────────────────────────────
    w("## 5. Consistency Issues (consistency < 0.7)")
    w()
    low_cons = [r for r in results if r.consistency_rate < 0.7]
    if not low_cons:
        w("No consistency issues detected. All questions scored ≥ 0.7.")
    else:
        w("| ID | Category | consistency | avg_kw |")
        w("|----|----------|-------------|--------|")
        for r in low_cons:
            w(f"| {r.test_case.id} | {r.test_case.category} | {r.consistency_rate:.2f} | {r.avg_keyword_rate:.0%} |")
        w()
        for r in low_cons:
            w(f"### {r.test_case.id} round-by-round keyword hits")
            for rr in r.rounds:
                w(f"- Round {rr.round_num}: {rr.keyword_hits}")
            w()

    # ── 6. Findings & recommendations ────────────────────────────────────
    w("## 6. Findings & Recommendations")
    w()
    fails = [r for r in results if not r.passed]
    known_fails = [r for r in fails if r.test_case.known_issue]
    new_fails = [r for r in fails if not r.test_case.known_issue]
    if fails:
        w(f"**{len(fails)} question(s) failed** (avg_kw < {criteria.keyword_rate_min:.0%} OR avg_llm < {criteria.llm_score_min:.0f}):")
        w()
        if known_fails:
            w(f"*⚠️ Known system issues ({len(known_fails)}): these are real system defects, not eval config problems.*")
            w()
        for r in fails:
            label = " ⚠️ known_issue" if r.test_case.known_issue else ""
            w(f"- **{r.test_case.id}** ({r.test_case.category}): kw={r.avg_keyword_rate:.0%} llm={r.avg_llm_score:.1f}{label}")
            # Determine missing keywords across rounds
            all_missing = []
            for rr in r.rounds:
                missing = [k for k in r.test_case.required_keywords if k not in rr.keyword_hits]
                all_missing.extend(missing)
            if all_missing:
                freq: dict[str, int] = {}
                for k in all_missing:
                    freq[k] = freq.get(k, 0) + 1
                top_missing = sorted(freq.items(), key=lambda x: -x[1])
                w(f"  - Frequently missing keywords: {[k for k, _ in top_missing[:5]]}")
        if new_fails:
            w()
            w(f"**Action needed**: {len(new_fails)} new failure(s) require investigation.")
        w()
    else:
        w("All questions passed the accuracy threshold.")
        w()

    # ── 7. FAIL detail — full AI answer per round ────────────────────────
    fails = [r for r in results if not r.passed]
    if fails:
        w("## 7. FAIL 详情（逐题 AI 原始回答）")
        w()
        w("*此 section 展示每道 FAIL 题的完整 AI 回答，方便分析出错原因。*")
        w()
        for r in fails:
            missing_all: dict[str, int] = {}
            for rr in r.rounds:
                for kw in r.test_case.required_keywords:
                    if kw not in rr.keyword_hits:
                        missing_all[kw] = missing_all.get(kw, 0) + 1
            missing_sorted = sorted(missing_all.items(), key=lambda x: -x[1])

            w(f"### ❌ {r.test_case.id} — {r.test_case.category}")
            w(f"**问题**: {r.test_case.question}")
            w(f"**关键词要求**: {r.test_case.required_keywords}")
            w(f"**缺失关键词（出现频次）**: {[k for k, _ in missing_sorted]}")
            w(f"**avg_kw**: {r.avg_keyword_rate:.0%} | **avg_llm**: {r.avg_llm_score:.1f} | **判断**: FAIL")
            w()
            for rr in r.rounds:
                w(f"**Round {rr.round_num}** — keyword={len(rr.keyword_hits)}/{len(r.test_case.required_keywords)} "
                  f"({rr.keyword_rate:.0%})  llm={rr.llm_score}/5")
                w(f"命中: `{rr.keyword_hits}`")
                w()
                w("AI 回答：")
                w("```")
                w(rr.answer)
                w("```")
                w()

    # ── 8. Intent accuracy ───────────────────────────────────────────────
    w("## 8. Intent Classification Accuracy")
    w()
    intent_results = [(r.test_case.id, r.test_case.expected_intent, r.intent_accuracy) for r in results]
    overall_intent_acc = statistics.mean(r.intent_accuracy for r in results)
    misclassified = [r for r in results if r.intent_accuracy < 1.0]

    w(f"**Overall intent accuracy: {overall_intent_acc:.1%}** ({sum(1 for r in results if r.intent_accuracy == 1.0)}/{total} questions correct in all rounds)")
    w()
    if misclassified:
        w("| ID | Category | expected_intent | intent_accuracy | Rounds detail |")
        w("|----|----------|-----------------|-----------------|---------------|")
        for r in misclassified:
            details = " / ".join(
                f"r{rr.round_num}:{rr.intent}({'✓' if rr.intent_match else '✗'})"
                for rr in r.rounds
            )
            w(
                f"| {r.test_case.id} | {r.test_case.category} "
                f"| {r.test_case.expected_intent} | {r.intent_accuracy:.0%} | {details} |"
            )
    else:
        w("✅ All questions were classified with the correct intent in every round.")
    w()

    # Final verdict
    overall_pass = (
        (passed >= criteria.questions_pass_min)
        and (overall_llm >= criteria.overall_llm_min)
        and (cons_pass >= criteria.consistency_pass_min)
    )
    verdict = "✅ OVERALL PASS" if overall_pass else "❌ OVERALL FAIL"
    w(f"---")
    w()
    w(f"**{verdict}**  |  Questions passed: {passed}/{total}  |  avg_llm: {overall_llm:.2f}  |  consistency_pass: {cons_pass}/{total}  |  intent_acc: {overall_intent_acc:.1%}")
    w()

    report_text = "\n".join(lines)

    # Write latest report (always overwrite)
    os.makedirs("reports", exist_ok=True)
    report_path = "reports/ACCURACY_EVAL_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # Write timestamped archive copy
    os.makedirs("reports/archive", exist_ok=True)
    archive_path = f"reports/archive/ACCURACY_EVAL_{timestamp}.md"
    shutil.copy(report_path, archive_path)

    print(f"\nReport saved: {report_path}")
    print(f"Archived:    {archive_path}")

    return report_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import sys  # pylint: disable=import-outside-toplevel
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Accuracy evaluation for Cannabis Law Assistant")
    parser.add_argument("--rounds", type=int, default=3, help="Number of rounds per question (default: 3)")
    args = parser.parse_args()

    print(f"=== Cannabis Law Assistant — Accuracy Evaluation ({args.rounds} rounds) ===\n")
    print("Building agent...")
    agent, llm_client = build_agent()
    print("Agent ready.\n")

    test_cases, criteria = load_dataset()
    print(f"Loaded {len(test_cases)} test cases from golden dataset.")
    print(f"Pass criteria: kw≥{criteria.keyword_rate_min:.0%}, llm≥{criteria.llm_score_min}, "
          f"pass≥{criteria.questions_pass_min}, overall_llm≥{criteria.overall_llm_min}, "
          f"cons_pass≥{criteria.consistency_pass_min}\n")

    results: list[QuestionResult] = []
    total = len(test_cases)

    for idx, tc in enumerate(test_cases, start=1):
        print(f"[{idx}/{total}] {tc.id} — {tc.category}"
              + (" [known_issue]" if tc.known_issue else ""))
        qr = run_question(agent, llm_client, tc, n_rounds=args.rounds, criteria=criteria)
        results.append(qr)
        print()

    print("=" * 60)
    print("Generating report...")
    generate_report(results, n_rounds=args.rounds, criteria=criteria)
    print("Done.")


if __name__ == "__main__":
    main()
