"""Intent classification for general legal query vs strategy review."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from openai import OpenAI


class IntentClassifier:
    """Classify user intent into general_query or strategy_review."""

    # Chinese keywords: substring match is safe (distinct enough)
    STRATEGY_KEYWORDS_CN = {"广告", "文案", "营销", "促销", "审查"}

    # English keywords: whole-word match required to avoid false positives
    # e.g. "ad" must not match "administrative", "advance", "advertising"
    STRATEGY_KEYWORDS_EN_WHOLE = {"review", "marketing"}

    def __init__(self, openai_client: "OpenAI | None" = None, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.openai_client = openai_client or self._init_openai_client()

    @staticmethod
    def _init_openai_client() -> Any | None:
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return None
        try:
            from openai import OpenAI  # pylint: disable=import-outside-toplevel
        except ImportError:
            return None
        return OpenAI(api_key=openai_api_key)

    @staticmethod
    def _extract_last_intent(history: list[dict]) -> str | None:
        for message in reversed(history):
            intent = message.get("intent")
            if intent in {"general_query", "strategy_review"}:
                return intent
        return None

    def _matches_strategy_keywords(self, text: str) -> bool:
        import re  # pylint: disable=import-outside-toplevel
        lowered = text.lower()
        if any(kw in lowered for kw in self.STRATEGY_KEYWORDS_CN):
            return True
        return any(
            re.search(r"\b" + re.escape(kw) + r"\b", lowered)
            for kw in self.STRATEGY_KEYWORDS_EN_WHOLE
        )

    def _llm_classify(self, user_input: str, history: list[dict]) -> str:
        if self.openai_client is None:
            return "general_query"

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You classify user intent for a cannabis law assistant.\n"
                            "Return only one label: general_query or strategy_review.\n"
                            "Use strategy_review for ad copy, marketing plans, compliance review requests."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"History: {history}\n"
                            f"Input: {user_input}\n"
                            "Output label only."
                        ),
                    },
                ],
                temperature=0,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return "general_query"
        try:
            label = response.choices[0].message.content.strip().lower()
        except (AttributeError, IndexError, TypeError):
            return "general_query"
        if "strategy_review" in label:
            return "strategy_review"
        return "general_query"

    def classify(self, user_input: str, history: list[dict]) -> str:
        """Classify intent using rule layer, context layer, then LLM fallback."""
        if self._matches_strategy_keywords(user_input):
            return "strategy_review"

        last_intent = self._extract_last_intent(history)
        if last_intent == "strategy_review":
            return "strategy_review"

        return self._llm_classify(user_input, history)
