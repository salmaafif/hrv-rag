"""
build_kb_index.py — Build the knowledge base index, then probe it with sample queries.

Usage:
    python scripts/build_kb_index.py              # build + run sample queries
    python scripts/build_kb_index.py --search-only
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_rag.rag.kb_index import build_index                    # noqa: E402
from hrv_rag.rag.retrieval import KBIndex                       # noqa: E402

#: Sample queries representing conditions the system will actually meet.
#: The third one deliberately represents the atypical pattern found in subjects
#: S6 and S10, to confirm the chunk that handles it is really retrieved.
TEST_QUERIES = [
    "RMSSD 35% below baseline, HF decreased, LF/HF increased, heart rate elevated",
    "data comes from a PPG smartwatch, how reliable is the assessment",
    "RMSSD increased but heart rate also increased while answering a question",
    "technical question requiring arithmetic and recalling details",
    "how quickly does the person return to calm after a difficult question",
]


def main() -> None:
    if "--search-only" not in sys.argv:
        print("Building index...")
        meta = build_index()
        print(f"  KB version : {meta['kb_version']}")
        print(f"  model      : {meta['embedding_model']}")
        print(f"  chunks     : {meta['n_chunks']}")
        print(f"  dimension  : {meta['dimension']}")

    index = KBIndex.load()
    print(f"\nIndex loaded: {len(index.chunks)} chunks, {index.kb_version}\n")

    for query in TEST_QUERIES:
        print(f"QUERY: {query}")
        hits = index.search(query)
        if not hits:
            print("   (nothing above the similarity threshold)")
        for hit in hits:
            print("   " + hit.describe())
        print()


if __name__ == "__main__":
    main()
