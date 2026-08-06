"""
Tests for the anti-hallucination guards.

These matter more than their size suggests. Mandatory Rule #1 says the code
computes every number and the LLM only interprets — and `rag/guards.py` is the
only thing that ENFORCES that automatically rather than politely requesting it in
a prompt. Until now the module had no tests at all, and a mutation that made both
guards return "nothing wrong" passed the entire suite.

The two directions are tested separately on purpose:

  - A guard that misses inventions is worthless, and worse than worthless because
    it produces a clean faithfulness score for output nobody checked.
  - A guard that flags honest quotations marks sound assessments untrustworthy and
    corrupts the same metric in the other direction.

None of this needs an API key.
"""

import pytest

from hrv_rag.rag.guards import (find_fabricated_citations, find_invented_numbers,
                                find_unknown_references)

#: Stands in for a built prompt: the measurements, plus chunk bookkeeping of the
#: kind `format_context` writes above every retrieved chunk.
PROMPT = """
### KB-RMSSD-01 — RMSSD basics
(relevance 0.807; sources: Task Force 1996; Shaffer 2017)

RMSSD reflects vagal tone. A drop beyond 20% from a personal baseline is commonly
read as a meaningful withdrawal.

## MEASUREMENTS
- RMSSD: 31.70 ms
- Heart rate: 88.40 bpm
- RMSSD: -44.2% vs baseline
"""


# ------------------------------------------------------------ quoting is fine
@pytest.mark.parametrize("token", ["31.70", "31.7", "32", "44.2", "44", "88"])
def test_rounding_a_measurement_is_not_invention(token):
    """
    Reporting "-44.2%" as "44%" is quoting, not calculating.

    If this were flagged the guard would be unusable: models round, and rounding
    is exactly what a human explanation is supposed to do.
    """
    assert find_invented_numbers(f"RMSSD moved by {token} percent", PROMPT) == []


def test_sign_is_ignored():
    """"fell 44%" and "-44%" are the same measurement seen from two directions."""
    assert find_invented_numbers("RMSSD fell 44%", PROMPT) == []
    assert find_invented_numbers("RMSSD changed -44%", PROMPT) == []


def test_indonesian_decimal_comma_is_understood():
    """
    The user-facing half of every response is Indonesian, where 0,85 is a decimal.

    Read as English it splits into 0 and 85, and 85 then looks invented — so a
    faithful sentence would be recorded as a violation.
    """
    assert find_invented_numbers("Skornya 0,85 dari 1,00", "nilai 0.85 dan 1.00") == []


# ------------------------------------------------------- invention is caught
def test_invented_number_is_caught():
    assert find_invented_numbers("The stress index is 7.3", PROMPT) == ["7.3"]


@pytest.mark.parametrize("sentence,expected", [
    ("The vagal tone index computed as 0.7 indicates withdrawal.", "0.7"),
    ("The probability of high stress is 0.72.", "0.72"),
    ("Sympathetic activation is 305 arbitrary units.", "305"),
])
def test_precise_fabrications_are_caught(sentence, expected):
    """
    Regression: every one of these used to pass clean.

    A flat +/-0.5 tolerance was applied to each of the couple of dozen numbers in
    a prompt, which covered roughly half of all values between 0 and 10 by
    coincidence. The allowance now follows the precision the model itself wrote,
    so a figure stated to two decimals has to match to two decimals.
    """
    assert expected in find_invented_numbers(sentence, PROMPT)


def test_chunk_ids_and_citation_years_do_not_license_numbers():
    """
    Bookkeeping in the prompt is not knowledge and must not widen what is allowed.

    "KB-RMSSD-01" once contributed the value 1, and "1996" permitted anything
    within 2% of it — a window about 40 years wide.
    """
    assert find_invented_numbers("Reported in a 1980 study.", PROMPT) == ["1980"]


def test_a_chunk_id_is_not_a_source_for_the_number_it_contains():
    """
    The only "1" in this prompt is the -01 suffix of a chunk identifier.

    A response asserting "1" must therefore be reported. Leaving IDs in the pool
    let the model quote small integers that came from filenames, not measurements.
    """
    prompt = "### KB-RMSSD-01 — RMSSD basics\n\nVagal tone falls under load."
    assert find_invented_numbers("The stress index is 1", prompt) == ["1"]


def test_a_number_near_a_measurement_is_not_close_enough_when_stated_precisely():
    """
    The prompt says 2.31. A response asserting 2.50 is not rounding it.

    Under a flat +/-0.5 allowance the two were treated as the same figure, which is
    how invented ratios and probabilities slipped through: half a unit is enormous
    next to an LF/HF ratio. Stating a value to two decimals claims precision to two
    decimals, and the check now holds it to that.
    """
    prompt = "- LF/HF: 2.31"
    assert find_invented_numbers("The ratio is 2.50", prompt) == ["2.50"]
    # ... while a genuine rounding of the same figure still passes.
    assert find_invented_numbers("The ratio is about 2.3", prompt) == []


def test_everything_is_invented_when_the_prompt_has_no_numbers():
    """With nothing to quote, any number is the model's own."""
    assert find_invented_numbers("RMSSD fell 35%", "no numbers here") == ["35"]


# ------------------------------------------------------------- citations
def test_unknown_reference_is_caught():
    assert find_unknown_references(["KB-GHOST-01"], ["KB-RMSSD-01"]) == ["KB-GHOST-01"]


@pytest.mark.parametrize("cited", [
    "kb-rmssd-01",                 # lower case
    "KB-RMSSD-01 ",                # trailing space
    "KB-RMSSD-01 (RMSSD basics)",  # title appended
])
def test_formatting_variations_are_not_fabrications(cited):
    """
    Each of these names a chunk that really was supplied.

    Rejecting them inflated the violation count and marked sound assessments
    untrustworthy — punishing formatting as dishonesty.
    """
    assert find_unknown_references([cited], ["KB-RMSSD-01"]) == []


def test_two_ids_in_one_string_are_split():
    available = ["KB-RMSSD-01", "KB-LEVEL-01"]
    assert find_unknown_references(["KB-RMSSD-01, KB-LEVEL-01"], available) == []
    assert find_unknown_references(
        ["KB-RMSSD-01, KB-GHOST-02"], available) == ["KB-GHOST-02"]


def test_citation_fabricated_in_prose_is_caught():
    """
    A citation written into a sentence carries the same authority as a listed one.

    `find_unknown_references` only inspects the structured field, so "Per
    KB-CORTISOL-01, cortisol rises under stress" cited a chunk that exists nowhere
    in the knowledge base and nothing noticed.
    """
    assert find_fabricated_citations(
        "Per KB-CORTISOL-01, cortisol rises under stress.", ["KB-RMSSD-01"]
    ) == ["KB-CORTISOL-01"]


def test_prose_citations_that_were_retrieved_are_accepted():
    assert find_fabricated_citations(
        "As KB-RMSSD-01 explains, vagal tone falls.", ["KB-RMSSD-01"]) == []
