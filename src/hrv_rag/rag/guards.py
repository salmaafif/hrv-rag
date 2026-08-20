"""
guards.py — Automated checks that the LLM stayed inside its remit (T4.5, T4.6).

Mandatory Rule #1 says the code computes the numbers and the LLM only interprets
them. Instructing the model to obey that is necessary but not sufficient: an
instruction is a request, not a guarantee. These guards verify the output after the
fact, so a violation is detected rather than trusted away.

Two things are checked:

1. **Invented numbers.** Every numeric value in the model's reasoning must already
   appear somewhere in the prompt — either among the supplied measurements or
   inside a retrieved knowledge chunk. A number that appears from nowhere is the
   model calculating, which is exactly what must never happen.

2. **Unknown citations.** Every ID in `references` must be one of the chunks
   actually retrieved. Citing a chunk that was never supplied is a fabricated
   citation, and it would silently corrupt the faithfulness metric (T5.6).

3. **Citations invented in prose.** The same rule applied to chunk IDs the model
   writes into its sentences rather than into the `references` field. A reader
   cannot tell the two apart, so neither should the check.

What these guards check is only as strong as WHICH TEXT is handed to them. Every
field the user will read has to be included — see `AssessmentPipeline.assess`.
"""

from __future__ import annotations

import re

#: Hyphen-like characters a model may write instead of an ASCII "-".
#:
#: Found in the wild: gpt-oss cited "KB‑PNN50‑ 01" — a NON-BREAKING HYPHEN,
#: which looks identical on screen. Every one of those citations was correct, and
#: every one was reported as fabricated, because the comparison is string equality
#: and the strings genuinely differ. The guard was accusing the model of inventing
#: chunks it had actually been given.
_HYPHENS = str.maketrans({"‐": "-", "‑": "-", "‒": "-",
                          "–": "-", "—": "-", "−": "-"})


#: Matches integers and decimals, with an optional sign.
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")

#: Stable chunk identifiers, e.g. KB-RMSSD-01. Used both to strip them out of the
#: prompt's number pool and to spot fabricated ones inside prose.
_CHUNK_ID = re.compile(r"\bKB[\-\u2010-\u2015\u2212][A-Z0-9]+[\-\u2010-\u2015\u2212]\d+\b", re.I)

#: The provenance line `format_context` writes above every chunk:
#: "(relevance 0.807; sources: Task Force 1996; Shaffer 2017)".
_CHUNK_PROVENANCE = re.compile(r"\(relevance\s+[^)]*\)")

#: A comma sitting between digits, as Indonesian writes decimals ("0,85").
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d{1,2}\b)")
#: A comma used as an English thousands separator ("1,234").
_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}\b)")


def _normalise(text: str) -> str:
    """
    Put numbers into one written form before comparing them.

    The user-facing half of every response is Indonesian, where the decimal
    separator is a comma. Left alone, "0,85" is read as the two separate numbers 0
    and 85 — and 85 will almost certainly look invented, so a perfectly faithful
    sentence gets reported as a violation. Since the guard decides whether an output
    is trustworthy, a false alarm here is not harmless.
    """
    text = _THOUSANDS_COMMA.sub("", text)
    return _DECIMAL_COMMA.sub(".", text)


def _extract_numbers(text: str) -> list[str]:
    return _NUMBER.findall(_normalise(text))


def _prompt_numbers(prompt_text: str) -> list[float]:
    """
    The numbers a response is allowed to quote: measurements and knowledge only.

    Bookkeeping is stripped first, because it is not knowledge and letting it widen
    the pool is what made this check nearly toothless. Three sources polluted it:

    - Chunk IDs. "KB-RMSSD-01" contributed the value 1.
    - Retrieval scores. "relevance 0.807" contributed a number in the 0-1 range,
      exactly where invented probabilities and ratios live.
    - Citation years. 1996 and 2017 each permitted anything within 2% — a window
      roughly 40 wide — so most four-digit inventions traced back to a reference.

    Measured against a real prompt, the unstripped pool accepted 53% of all values
    between 0 and 10 and half of all four-digit numbers. Sentences like "the stress
    index is 4" and "cortisol rose 2 fold" passed clean.
    """
    cleaned = _CHUNK_PROVENANCE.sub(" ", prompt_text)
    cleaned = _CHUNK_ID.sub(" ", cleaned)
    return [abs(float(n)) for n in _extract_numbers(cleaned)]


