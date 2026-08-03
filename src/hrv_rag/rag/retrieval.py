"""
retrieval.py — Finding the most relevant chunks with cosine similarity.

The entire search is written by hand (decision K3). It amounts to only a few lines
of linear algebra, and that is precisely the advantage: every step can be explained
at the defence without opening someone else's library.

How cosine similarity works: each text is represented as a vector. Similarity is
measured by the ANGLE between vectors, not the distance. If the vectors are
normalised to unit length first, the cosine of that angle equals a plain dot
product — so searching the whole KB is a single matrix multiplication.

The angle is used rather than the distance because vector length reflects text
length more than it reflects meaning. A long chunk and a short chunk about the same
topic should count as similar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config.settings import KB_INDEX_DIR, RAGConfig, settings
from .kb_index import GeminiEmbedder, KBChunk


@dataclass(frozen=True)
class RetrievedChunk:
    """One search result together with its similarity score."""

    chunk: KBChunk
    similarity: float
    rank: int

    def describe(self) -> str:
        return f"[{self.rank}] {self.similarity:.3f}  {self.chunk.id} — {self.chunk.title}"


class KBIndex:
    """
    The embedded knowledge base, ready to be searched.

    It holds state — the vector matrix, the chunk list, the embedding client — and
    is reused across many queries, which is why it is a class.
    """

    def __init__(self, vectors: np.ndarray, chunks: list[KBChunk],
                 meta: dict, cfg: RAGConfig | None = None,
                 embedder: GeminiEmbedder | None = None) -> None:
        self.cfg = cfg or settings.rag
        self.chunks = chunks
        self.meta = meta
        self._embedder = embedder

        # Vectors are normalised ONCE here rather than on every search. Once
        # normalised, cosine similarity reduces to a dot product.
        self.vectors = self._normalize(vectors)

    # ------------------------------------------------------------- loading
    @classmethod
    def load(cls, index_dir: Path | None = None,
             cfg: RAGConfig | None = None,
             embedder: GeminiEmbedder | None = None) -> "KBIndex":
        """Load an index previously built by `kb_index.build_index`."""
        index_dir = index_dir or KB_INDEX_DIR
        vectors_path = index_dir / "vectors.npy"
        meta_path = index_dir / "meta.json"

        if not vectors_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"No index found at {index_dir}. "
                f"Run: python scripts/build_kb_index.py"
            )

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        chunks = [KBChunk(**c) for c in meta["chunks"]]
        return cls(np.load(vectors_path), chunks, meta, cfg, embedder)

    # ------------------------------------------------------------ utilities
    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        """
        Scale every vector to unit length.

        The divisor is floored at a tiny value so that a zero vector — should one
        ever occur — does not cause a division by zero.
        """
        norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
        return matrix / np.maximum(norms, 1e-12)

    @property
    def kb_version(self) -> str:
        """The KB version this index was built from; must be recorded in outputs."""
        return self.meta["kb_version"]

    def verify_kb_version(self, expected: str) -> None:
        """
        Confirm the index came from the KB version currently in use.

        If the KB is edited without rebuilding the index, the system searches old
        knowledge while the report claims a new version — and the result cannot be
        reproduced. Failing loudly is better.
        """
        if self.kb_version != expected:
            raise ValueError(
                f"Index was built from {self.kb_version}, but the KB is now "
                f"{expected}. Rebuild the index."
            )

    # ------------------------------------------------------------ searching
    def search(self, query: str, top_k: int | None = None,
               min_similarity: float | None = None) -> list[RetrievedChunk]:
        """
        Find the chunks most relevant to a text query.

        The query is embedded with task_type RETRIEVAL_QUERY — unlike the chunks,
        which use RETRIEVAL_DOCUMENT — because the two really are different in shape
        and the model treats them differently.

        Chunks scoring below the threshold are not returned. Returning two relevant
        chunks is better than three where the third is only filling space and could
        skew the LLM's interpretation.
        """
        top_k = top_k or self.cfg.top_k
        min_similarity = (min_similarity if min_similarity is not None
                          else self.cfg.min_similarity)

        if self._embedder is None:
            self._embedder = GeminiEmbedder(self.cfg)

        q = self._embedder.embed([query], task_type=self.cfg.task_query)
        q = self._normalize(q)[0]

        # Because every vector is already normalised, this dot product IS exactly
        # the cosine similarity against every chunk at once.
        scores = self.vectors @ q

        # argsort is ascending, so reverse it to put the highest score first.
        order = np.argsort(scores)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(order, start=1):
            score = float(scores[idx])
            if score < min_similarity:
                break                    # everything after this scores lower still
            results.append(RetrievedChunk(self.chunks[idx], score, rank))

        return self._apply_pinning(results, scores)

    def _apply_pinning(self, results: list[RetrievedChunk],
                       scores: np.ndarray) -> list[RetrievedChunk]:
        """
        Prepend the pinned chunk when one is configured and was not already found.

        The pinned chunk is the rating rubric, which serves a different purpose from
        ordinary knowledge: without a definition of what "low" means, the model
        cannot assign that label no matter how calm the measurements look. Its real
        similarity score is kept so the retrieval record stays honest about how it
        got there.
        """
        pinned_id = self.cfg.pinned_chunk_id
        if not pinned_id or any(r.chunk.id == pinned_id for r in results):
            return results

        for idx, chunk in enumerate(self.chunks):
            if chunk.id == pinned_id:
                pinned = RetrievedChunk(chunk, float(scores[idx]), 0)
                return [pinned] + results
        raise KeyError(f"Pinned chunk {pinned_id} is not in the index.")

    def get(self, chunk_id: str) -> KBChunk:
        """Fetch one chunk by ID — used when testing faithfulness."""
        for c in self.chunks:
            if c.id == chunk_id:
                return c
        raise KeyError(f"Chunk {chunk_id} is not in the index.")
