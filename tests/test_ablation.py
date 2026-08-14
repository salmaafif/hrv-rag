"""
Tests for the RAG ablation modes (BACKLOG U3.2 and U3.3).

An ablation is only worth running if the ablated condition differs from the real
one in EXACTLY ONE way. Everything else — how many chunks reach the prompt, how the
prompt is shaped, which knowledge base is searched — has to stay identical, or the
difference in the resulting score cannot be attributed to anything.

These tests hold that one-difference property in place. Nothing here calls an API:
the index is built from a handful of fake chunks with hand-written vectors, so the
selection rules can be checked against answers known in advance.
"""

from dataclasses import replace

import numpy as np
import pytest

from hrv_rag.core.schemas import AssessmentInput, SignalQuality
from hrv_rag.core.types import Modality, Phase
from hrv_rag.evaluation.cache import cache_key
from hrv_rag.rag.kb_index import KBChunk
from hrv_rag.rag.retrieval import KBIndex, RetrievalMode, segment_seed

N_CHUNKS = 8


class FakeEmbedder:
    """Returns a fixed query vector, so similarity is decided by the chunks alone."""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts, task_type):
        self.calls += 1
        vector = np.zeros((1, 4), dtype=np.float32)
        vector[0, 0] = 1.0
        return vector


@pytest.fixture
def index() -> KBIndex:
    """
    Eight chunks whose similarity to the query is known by construction.

    Chunk i leans on the first axis by (8 - i)/8, so KB-00 is the closest match and
    KB-07 the furthest. Semantic search must return the first three in that order,
    and any other ordering means something is wrong with the selection rather than
    with the embedding.
    """
    vectors = np.zeros((N_CHUNKS, 4), dtype=np.float32)
    chunks = []
    for i in range(N_CHUNKS):
        vectors[i, 0] = (N_CHUNKS - i) / N_CHUNKS
        vectors[i, 1] = 0.1
        chunks.append(KBChunk(id=f"KB-{i:02d}", title=f"chunk {i}",
                              text=f"body of chunk {i}", references="Someone 2020"))
    meta = {"kb_version": "kb_test", "chunks": [c.__dict__ for c in chunks]}
    return KBIndex(vectors, chunks, meta, embedder=FakeEmbedder())


def an_input(segment: int = 1, session: str = "S2") -> AssessmentInput:
    return AssessmentInput(
        session_id=session, segment_index=segment, modality=Modality.ECG,
        phase=Phase.QUESTION, device="chest strap",
        signal_quality=SignalQuality(outlier_pct=1.2, is_acceptable=True),
        features={"rmssd": 30.0, "mean_hr": 80.0},
        reactivity={"delta_pct_rmssd": -30.0, "delta_pct_mean_hr": 12.0},
    )


# --------------------------------------------------------------- selection
def test_semantic_search_returns_the_closest_chunks_in_order(index):
    """The control condition. If this drifts, every ablation loses its reference."""
    hits = index.search("apa saja", min_similarity=-1.0)

    assert [h.chunk.id for h in hits] == ["KB-00", "KB-01", "KB-02"]


def test_random_draws_the_same_number_of_chunks_as_search(index):
    """
    Volume of context is held constant, so only relevance differs.

    On all 293 development segments the semantic condition returned exactly three
    chunks. A random condition handing over one or five would confound "irrelevant
    context" with "less context", and the ablation would answer neither question.

    Drawing WITH replacement would also usually return three, so distinctness is
    checked across many seeds rather than one: with eight chunks a single draw
    repeats itself only about a third of the time, and one lucky seed would let a
    duplicate-producing bug through. A duplicate would show the model the same
    chunk twice and quietly reduce the context to two.
    """
    assert len(index.search("apa saja", min_similarity=-1.0)) == 3

    for seed in range(40):
        hits = index.random_chunks("apa saja", seed=seed)
        assert len(hits) == 3
        assert len({h.chunk.id for h in hits}) == 3


def test_random_actually_ignores_relevance(index):
    """
    Over many draws the random condition must reach chunks semantic search never
    would. Always returning the top three would make the ablation a copy of the
    control that quietly reports "no difference".
    """
    seen = set()
    for seed in range(40):
        seen |= {h.chunk.id for h in index.random_chunks("apa saja", seed=seed)}

    assert seen == {f"KB-{i:02d}" for i in range(N_CHUNKS)}


def test_random_reports_the_true_similarity_of_what_it_drew(index):
    """
    The relevance figure is printed into the prompt, so it cannot be faked or
    blanked: a differently shaped prompt would be a second difference between the
    conditions. Here the score must match the chunk actually drawn, not its rank.
    """
    hits = index.random_chunks("apa saja", seed=7)
    scores = index.similarities("apa saja")
    by_id = {c.id: float(scores[i]) for i, c in enumerate(index.chunks)}

    for hit in hits:
        assert hit.similarity == pytest.approx(by_id[hit.chunk.id])


def test_random_ignores_the_similarity_threshold(index):
    """
    Applying the threshold would usually leave nothing, and the run would silently
    become the no-context ablation while still calling itself 'random'.
    """
    # Above the closest chunk's 0.995, so semantic search is left with nothing.
    index.cfg = replace(index.cfg, min_similarity=0.999)

    assert len(index.random_chunks("apa saja", seed=3)) == 3
    assert index.search("apa saja") == []


# ------------------------------------------------------------------ seeds
def test_every_segment_draws_a_different_lot():
    """
    One seed for the whole run would give all 293 segments the same three chunks,
    and the experiment would rest on whether that single triple happened to help —
    one sample reported as 293.
    """
    seeds = {segment_seed(1, "S2", i) for i in range(50)}

    assert len(seeds) == 50