def _rounding_tolerance(token: str, whole_number_tol: float) -> float:
    """
    How far a quoted number may sit from its source and still be a rounding of it.

    The allowance is set by the precision the MODEL chose to write, not by a single
    constant. "44" could be any value from 43.5 to 44.5, so it earns +/-0.5. "0.72"
    claims precision to the hundredth, so it only earns +/-0.005 — and a model that
    states a figure that precisely is asserting it, not rounding it.

    A fixed +/-0.5 for everything was what made this check nearly decorative. Half a
    unit is enormous next to an LF/HF ratio or a probability, so with a couple of
    dozen numbers in the prompt roughly half of every value between 0 and 10 traced
    back to something by coincidence. Scaling with the written precision drops that
    to 9% while every genuine rounding in the measurements still passes.
    """
    _, _, decimals = token.partition(".")
    return whole_number_tol * (10.0 ** -len(decimals))


def find_invented_numbers(response_text: str, prompt_text: str,
                          whole_number_tol: float = 0.5, rel_tol: float = 0.02
                          ) -> list[str]:
    """
    Return any number in the response that does not trace back to the prompt.

    Tolerances exist because sensible rounding is not fabrication: a model that
    reports "35%" when the input said "-35.2%" is quoting, not inventing. A value
    counts as traceable when it sits within a rounding of some prompt number — see
    `_rounding_tolerance` — or within `rel_tol` of it, which covers a large figure
    being reported to fewer significant digits.

    Signs are ignored on purpose. "RMSSD fell 35%" and "-35%" describe the same
    measurement, and the direction is already carried by the surrounding words.
    """
    allowed = _prompt_numbers(prompt_text)
    if not allowed:
        return _extract_numbers(response_text)

    invented: list[str] = []
    for token in _extract_numbers(response_text):
        value = abs(float(token))
        tol = _rounding_tolerance(token, whole_number_tol)
        traceable = any(
            abs(value - a) <= max(tol, abs(a) * rel_tol) for a in allowed
        )
        if not traceable:
            invented.append(token)
    return invented


def find_unknown_references(cited: list[str], retrieved_ids: list[str]) -> list[str]:
    """
    Return cited chunk IDs that were never actually retrieved.

    A non-empty result means the model produced a citation for knowledge it was
    never given — the citation equivalent of an invented number.

    Both sides are normalised before comparison. A raw set membership test rejected
    "kb-rmssd-01", "KB-RMSSD-01 " and "KB-RMSSD-01 (RMSSD basics)" as fabrications
    even though every one of them names a chunk that really was supplied, and a
    single string holding two comma-separated IDs failed as one unrecognised blob.
    Punishing formatting as dishonesty inflates the faithfulness violation count and
    marks sound assessments untrustworthy.
    """
    available = {_canonical_id(r) for r in retrieved_ids}

    unknown: list[str] = []
    for ref in cited:
        ids = _CHUNK_ID.findall(ref)
        # Nothing that even looks like an ID: report the raw string as given.
        candidates = ids or [ref]
        for candidate in candidates:
            if _canonical_id(candidate) not in available:
                unknown.append(candidate)
    return unknown


def _canonical_id(raw: str) -> str:
    """
    One spelling for a chunk ID, so formatting is never read as dishonesty.

    Whitespace inside is collapsed as well as trimmed: "KB-PNN50- 01" names a real
    chunk, and a model that puts a stray space in an identifier has not invented
    anything. The failure being hunted is a citation to knowledge that was never
    supplied — not a typographic slip.
    """
    return re.sub(r"\s+", "", raw.translate(_HYPHENS)).upper()


