"""
test_k4_guard.py — the guard that catches disclosure rather than fabrication.

The two older guards ask "did the model make this up?". This one asks "should the
user be seeing this at all?", and the difference is why it was missing for so long:
the offending output passed both existing checks cleanly, because every number in
it was real and every citation was real.

A guard that cries wolf gets switched off, and then it protects nothing. So half
of what is pinned here is the things it must NOT flag.
"""

from __future__ import annotations

from hrv_rag.core.schemas import Assessment, LLMResponse, StressLevel
from hrv_rag.rag.guards import find_k4_violations

#: The exact sentence `deepseek-r1:latest` produced on WESAD S2, segment 1, into
#: the field a KARIRLINK user reads. Kept verbatim: this is the evidence the guard
#: exists for, and paraphrasing it would loosen the test over time.
REAL_VIOLATION = (
    "HRV menunjukkan penurunan signifikan selama sesi wawancara, dengan RMSSD, "
    "SDNN, dan pNN50 semuanya berkurang terhadap baseline sendiri. Heart rate "
    "meningkat, yang konsisten dengan respons stres."
)

#: What gpt-oss:20b produced for the same segment, through the same prompt.
REAL_CLEAN = (
    "Selama pertanyaan ini, tubuh Anda menunjukkan tanda-tanda stres yang cukup "
    "kuat. Cobalah melakukan pernapasan dalam dan fokus pada pikiran positif "
    "sebelum melanjutkan wawancara."
)


def test_it_catches_the_output_it_was_built_for():
    found = find_k4_violations(REAL_VIOLATION)
    assert {"rmssd", "sdnn", "pnn50", "hrv", "baseline"} <= set(found)


def test_it_passes_the_output_that_was_fine():
    assert find_k4_violations(REAL_CLEAN) == []


# --------------------------------------------------- what it must not flag
def test_a_breathing_instruction_keeps_its_numbers():
    # "Hold for ten seconds" is good advice. A guard that forbade it would be
    # turned off within a week, and then it guards nothing.
    text = ("Coba tarik napas perlahan selama 10 detik, lalu hembuskan dalam 4 "
            "hitungan sebelum menjawab pertanyaan berikutnya.")
    assert find_k4_violations(text) == []


def test_the_plain_indonesian_for_heart_rate_is_allowed():
    # "detak jantung" is precisely what the model SHOULD write instead of "HR"
    # or "bpm", so flagging it would push the output the wrong way.
    assert find_k4_violations("Detak jantungmu naik saat pertanyaan itu.") == []


def test_ordinary_words_containing_a_feature_abbreviation_are_safe():
    # "lf" sits inside "sendiri" only if the matcher forgets word boundaries; the
    # same trap exists for "hf", "ibi" and "prv" across ordinary Indonesian.
    for text in ("Kamu bisa mengatur napas sendiri.",
                 "Hasilnya berbeda dari sebelumnya.",
                 "Ambil jeda sebentar sebelum menjawab."):
        assert find_k4_violations(text) == [], text


# ------------------------------------------------------- what it must flag
def test_a_measured_value_with_its_unit_is_caught():
    assert "24%" in find_k4_violations("Ketegangan naik 24% dibanding biasanya.")
    assert "31,7 ms" in find_k4_violations("Nilainya 31,7 ms saat itu.")
    assert "88 bpm" in find_k4_violations("Jantungmu 88 bpm sepanjang jawaban.")


def test_physiology_vocabulary_is_caught_in_all_its_indonesian_forms():
    # Prefix matching, because Indonesian keeps producing variants of one root and
    # a fixed word list would have to chase them forever.
    assert find_k4_violations("aktivitas parasimpatis menurun")
    assert find_k4_violations("aktivitas parasimpatik menurun")
    assert find_k4_violations("tonus vagal berkurang")
    assert find_k4_violations("sistem saraf otonom terpengaruh")


# ------------------------------------------------- how it reaches the result
def _assessment(**over) -> Assessment:
    response = LLMResponse(
        stress_level=StressLevel.HIGH, confidence=0.8, reasoning="RMSSD fell 24%.",
        references=["KB-RMSSD-01"], uncertainty_notes="PPG lowers confidence.",
        user_summary="Tubuhmu tegang saat menjawab.",
        user_recommendation="Tarik napas perlahan.",
    )
    base = dict(
        session_id="S2", segment_index=1, modality="ECG", phase="question",
        kb_version="kb_v2.0", prompt_version="v1", model="m", temperature=0.0,
        retrieved_ids=["KB-RMSSD-01"], retrieval_scores=[0.9], response=response,
    )
    base.update(over)
    return Assessment(**base)


