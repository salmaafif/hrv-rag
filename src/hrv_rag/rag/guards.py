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
"""

from __future__ import annotations

import re

#: Matches integers and decimals, with an optional sign.
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _extract_numbers(text: str) -> list[str]:
    return _NUMBER.findall(text)


def find_invented_numbers(response_text: str, prompt_text: str,
                          abs_tol: float = 0.5, rel_tol: float = 0.02
                          ) -> list[str]:
    """
    Return any number in the response that does not trace back to the prompt.

    Tolerances exist because sensible rounding is not fabrication: a model that
    reports "35%" when the input said "-35.2%" is quoting, not inventing. A value
    counts as traceable when it is within `abs_tol` in absolute terms or within
    `rel_tol` relatively of some number in the prompt.

    Signs are ignored on purpose. "RMSSD fell 35%" and "-35%" describe the same
    measurement, and the direction is already carried by the surrounding words.
    """
    allowed = [abs(float(n)) for n in _extract_numbers(prompt_text)]
    if not allowed:
        return _extract_numbers(response_text)

    invented: list[str] = []
    for token in _extract_numbers(response_text):
        value = abs(float(token))
        traceable = any(
            abs(value - a) <= max(abs_tol, abs(a) * rel_tol) for a in allowed
        )
        if not traceable:
            invented.append(token)
    return invented


def find_unknown_references(cited: list[str], retrieved_ids: list[str]) -> list[str]:
    """
    Return cited chunk IDs that were never actually retrieved.

    A non-empty result means the model produced a citation for knowledge it was
    never given — the citation equivalent of an invented number.
    """
    available = set(retrieved_ids)
    return [ref for ref in cited if ref not in available]
