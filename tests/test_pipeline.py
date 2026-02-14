"""Unit tests for RetrievalPipeline."""

from __future__ import annotations

from src.retrieval.pipeline import RetrievalPipeline


def build_pipeline(
    mock_openai_client,
    mock_embeddings,
    mock_chroma_collection,
    mock_bm25_index_data,
):
    return RetrievalPipeline(
        openai_client=mock_openai_client,
        embeddings=mock_embeddings,
        collection=mock_chroma_collection,
        index_data=mock_bm25_index_data,
        today="2026-02-12",
    )


def test_hybrid_search_returns_results(
    mock_openai_client,
    mock_embeddings,
    mock_chroma_collection,
    mock_bm25_index_data,
):
    pipeline = build_pipeline(
        mock_openai_client,
        mock_embeddings,
        mock_chroma_collection,
        mock_bm25_index_data,
    )
    results = pipeline.search("packaging rules")
    assert results
    assert results[0].chunk_id in {"c1", "c3", "c4"}


def test_hybrid_search_top_k(
    mock_openai_client,
    mock_embeddings,
    mock_chroma_collection,
    mock_bm25_index_data,
):
    pipeline = build_pipeline(
        mock_openai_client,
        mock_embeddings,
        mock_chroma_collection,
        mock_bm25_index_data,
    )
    results = pipeline.search("packaging rules", top_k=2)
    assert len(results) == 2


def test_rrf_fusion_scoring():
    scores = RetrievalPipeline._rrf_scores(["a", "b"], ["b", "c"])
    assert scores["b"] > scores["a"]
    assert scores["a"] > scores["c"]


def test_translate_if_chinese_detects(
    mock_openai_client,
    mock_embeddings,
    mock_chroma_collection,
    mock_bm25_index_data,
):
    pipeline = build_pipeline(
        mock_openai_client,
        mock_embeddings,
        mock_chroma_collection,
        mock_bm25_index_data,
    )
    original, translated = pipeline.translate_if_chinese("大麻广告有什么限制")
    assert original == "大麻广告有什么限制"
    assert translated == "translated english question"
    pipeline.openai_client.chat.completions.create.assert_called_once()


def test_translate_if_chinese_passthrough(
    mock_openai_client,
    mock_embeddings,
    mock_chroma_collection,
    mock_bm25_index_data,
):
    pipeline = build_pipeline(
        mock_openai_client,
        mock_embeddings,
        mock_chroma_collection,
        mock_bm25_index_data,
    )
    original, translated = pipeline.translate_if_chinese("What are packaging rules?")
    assert original == "What are packaging rules?"
    assert translated == "What are packaging rules?"
    pipeline.openai_client.chat.completions.create.assert_not_called()


def test_build_context_with_warnings(
    mock_openai_client,
    mock_embeddings,
    mock_chroma_collection,
    mock_bm25_index_data,
    sample_chunk_result,
):
    pipeline = build_pipeline(
        mock_openai_client,
        mock_embeddings,
        mock_chroma_collection,
        mock_bm25_index_data,
    )
    context, warnings = pipeline.build_context([sample_chunk_result])
    assert "source.md" in context
    assert "sample text" in context
    assert warnings
    assert "2026-02-24" in warnings[0]
    assert "2026-02-12" in warnings[0]
