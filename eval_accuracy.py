"""Accuracy Evaluation Script for Cannabis Law Assistant.

Runs 20 predefined legal questions with clear correct answers, each for N rounds
(default 3). Uses keyword checking + LLM scoring to assess accuracy and consistency.

Usage:
    venv/Scripts/python.exe eval_accuracy.py
    venv/Scripts/python.exe eval_accuracy.py --rounds 5

Output: reports/ACCURACY_EVAL_REPORT.md
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

from src.agent import AgentCore, ConversationManager, IntentClassifier, StrategyReviewer
from src.retrieval import RetrievalPipeline


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    id: str
    category: str
    question: str
    required_keywords: list[str]
    ground_truth: str
    expected_intent: str = "general_query"


@dataclass
class RoundResult:
    round_num: int
    answer: str
    intent: str
    sources_count: int
    keyword_hits: list[str]
    keyword_rate: float
    llm_score: int


@dataclass
class QuestionResult:
    test_case: TestCase
    rounds: list[RoundResult]
    avg_keyword_rate: float
    avg_llm_score: float
    consistency_rate: float
    passed: bool


# ---------------------------------------------------------------------------
# Test suite — 20 questions with known correct answers
# ---------------------------------------------------------------------------

TEST_CASES: list[TestCase] = [
    # ── Category A: Licensing & Registration ──────────────────────────────
    TestCase(
        id="Q01",
        category="A-许可证",
        question="What state agency issues cannabis retail dispensary licenses in New York?",
        required_keywords=["OCM", "Office of Cannabis Management"],
        ground_truth=(
            "Cannabis retail dispensary licenses in New York are issued by the "
            "Office of Cannabis Management (OCM), a state-level agency. "
            "DCWP (NYC Department of Consumer and Worker Protection) does not "
            "issue cannabis licenses but participates in joint enforcement inspections."
        ),
    ),
    TestCase(
        id="Q02",
        category="A-许可证",
        question="Does NYC require a separate local registration for cannabis retailers beyond the state license?",
        required_keywords=["DCWP", "registration"],
        ground_truth=(
            "NYC does not require a separate DCWP cannabis license. Cannabis retail "
            "licenses are issued by OCM at the state level. However, retailers must "
            "comply with city-level requirements from DOB (building permits, Certificate "
            "of Occupancy) and FDNY (fire safety inspection), but there is no separate "
            "DCWP cannabis registration."
        ),
    ),
    TestCase(
        id="Q03",
        category="A-许可证",
        question="Within how many days of hiring must cannabis employees complete OCM responsible work training?",
        required_keywords=["30", "days", "training"],
        ground_truth=(
            "All cannabis industry employees must complete OCM's Responsible Workforce "
            "Training Program within 30 days of hire. Training includes a free online "
            "video course, at least 2 hours of employer-provided position-specific "
            "training, and at least 1 hour of implicit bias and cultural competency training."
        ),
    ),
    TestCase(
        id="Q04",
        category="A-许可证",
        question="How far in advance must cannabis licensees submit renewal applications before expiration?",
        required_keywords=["60", "120", "days", "renewal"],
        ground_truth=(
            "Cannabis licensees must submit renewal applications 60 to 120 days before "
            "license expiration. Late submissions may result in operational gaps or "
            "administrative suspension. All temporary CAURD and adult-use licenses have "
            "been extended to December 31, 2026."
        ),
    ),

    # ── Category B: Packaging & Labeling ─────────────────────────────────
    TestCase(
        id="Q05",
        category="B-包装标签",
        question="What child-resistant packaging standard must cannabis products comply with?",
        required_keywords=["ASTM", "D3475", "child-resistant"],
        ground_truth=(
            "All cannabis products must comply with ASTM D3475 (Standard Classification "
            "for Child-Resistant Packaging). Packaging must be opaque or translucent, "
            "resealable and maintain child resistance after each opening for multi-serving "
            "products. Single-use packages must be child-resistant but do not need to be "
            "resealable. Dispensaries must also provide child-resistant exit packaging."
        ),
    ),
    TestCase(
        id="Q06",
        category="B-包装标签",
        question="What is the Universal Cannabis Symbol and what does it look like?",
        required_keywords=["THC", "orange", "exclamation"],
        ground_truth=(
            "The Universal Cannabis Symbol is a standardized NYS warning symbol developed "
            "by OCM. It consists of an orange exclamation mark in an orange circle on a "
            "white background with the text 'THC'. It must appear on the front of every "
            "cannabis product package at a minimum size of 0.375 × 0.375 inches."
        ),
    ),
    TestCase(
        id="Q07",
        category="B-包装标签",
        question="Are cannabis dispensaries allowed to repackage products received from manufacturers?",
        required_keywords=["prohibited", "repackage"],
        ground_truth=(
            "No. Repackaging is prohibited. Dispensaries may not re-package cannabis "
            "products. All products must be sold in the original manufacturer packaging "
            "that has been pre-approved and labeled in compliance with 9 NYCRR Part 119."
        ),
    ),
    TestCase(
        id="Q08",
        category="B-包装标签",
        question="What visual elements are prohibited on cannabis packaging?",
        required_keywords=["cartoon", "youth", "candy", "food", "bright"],
        ground_truth=(
            "Cannabis packaging must not use: cartoon characters or toys that appeal to "
            "persons under 21, bright primary colors in a manner that appeals to children "
            "(e.g., bright candy-like colors), depictions of persons under 21, imitation "
            "of food or candy branding, celebrity or influencer endorsements, or any logo "
            "or mascot primarily associated with products marketed to children."
        ),
    ),

    # ── Category C: Marketing & Advertising ──────────────────────────────
    TestCase(
        id="Q09",
        category="C-广告营销",
        question="What percentage of a cannabis ad's audience must be 21 or older?",
        required_keywords=["90", "percent", "21"],
        ground_truth=(
            "At least 90% of the audience of any cannabis advertisement must be 21 years "
            "of age or older. This applies to all media channels including digital, print, "
            "television, radio, and outdoor advertising. Licensees must be able to "
            "demonstrate compliance with audience composition requirements."
        ),
    ),
    TestCase(
        id="Q10",
        category="C-广告营销",
        question="What distance must cannabis ads maintain from schools and daycare centers?",
        required_keywords=["500", "feet", "school"],
        ground_truth=(
            "Cannabis advertising must maintain a minimum distance of 500 feet from "
            "schools, daycare centers, playgrounds, and youth activity centers. This "
            "applies to all outdoor advertising including billboards, signage, and "
            "posters visible from a public right-of-way."
        ),
    ),
    TestCase(
        id="Q11",
        category="C-广告营销",
        question="What types of characters or themes are banned in cannabis advertising?",
        required_keywords=["cartoon", "children", "youth", "characters"],
        ground_truth=(
            "Cannabis advertising is banned from using: cartoon characters, mascots, "
            "or animated figures that primarily appeal to children or youth; themes, "
            "imagery, or language directed at persons under 21; celebrities or "
            "influencers primarily known for appealing to youth; and any content that "
            "implies cannabis use is safe or beneficial for minors."
        ),
    ),
    TestCase(
        id="Q12",
        category="C-广告营销",
        question="What is the outdoor billboard compliance deadline for cannabis advertising?",
        required_keywords=["2026", "February", "24", "billboard"],
        ground_truth=(
            "The outdoor billboard compliance deadline for cannabis advertising is "
            "February 24, 2026. All cannabis outdoor billboard advertisements must be "
            "brought into full compliance with OCM advertising regulations by this date. "
            "Non-compliant billboards must be removed or modified."
        ),
    ),

    # ── Category D: Violations & Penalties ───────────────────────────────
    TestCase(
        id="Q13",
        category="D-违规罚则",
        question="What administrative penalties can cannabis licensees face for violations?",
        required_keywords=["warning", "fine", "revocation", "suspension"],
        ground_truth=(
            "Cannabis licensees can face administrative penalties including: warning "
            "letters for minor first-time violations, fines (amounts vary based on "
            "violation severity), license suspension (temporary closure during "
            "investigation or remediation period), and license revocation (permanent "
            "loss of license for serious or repeated violations). Multiple violations "
            "escalate penalty severity."
        ),
    ),
    TestCase(
        id="Q14",
        category="D-违规罚则",
        question="What are the consequences of selling cannabis without a license in New York?",
        required_keywords=["unlicensed", "penalty", "criminal", "fine"],
        ground_truth=(
            "Selling cannabis without a license in New York is illegal and subject to "
            "serious consequences including: criminal charges and prosecution, substantial "
            "civil and criminal fines, seizure of cannabis products and business assets, "
            "store closure under Operation Padlock (multi-agency enforcement), and "
            "prohibition from future licensing. Large-scale unlicensed operations may "
            "face federal investigation."
        ),
    ),
    TestCase(
        id="Q15",
        category="D-违规罚则",
        question="Under what circumstances can a cannabis license be revoked or suspended?",
        required_keywords=["revok", "suspend", "violation", "license"],
        ground_truth=(
            "A cannabis license can be revoked or suspended under circumstances including: "
            "repeated or serious regulatory violations, sales to minors, operating outside "
            "license scope, failure to maintain required records, false statements in "
            "license applications, loss of required qualifications (e.g., Labor Peace "
            "Agreement), failure to pay required fees, or criminal conviction of a "
            "licensee or key personnel."
        ),
    ),

    # ── Category E: Operations & Safety ──────────────────────────────────
    TestCase(
        id="Q16",
        category="E-运营安全",
        question="What FDNY fire safety requirements apply to cannabis storage?",
        required_keywords=["FDNY", "fire", "MAQ", "sprinkler", "storage"],
        ground_truth=(
            "FDNY fire safety requirements for cannabis storage include: compliance with "
            "Maximum Allowable Quantities (MAQ) for combustible and flammable materials, "
            "sprinkler system requirements for storage areas exceeding MAQ thresholds, "
            "proper ventilation and fire suppression systems, storage in approved cabinets "
            "or rooms for concentrated cannabis products, fire safety inspections and "
            "approval certificates, and compliance with NYC Fire Code hazardous materials "
            "storage provisions."
        ),
    ),
    TestCase(
        id="Q17",
        category="E-运营安全",
        question="What laboratory testing requirements must cannabis products pass before sale?",
        required_keywords=["laboratory", "test", "potency", "contaminant"],
        ground_truth=(
            "Cannabis products must pass laboratory testing by an OCM-licensed testing "
            "facility before sale. Required tests include: cannabinoid potency (THC, CBD "
            "content verification), pesticide residue screening, heavy metals testing "
            "(arsenic, cadmium, lead, mercury), microbial contaminant testing (E. coli, "
            "Salmonella, yeast, mold), mycotoxin screening, residual solvent testing for "
            "extracts/concentrates, and water activity measurement. Results documented in "
            "a Certificate of Analysis (COA) linked via QR code on the product label."
        ),
    ),
    TestCase(
        id="Q18",
        category="E-运营安全",
        question="What labor protections exist for cannabis employees in New York?",
        required_keywords=["labor", "wage", "worker", "employee", "protection"],
        ground_truth=(
            "Labor protections for cannabis employees in New York include: mandatory Labor "
            "Peace Agreement guaranteeing organizing rights, wage and hour compliance "
            "oversight by DCWP, workplace safety standards enforced by DCWP, "
            "anti-discrimination policies, right to complete OCM-mandated training within "
            "30 days of hire, and protections under New York State labor laws including "
            "minimum wage requirements. Employers must maintain drug-free, smoke-free, "
            "and alcohol-free workplaces."
        ),
    ),

    # ── Category F: Strategy Review ───────────────────────────────────────
    TestCase(
        id="Q19",
        category="F-策略审查",
        question=(
            "Please review: 'Get high with our stoner products! "
            "Great for everyone including kids!'"
        ),
        required_keywords=["stoner", "kid", "prohibited", "violation"],
        ground_truth=(
            "This marketing copy violates multiple cannabis advertising regulations: "
            "(1) 'Get high' and 'stoner' are prohibited slang terms under OCM advertising "
            "rules; (2) 'Great for everyone including kids' directly targets minors and "
            "violates the prohibition on youth-directed advertising; (3) The ad fails to "
            "include required age restriction (21+) language. The copy must be completely "
            "rewritten to remove slang, exclude youth references, and add proper age gates."
        ),
        expected_intent="strategy_review",
    ),
    TestCase(
        id="Q20",
        category="F-策略审查",
        question=(
            "Please review: 'Our cannabis products cure anxiety "
            "and treat depression naturally!'"
        ),
        required_keywords=["cure", "treat", "medical", "claim", "prohibited"],
        ground_truth=(
            "This marketing copy violates cannabis advertising regulations because it "
            "makes prohibited medical/therapeutic claims: (1) 'cure anxiety' is a "
            "medical claim prohibited under 9 NYCRR Part 119 and OCM advertising rules; "
            "(2) 'treat depression' is a therapeutic claim implying FDA-level efficacy "
            "that is explicitly banned; (3) Such language is also subject to FTC and "
            "FDA enforcement. The copy must remove all health/medical claims and instead "
            "use permissible language about the product's characteristics."
        ),
        expected_intent="strategy_review",
    ),
]


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
) -> QuestionResult:
    """Run one test case for n_rounds, each in a fresh session."""
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

        rr = RoundResult(
            round_num=rn,
            answer=answer,
            intent=intent,
            sources_count=sources_count,
            keyword_hits=hits,
            keyword_rate=rate,
            llm_score=score,
        )
        rounds.append(rr)

        kw_str = f"{len(hits)}/{len(tc.required_keywords)}"
        print(
            f"  {tc.id} [{tc.category}] round {rn}/{n_rounds} "
            f"... keyword={kw_str} ({rate:.0%}) llm={score} "
            f"latency={elapsed:.1f}s"
        )

        # Small pause to avoid rate-limit bursts
        time.sleep(1.0)

    avg_kw = statistics.mean(r.keyword_rate for r in rounds)
    avg_llm = statistics.mean(r.llm_score for r in rounds)
    cons = consistency_score(rounds)
    passed = avg_kw >= 0.6 and avg_llm >= 3.0

    status = "PASS" if passed else "FAIL"
    print(
        f"  {tc.id} RESULT  avg_kw={avg_kw:.0%}  avg_llm={avg_llm:.1f}  "
        f"consistency={cons:.2f}  [{status}]"
    )
    return QuestionResult(
        test_case=tc,
        rounds=rounds,
        avg_keyword_rate=avg_kw,
        avg_llm_score=avg_llm,
        consistency_rate=cons,
        passed=passed,
    )


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def generate_report(results: list[QuestionResult], n_rounds: int) -> str:
    """Build the Markdown report and write to reports/ACCURACY_EVAL_REPORT.md."""
    date_str = time.strftime("%Y-%m-%d")

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
    w("| ID | Category | avg_kw | avg_llm | consistency | Status |")
    w("|----|----------|--------|---------|-------------|--------|")
    for r in results:
        s = "✅ PASS" if r.passed else "❌ FAIL"
        w(
            f"| {r.test_case.id} | {r.test_case.category} "
            f"| {r.avg_keyword_rate:.0%} | {r.avg_llm_score:.1f} "
            f"| {r.consistency_rate:.2f} | {s} |"
        )
    w()

    # ── 2. Overall summary ───────────────────────────────────────────────
    w("## 2. Summary")
    w()
    w("| Metric | Value | Threshold | Result |")
    w("|--------|-------|-----------|--------|")
    kw_ok = "✅" if passed >= 15 else "❌"
    llm_ok = "✅" if overall_llm >= 3.5 else "❌"
    cons_ok = "✅" if cons_pass >= 16 else "❌"
    w(f"| Questions passed (kw≥60% AND llm≥3) | {passed}/{total} | ≥15/20 | {kw_ok} |")
    w(f"| Overall avg keyword rate | {overall_kw:.1%} | — | — |")
    w(f"| Overall avg LLM score | {overall_llm:.2f} | ≥3.5 | {llm_ok} |")
    w(f"| Consistency pass (≥0.7) | {cons_pass}/{total} | ≥16/20 | {cons_ok} |")
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
    if fails:
        w(f"**{len(fails)} question(s) failed** (avg_kw < 60% OR avg_llm < 3):")
        w()
        for r in fails:
            w(f"- **{r.test_case.id}** ({r.test_case.category}): kw={r.avg_keyword_rate:.0%} llm={r.avg_llm_score:.1f}")
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
        w()
    else:
        w("All questions passed the accuracy threshold.")
        w()

    # Final verdict
    overall_pass = (passed >= 15) and (overall_llm >= 3.5) and (cons_pass >= 16)
    verdict = "✅ OVERALL PASS" if overall_pass else "❌ OVERALL FAIL"
    w(f"---")
    w()
    w(f"**{verdict}**  |  Questions passed: {passed}/20  |  avg_llm: {overall_llm:.2f}  |  consistency_pass: {cons_pass}/20")
    w()

    report_text = "\n".join(lines)

    os.makedirs("reports", exist_ok=True)
    report_path = "reports/ACCURACY_EVAL_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nReport saved: {report_path}")

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

    results: list[QuestionResult] = []
    total = len(TEST_CASES)

    for idx, tc in enumerate(TEST_CASES, start=1):
        print(f"[{idx}/{total}] {tc.id} — {tc.category}")
        qr = run_question(agent, llm_client, tc, n_rounds=args.rounds)
        results.append(qr)
        print()

    print("=" * 60)
    print("Generating report...")
    generate_report(results, n_rounds=args.rounds)
    print("Done.")


if __name__ == "__main__":
    main()