def test_the_lot_is_the_same_tomorrow():
    """
    Python salts `hash()` per process, so a seed derived from it would draw
    different chunks on a rerun and the cached results could never be reproduced.
    """
    assert segment_seed(1, "S2", 7) == segment_seed(1, "S2", 7)
    assert segment_seed(1, "S2", 7) != segment_seed(2, "S2", 7)
    assert segment_seed(1, "S2", 7) != segment_seed(1, "S3", 7)


# --------------------------------------------------------------- pipeline
def test_the_pipeline_asks_for_the_context_its_mode_requires(index):
    from hrv_rag.rag.pipeline import AssessmentPipeline

    def context_for(mode):
        pipeline = AssessmentPipeline.__new__(AssessmentPipeline)
        pipeline.index, pipeline.retrieval = index, mode
        return pipeline._context_for(an_input())

    assert ([h.chunk.id for h in context_for(RetrievalMode.SEMANTIC)]
            == ["KB-00", "KB-01", "KB-02"])
    assert len(context_for(RetrievalMode.RANDOM)) == 3
    assert context_for(RetrievalMode.NONE) == []


def test_no_context_mode_never_touches_the_embedding_api(index):
    """
    Nothing to retrieve means nothing to embed. Spending a call anyway would be
    paid for on every segment of a 293-row run, for a vector thrown away.
    """
    from hrv_rag.rag.pipeline import AssessmentPipeline

    pipeline = AssessmentPipeline.__new__(AssessmentPipeline)
    pipeline.index, pipeline.retrieval = index, RetrievalMode.NONE
    pipeline._context_for(an_input())

    assert index._embedder.calls == 0


# ----------------------------------------------------- the closed-book prompt
SHIPPED_PROMPT = "HRV_stress_interpretation"
CLOSED_BOOK_PROMPT = "HRV_stress_interpretation_nokb"


def test_the_closed_book_prompt_fills_in_and_carries_no_context():
    """
    It must render from the same substitutions as the shipped one — a template that
    only fails at run time would fail after the GPU is already rented.
    """
    from hrv_rag.rag.prompt import build_prompt

    text = build_prompt(an_input(), [], version=CLOSED_BOOK_PROMPT)

    assert "## MEASUREMENTS" in text and "## CONTEXT" not in text
    assert "{" not in text.split("## SYSTEM INSTRUCTION")[1]   # nothing unfilled
    assert "no knowledge chunk passed the relevance threshold" not in text


def test_the_closed_book_prompt_drops_only_the_rules_that_named_the_context():
    """
    An ablation is attributable only if ONE thing changed. The context and the two
    rules pointing at it must go — a closed-book condition cannot be ordered to
    reason from a book it does not have — and nothing else may drift, or the
    difference in score belongs to an unknown mixture of causes.
    """
    from hrv_rag.rag.prompt import load_template

    shipped = load_template(SHIPPED_PROMPT)
    closed = load_template(CLOSED_BOOK_PROMPT)

    # Gone, and they are the reason this file exists.
    assert "Judge using the CONTEXT only" in shipped
    assert "Judge using the CONTEXT only" not in closed
    assert "list those chunk IDs in `references`" in shipped
    assert "list those chunk IDs in `references`" not in closed

    # Kept, word for word. Mandatory Rule #1, the honest-abstention rule, the
    # not-a-diagnosis rule, how features are weighed, and the output languages.
    for clause in [
        "Never calculate, estimate, round, or invent",
        "Any figure you mention must appear verbatim in MEASUREMENTS.",
        "**`uncertain` is a valid and expected answer.**",
        "not a clinical diagnosis",
        "Prefer **RMSSD and heart rate**",
        "Consistency across features matters more than the size of any single",
        "`user_summary` and `user_recommendation`: **Indonesian**",
    ]:
        assert clause in shipped and clause in closed, clause


def test_the_closed_book_prompt_tells_the_model_not_to_cite():
    """
    With no chunk IDs supplied, any citation is fabricated by definition — the
    guard would flag every row and faithfulness would collapse for a reason that
    is an artefact of the setup rather than a property of the model.
    """
    from hrv_rag.rag.prompt import load_template

    closed = load_template(CLOSED_BOOK_PROMPT)

    assert "Leave `references` empty" in closed


# ------------------------------------------------------------------ cache
def test_an_ablation_row_cannot_be_mistaken_for_a_real_one():
    """Different condition, different key — otherwise one overwrites the other."""
    common = dict(subject="S2", phase="question", segment=1, modality="ECG",
                  kb_version="kb_v2.0", prompt_version="v1", model="ollama:x",
                  temperature=0.0, pinned=None)
    keys = {cache_key(**common, retrieval=m.value) for m in RetrievalMode}

    assert len(keys) == len(RetrievalMode)


def test_the_key_of_a_normal_run_is_byte_for_byte_what_it_always_was():
    """
    293 assessments are already on disk, each costing about nine seconds of rented
    GPU, and all were stored before this field existed. Appending it
    unconditionally would miss every one of them and re-pay for the lot.

    The expected string is written out in full on purpose: comparing against a
    freshly computed key would pass even if the format changed on both sides.
    """
    key = cache_key(subject="S2", phase="calibration", segment=1, modality="ECG",
                    kb_version="kb_v2.0",
                    prompt_version="HRV_stress_interpretation",
                    model="gemini-2.5-flash", temperature=0.0, pinned=None)

    assert key == ("S2|calibration|1|ECG|kb_v2.0|HRV_stress_interpretation"
                   "|gemini-2.5-flash|0.0|none")