def find_fabricated_citations(response_text: str,
                              retrieved_ids: list[str]) -> list[str]:
    """
    Return chunk IDs invoked in PROSE that were never retrieved.

    `find_unknown_references` only inspects the structured `references` field, so a
    model that writes "Per KB-CORTISOL-01, cortisol rises under stress" in its
    reasoning cites a chunk that does not exist anywhere in the knowledge base and
    nothing notices. To a reader that sentence carries exactly the authority a real
    citation would, which makes it the more damaging of the two failures.
    """
    available = {_canonical_id(r) for r in retrieved_ids}
    seen: set[str] = set()
    fabricated: list[str] = []
    for match in _CHUNK_ID.findall(response_text):
        canonical = _canonical_id(match)
        if canonical not in available and canonical not in seen:
            seen.add(canonical)
            fabricated.append(match)
    return fabricated


# ===========================================================================
# K4 — what the user is allowed to read
# ===========================================================================
#
# WHY THIS GUARD EXISTS, AND WHY IT DID NOT UNTIL NOW.
#
# The two guards above catch a model INVENTING something. This one catches a
# model DISCLOSING something — and the difference is why it was missed. Asked to
# narrate one segment, `deepseek-r1:latest` wrote, into the field a KARIRLINK user
# reads: "HRV menunjukkan penurunan signifikan ... dengan RMSSD, SDNN, dan pNN50
# semuanya berkurang terhadap baseline sendiri." Every number in it was real, every
# citation was real, and both existing guards reported zero violations. They were
# right: nothing was fabricated. The output was still unusable.
#
# The gap stayed invisible while Gemini was the only backend, because Gemini
# happened to obey the instruction. An instruction is a request; a second model
# declined it, and there was nothing underneath to catch that.
#
# SCOPE: user-facing fields ONLY. `reasoning` and `uncertainty_notes` are English,
# are meant for the developer, and are SUPPOSED to name features — running this
# over them would flag correct behaviour.

#: Measurement vocabulary that must never reach the user. Written as whole words
#: so "HF" does not fire inside an unrelated Indonesian word.
_FEATURE_TERMS = (
    "rmssd", "sdnn", "pnn50", "nn50", "lf/hf", "lfhf", "hrv", "prv",
    "meanrr", "mean rr", "rr-interval", "rr interval", "ibi", "bpm",
)

#: Physiology the user is not being taught. "detak jantung" is deliberately absent
#: — it is the plain Indonesian phrase and exactly what SHOULD be used instead.
_CLINICAL_TERMS = (
    "parasimpat", "simpatik", "simpatis", "vagal", "otonom",
    "variabilitas", "baseline", "interval", "segmen", "amplitudo",
)

#: A value with a unit attached: "24%", "31,7 ms", "88 bpm".
#:
#: Bare digits are NOT matched, and that is deliberate. "Tarik napas selama empat
#: hitungan" and "jeda 10 detik" are good advice, and a guard that forbade them
#: would be switched off within a week — at which point it protects nothing.
_MEASURED_VALUE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|persen|ms|milidetik|bpm|denyut/menit)", re.I
)

#: Whole-word matcher built once per term, so "lf" cannot fire inside "sendiri".
_TERM_PATTERNS = tuple(
    (term, re.compile(rf"(?<![a-z]){re.escape(term)}", re.I))
    for term in _FEATURE_TERMS + _CLINICAL_TERMS
)


def find_k4_violations(user_text: str) -> list[str]:
    """
    Technical language that reached the text a user reads (decision K4).

    Returns what was found, not a count, because the point is to be able to look
    at it: a guard that says "3 violations" sends you hunting, while one that says
    `['rmssd', 'sdnn', '24%']` has already answered the question.

    Prefix matching on the clinical terms is intentional — "parasimpat" catches
    both "parasimpatik" and "parasimpatis", and Indonesian will keep producing
    variants of the same root that a word list would have to chase forever.
    """
    found: list[str] = []
    for term, pattern in _TERM_PATTERNS:
        if pattern.search(user_text):
            found.append(term)
    found.extend(m.group(0).strip() for m in _MEASURED_VALUE.finditer(user_text))
    return found
