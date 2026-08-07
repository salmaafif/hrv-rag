"""
Tests for the bridge from numbers to the retrieval query.

This is where computed features become the sentence that goes searching in the
knowledge base. Get it wrong and retrieval fetches knowledge about the wrong
physiological state — after which the model reasons impeccably from the wrong
chunks, and the output looks exactly as confident as a correct one.

None of this needs an API key: the query is built by code, and only the search
that consumes it needs embeddings.
"""

import pytest

from hrv_rag.core.schemas import AssessmentInput, SignalQuality
from hrv_rag.core.types import Modality, Phase
from hrv_rag.rag.query_builder import (build_query, describe_reactivity,
                                       is_atypical)


def make_input(reactivity: dict[str, float], **kwargs) -> AssessmentInput:
    defaults = dict(
        session_id="S2", segment_index=1, modality=Modality.ECG,
        device="RespiBAN chest strap, 700 Hz", phase=Phase.QUESTION,
        features={"rmssd": 31.7, "mean_hr": 88.4},
        reactivity=reactivity,
        signal_quality=SignalQuality(outlier_pct=1.5, is_acceptable=True),
    )
    return AssessmentInput(**{**defaults, **kwargs})


# ------------------------------------------------------ magnitude wording
def test_small_changes_are_called_unchanged():
    """
    Under 10% is normal segment-to-segment wobble in a resting baseline. Calling
    it a change would send the query looking for a stress response that is not
    there, and the retrieved knowledge would then justify one.
    """
    text = describe_reactivity({"delta_pct_rmssd": -6.0})
    assert "unchanged" in text
    assert "below" not in text


def test_direction_survives_into_the_words():
    # A drop and a rise of the same size mean opposite things physiologically.
    assert "below" in describe_reactivity({"delta_pct_rmssd": -22.0})
    assert "above" in describe_reactivity({"delta_pct_rmssd": +22.0})


def test_large_changes_are_called_sharp():
    assert "sharply" in describe_reactivity({"delta_pct_rmssd": -45.0})
    assert "moderately" in describe_reactivity({"delta_pct_rmssd": -22.0})


def test_the_number_itself_is_carried_with_its_sign():
    # The model is forbidden from computing, so every figure it may quote has to
    # be present in the prompt already — signed, so it cannot be misread.
    text = describe_reactivity({"delta_pct_rmssd": -44.0})
    assert "-44%" in text


def test_missing_and_unmeasurable_features_are_skipped():
    """
    NaN means the feature could not be measured. Rendering it would put the word
    "nan" into a search query, and worse, imply something was observed.
    """
    text = describe_reactivity({
        "delta_pct_rmssd": -30.0,
        "delta_pct_hf_welch": float("nan"),
    })
    assert "nan" not in text.lower()
    assert "RMSSD" in text or "rmssd" in text.lower()


def test_no_reactivity_at_all_says_so_rather_than_returning_nothing():
    # An empty query would retrieve arbitrary chunks and the model would answer
    # from whatever came back.
    assert describe_reactivity({}) == "no reactivity available"


# ----------------------------------------------------- the inverted pattern
def test_inverted_pattern_is_flagged():
    """
    Two of the five development subjects show RMSSD RISING under stress while
    heart rate rises too. Read by the textbook that says "no stress", which the
    rising heart rate contradicts — so the query has to pull in the chunk that
    explains what to do with the conflict.
    """
    assert is_atypical({"delta_pct_rmssd": +40.0, "delta_pct_mean_hr": +12.0})


def test_the_ordinary_stress_pattern_is_not_flagged():
    assert not is_atypical({"delta_pct_rmssd": -35.0, "delta_pct_mean_hr": +15.0})


def test_rmssd_rising_while_heart_rate_falls_is_not_flagged():
    # That is plain recovery, not a conflict.
    assert not is_atypical({"delta_pct_rmssd": +40.0, "delta_pct_mean_hr": -8.0})


def test_both_barely_moving_is_not_flagged():
    # Requiring both to move keeps noise from being announced as a finding.
    assert not is_atypical({"delta_pct_rmssd": +3.0, "delta_pct_mean_hr": +1.0})


def test_a_missing_feature_cannot_raise_the_flag():
    assert not is_atypical({"delta_pct_rmssd": +40.0})
    assert not is_atypical({"delta_pct_rmssd": float("nan"),
                            "delta_pct_mean_hr": +12.0})


# ------------------------------------------------------------- full query
def test_modality_always_reaches_the_query():
    """
    Mandatory rule: the modality travels with the measurement so the model can
    weigh an optical reading more cautiously. If it never enters the query, the
    chunks explaining PPG reliability can never be retrieved — and the model
    would trust a wrist reading exactly as much as a chest one.
    """
    for modality in (Modality.ECG, Modality.PPG):
        query = build_query(make_input({"delta_pct_rmssd": -30.0},
                                       modality=modality))
        assert modality.value in query


def test_question_type_is_included_when_known():
    query = build_query(make_input({"delta_pct_rmssd": -30.0},
                                   question_type="technical"))
    assert "technical" in query


def test_question_type_is_omitted_when_unknown():
    query = build_query(make_input({"delta_pct_rmssd": -30.0}))
    assert "during a" not in query


def test_the_inverted_pattern_reaches_the_query_text():
    query = build_query(make_input({"delta_pct_rmssd": +40.0,
                                    "delta_pct_mean_hr": +12.0}))
    assert "heart rate also increased" in query


def test_a_query_is_produced_even_with_nothing_measured():
    # Retrieval still has to run; the model then has to say it cannot conclude.
    # Returning an empty string would make the search meaningless instead.
    query = build_query(make_input({}))
    assert query.strip() != ""
    assert Modality.ECG.value in query
