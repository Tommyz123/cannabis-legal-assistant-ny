"""Strategy compliance reviewer for ad/marketing content."""

from __future__ import annotations

from dataclasses import dataclass

from .prompts import STRATEGY_REVIEW_PROMPT


@dataclass
class ReviewResult:
    """Structured compliance review output."""

    violations: list[dict]
    compliance_score: str
    reminders: list[str]


class StrategyReviewer:
    """Detect obvious violations and build review context prompt."""

    PROHIBITED_SLANG = {"stoner", "weed", "pot", "high", "420"}
    MEDICAL_TERMS = {"治愈", "疗效", "治疗", "medical claim", "cure", "treat"}
    CARTOON_TERMS = {"卡通", "儿童", "未成年人", "cartoon", "kid", "child"}

    REMINDERS = [
        "受众要求：广告受众中预计至少 90% 为 21 岁及以上。",
        "地理限制：广告与学校/托育等敏感场所保持至少 500 英尺距离。",
        "时效提醒：户外广告规则请关注截止日期 2026-02-24。",
    ]

    @staticmethod
    def _find_hits(content: str, keywords: set[str]) -> list[str]:
        lowered = content.lower()
        return [keyword for keyword in keywords if keyword in lowered]

    def build_review_prompt(self, content: str, context_chunks: list[dict]) -> str:
        """Build prompt with retrieved law chunks and review rules."""
        context_lines: list[str] = []
        for idx, chunk in enumerate(context_chunks, start=1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            source = (
                f"[来源 {idx}] {metadata.get('file_name', '')} | "
                f"{metadata.get('domain', '')} | "
                f"{metadata.get('section_title', '')}"
            )
            context_lines.append(f"{source}\n{text}")
        context = "\n\n---\n\n".join(context_lines)
        return STRATEGY_REVIEW_PROMPT.format(context=context, content=content).strip()

    def review(self, content: str, context_chunks: list[dict]) -> ReviewResult:
        """Review strategy text for prohibited patterns and reminders."""
        violations: list[dict] = []

        slang_hits = self._find_hits(content, self.PROHIBITED_SLANG)
        if slang_hits:
            violations.append(
                {
                    "type": "prohibited_slang",
                    "detail": f"检测到禁用俚语: {', '.join(sorted(slang_hits))}",
                    "suggestion": "移除俚语表达，改为中性合规描述。",
                }
            )

        medical_hits = self._find_hits(content, self.MEDICAL_TERMS)
        if medical_hits:
            violations.append(
                {
                    "type": "medical_claim",
                    "detail": f"检测到医疗承诺表达: {', '.join(sorted(medical_hits))}",
                    "suggestion": "删除疗效/治愈类表述，避免医疗承诺。",
                }
            )

        cartoon_hits = self._find_hits(content, self.CARTOON_TERMS)
        if cartoon_hits:
            violations.append(
                {
                    "type": "cartoon_element",
                    "detail": f"检测到儿童导向元素: {', '.join(sorted(cartoon_hits))}",
                    "suggestion": "移除卡通或未成年人导向元素。",
                }
            )

        # Ensure prompt path remains available for Task 5 graph integration.
        _ = self.build_review_prompt(content, context_chunks)

        return ReviewResult(
            violations=violations,
            compliance_score="不合规" if violations else "合规",
            reminders=self.REMINDERS.copy(),
        )
