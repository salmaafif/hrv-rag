"""
kb_index.py — Splits the knowledge base, embeds it, and stores the index.

Decision K3 established that retrieval is written by hand, without a framework. In
keeping with that, the embeddings are not stored in a vector store either: 23
chunks produce a 23 x 3072 float32 matrix, roughly 280 KB. At that size a search
index provides no benefit whatsoever — it only starts paying off at tens of
thousands of documents — while adding a dependency and a layer of abstraction that
makes the system harder to account for at the defence.

Two files are written:
    vectors.npy   the embedding matrix
    meta.json     chunk IDs, titles, text, references, KB version, model name
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from ..config.settings import KB_FILE, KB_INDEX_DIR, RAGConfig, settings

#: Captures each chunk: title, ID, references line, then the body up to the next
#: heading. The "## Sources" section is deliberately skipped.
_CHUNK_PATTERN = re.compile(
    r"\n## (?!Sources)(?P<title>.+?)\n"
    r"\*\*ID:\*\* `(?P<id>[A-Z0-9-]+)`[^\n]*?"
    r"\*\*References:\*\* (?P<references>[^\n]*)\n"
    r"(?P<body>.*?)(?=\n## |\n---)",
    re.S,
)

_VERSION_PATTERN = re.compile(r"\*\*Version:\*\* `(?P<version>[^`]+)`")


@dataclass(frozen=True)
class KBChunk:
    """One unit of knowledge together with its provenance."""

    id: str
    title: str
    text: str
    references: str

    def for_embedding(self) -> str:
        """
        The text actually sent to the embedding model.

        The title is included because it carries the key terms that queries tend to
        use — "RMSSD" or "Recovery", for instance — which sharpens matching compared
        with embedding the body alone.
        """
        return f"{self.title}\n\n{self.text}"


# ------------------------------------------------------------------ parser
def parse_kb(path: Path | None = None) -> tuple[list[KBChunk], str]:
    """
    Split the knowledge base file into a list of chunks.

    Splitting follows the `##` headings, per the note at the top of the KB stating
    that one heading equals one chunk. The boundaries are therefore decided by a
    human rather than by an automatic character-count splitter, which guarantees
    every chunk is semantically whole and never cut mid-sentence.

    Returns: (list of chunks, KB version)
    """
    path = path or KB_FILE
    raw = path.read_text(encoding="utf-8")

    version_match = _VERSION_PATTERN.search(raw)
    if not version_match:
        raise ValueError("KB version not found in the file header.")
    version = version_match.group("version")

    chunks = [
        KBChunk(
            id=m.group("id"),
            title=m.group("title").strip(),
            text=m.group("body").strip(),
            references=m.group("references").strip(),
        )
        for m in _CHUNK_PATTERN.finditer(raw)
    ]
    if not chunks:
        raise ValueError("No chunks parsed — check the KB formatting.")

    # IDs must be unique: the LLM uses them to cite sources and they serve as the
    # keys of the gold standard when retrieval quality is measured.
    ids = [c.id for c in chunks]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"Duplicate chunk IDs: {sorted(duplicates)}")

    return chunks, version


# ---------------------------------------------------------------- embedder
class GeminiEmbedder:
    """
    Thin wrapper around the Gemini embedding call.

    A class rather than a function because it holds state that is reused across
    calls — the API client and the model configuration — not because there is any
    variation to abstract over.
    """

    def __init__(self, cfg: RAGConfig | None = None,
                 api_key: str | None = None) -> None:
        self.cfg = cfg or settings.rag

        if api_key is None:
            # load_dotenv needs an explicit path; its automatic search fails when
            # the script runs from stdin or from another directory.
            load_dotenv(Path(__file__).resolve().parents[3] / ".env")
            api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not found. Fill in the .env file at the repo root."
            )

        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def embed(self, texts: list[str], task_type: str) -> np.ndarray:
        """
        Turn a list of texts into an embedding matrix (n_texts x dimension).

        `task_type` tells the model what role the text plays. KB chunks are embedded
        as RETRIEVAL_DOCUMENT and user feature descriptions as RETRIEVAL_QUERY.
        Distinguishing them improves matching because the two really are different
        in shape: a chunk is a long explanation, a query is a short summary.
        """
        from google.genai import types

        response = self._client.models.embed_content(
            model=self.cfg.embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        return np.asarray([e.values for e in response.embeddings],
                          dtype=np.float32)


# ----------------------------------------------------------------- builder
def build_index(kb_path: Path | None = None,
                out_dir: Path | None = None,
                cfg: RAGConfig | None = None) -> dict:
    """
    Build the index from the KB file and write it to disk.

    All chunks are embedded in ONE batched call rather than 23 separate ones —
    faster and less wasteful of quota.
    """
    cfg = cfg or settings.rag
    out_dir = out_dir or KB_INDEX_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks, kb_version = parse_kb(kb_path)
    embedder = GeminiEmbedder(cfg)
    vectors = embedder.embed([c.for_embedding() for c in chunks],
                             task_type=cfg.task_document)

    np.save(out_dir / "vectors.npy", vectors)

    meta = {
        "kb_version": kb_version,
        "embedding_model": cfg.embedding_model,
        "dimension": int(vectors.shape[1]),
        "n_chunks": len(chunks),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "chunks": [asdict(c) for c in chunks],
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta
