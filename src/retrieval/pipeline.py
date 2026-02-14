"""Hybrid retrieval pipeline for cannabis law chunks."""

from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from langchain_openai import OpenAIEmbeddings
    from openai import OpenAI


@dataclass
class ChunkResult:
    """Structured retrieval result after RRF fusion."""

    chunk_id: str
    text: str
    score: float
    file_name: str
    domain: str
    section_title: str
    time_sensitive: bool
    deadline_note: str


class RetrievalPipeline:
    """Encapsulates translation, hybrid retrieval and context building."""

    def __init__(
        self,
        openai_client: "OpenAI | None" = None,
        embeddings: "OpenAIEmbeddings | None" = None,
        collection: Any | None = None,
        index_data: dict[str, Any] | None = None,
        today: str | None = None,
    ) -> None:
        self.today = today or date.today().isoformat()
        if openai_client and embeddings and collection and index_data:
            self.openai_client = openai_client
            self.embeddings = embeddings
            self.collection = collection
            self.index_data = index_data
            return

        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required.")

        chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        collection_name = os.getenv("CHROMA_COLLECTION_NAME", "cannabis_law_nyc")
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        bm25_index_path = os.getenv("BM25_INDEX_PATH", "./bm25_index.pkl")

        from langchain_openai import OpenAIEmbeddings
        from openai import OpenAI
        import chromadb

        self.openai_client = openai_client or OpenAI(api_key=openai_api_key)
        self.embeddings = embeddings or OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=openai_api_key,
        )
        chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
        self.collection = collection or chroma_client.get_collection(collection_name)

        if index_data is None:
            with open(bm25_index_path, "rb") as file:
                self.index_data = pickle.load(file)
        else:
            self.index_data = index_data

    @staticmethod
    def _is_chinese(text: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in text)

    def _translate_to_english(self, text: str) -> str:
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a legal translation assistant. "
                            "Translate the user's Chinese question about cannabis law into clear, "
                            "concise English. Output only the translated text, no explanations."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        except Exception:  # pylint: disable=broad-exception-caught
            return text

    def translate_if_chinese(self, text: str) -> tuple[str, str]:
        """Return original text plus the text to use for retrieval."""
        if self._is_chinese(text):
            return text, self._translate_to_english(text)
        return text, text

    @staticmethod
    def _rrf_scores(vec_ids: list[str], bm25_ids: list[str], k: int = 60) -> dict[str, float]:
        scores: dict[str, float] = {}
        for rank, chunk_id in enumerate(vec_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        for rank, chunk_id in enumerate(bm25_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        return scores

    def search(self, query_en: str, top_k: int = 3, min_score: float = 0.0) -> list[ChunkResult]:
        """Run vector + BM25 retrieval and fuse results with RRF."""
        bm25 = self.index_data["bm25"]
        chunk_ids = self.index_data["chunk_ids"]
        texts = self.index_data["texts"]
        metadatas = self.index_data["metadatas"]

        try:
            query_vec = self.embeddings.embed_query(query_en)
            vec_results = self.collection.query(
                query_embeddings=[query_vec],
                n_results=10,
                include=["documents", "metadatas"],
            )
            vec_ids = vec_results["ids"][0]
        except Exception:  # pylint: disable=broad-exception-caught
            vec_ids = []

        tokenized = query_en.lower().split()
        bm25_scores = bm25.get_scores(tokenized)
        top10_idx = sorted(
            range(len(bm25_scores)),
            key=lambda index: bm25_scores[index],
            reverse=True,
        )[:10]
        bm25_ids = [chunk_ids[index] for index in top10_idx]

        fused_scores = self._rrf_scores(vec_ids, bm25_ids)
        fused_ids = sorted(
            [cid for cid, score in fused_scores.items() if score >= min_score],
            key=lambda chunk_id: fused_scores[chunk_id],
            reverse=True,
        )[:top_k]

        id_to_idx = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
        results: list[ChunkResult] = []
        for chunk_id in fused_ids:
            index = id_to_idx.get(chunk_id)
            if index is None:
                continue
            metadata = metadatas[index]
            results.append(
                ChunkResult(
                    chunk_id=chunk_id,
                    text=texts[index],
                    score=fused_scores[chunk_id],
                    file_name=metadata.get("file_name", ""),
                    domain=metadata.get("domain", ""),
                    section_title=metadata.get("section_title", ""),
                    time_sensitive=bool(metadata.get("time_sensitive", False)),
                    deadline_note=metadata.get("deadline_note", ""),
                )
            )
        return results

    def build_context(self, chunks: list[ChunkResult]) -> tuple[str, list[str]]:
        """Build LLM context and collect deadline warnings."""
        context_parts: list[str] = []
        warnings: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            label = (
                f"[Source {index}] file: {chunk.file_name} | "
                f"domain: {chunk.domain} | "
                f"section: {chunk.section_title[:60]}"
            )
            context_parts.append(f"{label}\n{chunk.text}")
            if chunk.time_sensitive:
                warnings.append(
                    f"Time-sensitive warning: {chunk.deadline_note} (today: {self.today})"
                )

        return "\n\n---\n\n".join(context_parts), list(dict.fromkeys(warnings))
