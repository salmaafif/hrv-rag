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

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

from ..config.settings import KB_INDEX_DIR, RAGConfig, settings
from .kb_index import GeminiEmbedder, KBChunk


class RetrievalMode(str, Enum):
    """
    How a segment's context is chosen — the variable the RAG ablations move.

    The thesis is titled after RAG, so "the knowledge base helps" cannot stay an
    assertion. Each mode removes one thing and leaves everything else alone, which
    is what makes the difference in the resulting score attributable:

    - `SEMANTIC` — the system as built: the three chunks closest to the query.
    - `RANDOM`   — three chunks drawn by lot. The context block is still full and
      the prompt is unchanged, so the ONLY thing destroyed is relevance. If the
      score holds up, retrieval was never doing the work and the model was
      answering from what it already knew.
    - `NONE`     — no chunks at all. Note that the shipped prompt orders the model
      to reason from the context and nothing else, so running this mode against
      that prompt measures obedience to an instruction rather than the value of the
      knowledge. It needs a closed-book prompt to mean what it appears to mean.
    """

    SEMANTIC = "semantic"
    RANDOM = "random"
    NONE = "none"


def segment_seed(base_seed: int, session_id: str, segment_index: int) -> int:
    """
    A per-segment seed that is stable across processes and runs.

    Every segment must draw a DIFFERENT lot. One seed for the whole run would hand
    all 293 segments the same three chunks, and the experiment would then rest on
    whether that single triple happened to be useful — one sample dressed up as
    293.

    Python's own `hash()` of a string is salted per process, so it cannot be used:
    the same run repeated tomorrow would draw different chunks and the cached
    results from today would be unreproducible.
    """
    material = f"{base_seed}|{session_id}|{segment_index}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(material, digest_size=8).digest(), "big")


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
    def similarities(self, query: str) -> np.ndarray:
        """
        Cosine similarity of the query against every chunk, in index order.

        Split out of `search` so the ablation can reuse it. The random condition
        still needs the true scores even though it ignores them when choosing:
        `format_context` prints a relevance figure into the prompt, and a mode that
        could not supply one would have to print something else — changing the
        shape of the prompt as well as the chunks in it, and confounding the very
        comparison the ablation exists to make.
        """
        if self._embedder is None:
            self._embedder = GeminiEmbedder(self.cfg)

        q = self._embedder.embed([query], task_type=self.cfg.task_query)
        q = self._normalize(q)[0]

        # Because every vector is already normalised, this dot product IS exactly
        # the cosine similarity against every chunk at once.
        return self.vectors @ q

    def random_chunks(self, query: str, seed: int,
                      top_k: int | None = None) -> list[RetrievedChunk]:
        """
        Chunks drawn by lot instead of by relevance — ablation U3.3.

        Exactly `top_k` are drawn, without replacement and without the similarity
        threshold. Both choices keep the comparison matched: on all 293 development
        segments the semantic condition returned exactly three chunks, so drawing
        three means the model sees the same VOLUME of context and the only
        difference left is whether that context is relevant. Applying the threshold
        instead would usually return nothing, and the run would silently become the
        no-context ablation wearing the wrong name.

        Pinning is deliberately not applied. The pinned chunk is a retrieval
        feature; leaving it in would hand the random condition the one chunk that
        matters most and understate what relevance is worth.
        """
        top_k = top_k or self.cfg.top_k
        scores = self.similarities(query)

        rng = np.random.default_rng(seed)
        picked = rng.choice(len(self.chunks), size=min(top_k, len(self.chunks)),
                            replace=False)
        return [RetrievedChunk(self.chunks[i], float(scores[i]), rank)
                for rank, i in enumerate(picked, start=1)]

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

        scores = self.similarities(query)

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
