"""Unit tests for IntentClassifier."""

from __future__ import annotations

from unittest.mock import Mock

from src.agent.intent import IntentClassifier


def test_intent_general_query():
    classifier = IntentClassifier(openai_client=Mock())
    result = classifier.classify("大麻包装要求", history=[])
    assert result == "general_query"


def test_intent_strategy_review_keyword():
    classifier = IntentClassifier(openai_client=Mock())
    result = classifier.classify("帮我审查这个广告文案", history=[])
    assert result == "strategy_review"


def test_intent_strategy_review_marketing():
    classifier = IntentClassifier(openai_client=Mock())
    result = classifier.classify("我的营销方案合规吗", history=[])
    assert result == "strategy_review"


def test_intent_context_continuation():
    classifier = IntentClassifier(openai_client=Mock())
    history = [
        {"role": "user", "content": "帮我审查这段文案", "intent": "strategy_review"},
        {"role": "assistant", "content": "请发文案内容", "intent": "strategy_review"},
    ]
    result = classifier.classify("再看这个版本", history=history)
    assert result == "strategy_review"


def test_intent_english_input():
    classifier = IntentClassifier(openai_client=Mock())
    result = classifier.classify("Can you review my ad copy?", history=[])
    assert result == "strategy_review"


def test_intent_ambiguous_input():
    mock_client = Mock()
    completion = Mock()
    completion.choices = [Mock(message=Mock(content="strategy_review"))]
    mock_client.chat.completions.create.return_value = completion
    classifier = IntentClassifier(openai_client=mock_client)
    result = classifier.classify("Can you check this?", history=[])
    assert result == "strategy_review"
    mock_client.chat.completions.create.assert_called_once()
