"""Unit tests for StrategyReviewer."""

from __future__ import annotations

from src.agent.reviewer import StrategyReviewer


def _sample_chunks() -> list[dict]:
    return [
        {
            "text": "Part 129 prohibits marketing targeting persons under 21.",
            "metadata": {
                "file_name": "part129.md",
                "domain": "marketing",
                "section_title": "Audience Restrictions",
            },
        }
    ]


def test_detect_prohibited_slang():
    reviewer = StrategyReviewer()
    result = reviewer.review("This ad gets you High quickly.", _sample_chunks())
    assert any(item["type"] == "prohibited_slang" for item in result.violations)


def test_detect_medical_claim():
    reviewer = StrategyReviewer()
    result = reviewer.review("本产品可治愈失眠。", _sample_chunks())
    assert any(item["type"] == "medical_claim" for item in result.violations)


def test_detect_cartoon_element():
    reviewer = StrategyReviewer()
    result = reviewer.review("海报使用卡通角色吸引用户。", _sample_chunks())
    assert any(item["type"] == "cartoon_element" for item in result.violations)


def test_clean_ad_passes():
    reviewer = StrategyReviewer()
    result = reviewer.review("面向 21+ 成人，强调依法购买与理性消费。", _sample_chunks())
    assert result.violations == []
    assert result.compliance_score == "合规"


def test_compliance_reminders_included():
    reviewer = StrategyReviewer()
    result = reviewer.review("普通品牌介绍文案。", _sample_chunks())
    assert any("90%" in item for item in result.reminders)
    assert any("500 英尺" in item for item in result.reminders)
    assert any("2026-02-24" in item for item in result.reminders)


def test_review_prompt_construction():
    reviewer = StrategyReviewer()
    prompt = reviewer.build_review_prompt("请审查我的营销文案", _sample_chunks())
    assert "请审查我的营销文案" in prompt
    assert "Part 129 prohibits marketing targeting persons under 21." in prompt
    assert "审查规则" in prompt
