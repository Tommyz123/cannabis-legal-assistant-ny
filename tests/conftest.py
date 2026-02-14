"""Shared fixtures for retrieval tests."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from src.retrieval.pipeline import ChunkResult


@dataclass
class DummyBM25:
    """Simple deterministic BM25 stub for tests."""

    scores: list[float]

    def get_scores(self, _tokens: list[str]) -> list[float]:
        return self.scores


@pytest.fixture
def mock_openai_client():
    client = Mock()
    completion = Mock()
    completion.choices = [Mock(message=Mock(content="translated english question"))]
    client.chat.completions.create.return_value = completion
    return client


@pytest.fixture
def mock_chroma_collection():
    collection = Mock()
    collection.query.return_value = {
        "ids": [["c3", "c1", "missing_vec"]],
        "documents": [[]],
        "metadatas": [[]],
    }
    return collection


@pytest.fixture
def mock_bm25_index_data():
    return {
        "bm25": DummyBM25(scores=[0.9, 0.1, 0.8, 0.7]),
        "chunk_ids": ["c1", "c2", "c3", "c4"],
        "texts": ["text 1", "text 2", "text 3", "text 4"],
        "metadatas": [
            {
                "file_name": "f1.md",
                "domain": "packaging",
                "section_title": "Section 1",
                "time_sensitive": False,
                "deadline_note": "",
            },
            {
                "file_name": "f2.md",
                "domain": "ads",
                "section_title": "Section 2",
                "time_sensitive": False,
                "deadline_note": "",
            },
            {
                "file_name": "f3.md",
                "domain": "ads",
                "section_title": "Section 3",
                "time_sensitive": True,
                "deadline_note": "Outdoor ads deadline",
            },
            {
                "file_name": "f4.md",
                "domain": "retail",
                "section_title": "Section 4",
                "time_sensitive": False,
                "deadline_note": "",
            },
        ],
    }


@pytest.fixture
def mock_embeddings():
    embeddings = Mock()
    embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
    return embeddings


@pytest.fixture
def sample_chunk_result():
    return ChunkResult(
        chunk_id="sample",
        text="sample text",
        score=0.5,
        file_name="source.md",
        domain="compliance",
        section_title="Sample section",
        time_sensitive=True,
        deadline_note="Submit before 2026-02-24",
    )