def test_a_k4_violation_does_not_change_what_trustworthy_means():
    # `is_trustworthy` already appears in API responses and feeds T5.6, where it
    # means one thing: nothing was fabricated. A K4 violation is the opposite
    # fault — all true, still undisplayable — so folding them together would
    # silently rewrite every figure reported so far.
    a = _assessment(k4_violations=["rmssd", "24%"])
    assert a.is_trustworthy is True
    assert a.is_user_safe is False


def test_a_fabrication_is_still_untrustworthy_and_separately_reported():
    a = _assessment(invented_numbers=["47"])
    assert a.is_trustworthy is False
    assert a.is_user_safe is True


def test_a_clean_assessment_passes_both():
    a = _assessment()
    assert a.is_trustworthy and a.is_user_safe


def _pipeline_with(summary: str, recommendation: str, reasoning: str,
                   monkeypatch):
    """Run one assessment through the real pipeline with a scripted response."""
    from hrv_rag.core.schemas import AssessmentInput, SignalQuality
    from hrv_rag.core.types import Modality, Phase
    from hrv_rag.rag import pipeline as mod

    class FakeIndex:
        kb_version = "kb_v2.0"

        def search(self, query):
            return []

    class FakeInterpreter:
        cfg = None
        model_label = "fake"

        def interpret(self, prompt, temperature=None):
            return LLMResponse(
                stress_level=StressLevel.HIGH, confidence=0.8, reasoning=reasoning,
                references=[], uncertainty_notes="LF/HF unstable at 60 s.",
                user_summary=summary, user_recommendation=recommendation,
            )

    # The prompt has to carry the values the scripted response quotes, or the
    # invented-number guard fires on a fixture problem rather than on the
    # behaviour under test — which is exactly what happened when this said "p".
    monkeypatch.setattr(mod, "build_query", lambda data: "q")
    monkeypatch.setattr(
        mod, "build_prompt",
        lambda data, chunks, version: "RMSSD 24% below baseline over 60 s",
    )

    pipe = mod.AssessmentPipeline(index=FakeIndex(), interpreter=FakeInterpreter())
    return pipe.assess(AssessmentInput(
        session_id="S2", modality=Modality.ECG, device="d", phase=Phase.QUESTION,
        segment_index=1, features={}, reactivity={},
        signal_quality=SignalQuality(outlier_pct=1.0, is_acceptable=True),
    ))


def test_the_pipeline_actually_runs_the_guard(monkeypatch):
    # The counterpart to the test below, and the one that was missing. Without it,
    # deleting the guard call from `AssessmentPipeline.assess` broke nothing: every
    # remaining test expected an empty list, which is also what a disabled guard
    # returns. A test that cannot tell "clean" from "not checked" checks nothing.
    result = _pipeline_with(
        summary="HRV turun, RMSSD berkurang 24% dari baseline.",
        recommendation="Tarik napas perlahan.",
        reasoning="RMSSD fell 24%.", monkeypatch=monkeypatch,
    )
    assert {"hrv", "rmssd", "baseline", "24%"} <= set(result.k4_violations)
    assert result.is_user_safe is False
    # And it is still trustworthy: nothing was invented, only disclosed.
    assert result.is_trustworthy is True


def test_the_pipeline_checks_only_the_two_fields_a_user_reads(monkeypatch):
    # `reasoning` here is stuffed with feature names, which is CORRECT — it is
    # English, it is for the developer, and the prompt asks for it. Checking it
    # would report correct behaviour as a violation.
    from hrv_rag.core.schemas import AssessmentInput, SignalQuality
    from hrv_rag.core.types import Modality, Phase
    from hrv_rag.rag import pipeline as mod

    class FakeIndex:
        kb_version = "kb_v2.0"

        def search(self, query):
            return []

    class FakeInterpreter:
        cfg = None
        model_label = "fake"

        def interpret(self, prompt, temperature=None):
            return LLMResponse(
                stress_level=StressLevel.HIGH, confidence=0.8,
                reasoning="RMSSD 31.7 ms, SDNN and pNN50 both fell against baseline.",
                references=[], uncertainty_notes="LF/HF unstable at 60 s.",
                user_summary="Tubuhmu menunjukkan ketegangan.",
                user_recommendation="Tarik napas perlahan sebelum menjawab.",
            )

    monkeypatch.setattr(mod, "build_query", lambda data: "q")
    monkeypatch.setattr(mod, "build_prompt", lambda data, chunks, version: "p")

    pipe = mod.AssessmentPipeline(index=FakeIndex(), interpreter=FakeInterpreter())
    result = pipe.assess(AssessmentInput(
        session_id="S2", modality=Modality.ECG, device="d", phase=Phase.QUESTION,
        segment_index=1, features={}, reactivity={},
        signal_quality=SignalQuality(outlier_pct=1.0, is_acceptable=True),
    ))
    assert result.k4_violations == [], result.k4_violations
    assert result.is_user_safe
