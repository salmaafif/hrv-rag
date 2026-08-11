"""
hrv_dl — the deep-learning comparator, kept deliberately OUTSIDE the system.

WHY THIS PACKAGE EXISTS, AND WHY IT IS NOT `hrv_rag`

CLAUDE.md states that the system assesses stress "tanpa melatih model machine
learning". That rule is not being broken here, and the distinction has to survive
being questioned at the viva:

    The SYSTEM trains nothing. A deep-learning model is trained HERE, outside the
    system package, for one purpose only — to be the thing the system is measured
    against.

That is why `hrv_rag` stays free of PyTorch, why the training dependencies live in
their own `requirements-dl.txt`, and why nothing in `hrv_rag` ever imports from
this package. The arrow points one way: `hrv_dl` reads from `hrv_rag`, never the
reverse. Anyone installing the system to run it gets no training code at all.

WHAT MAKES THE COMPARISON WORTH ANYTHING

Only one thing: both sides must face the identical sealed test set, cut into
identical segments, filtered by identical quality gates. That identity is a
property of the code, not of good intentions — which is exactly why this package
IMPORTS `settings.split`, `ECGPreprocessor` and `segment_rr_series` rather than
reimplementing them. A copied list of ten subject IDs can drift apart silently,
and if it drifts, neither number means anything any more and nothing says so.

This also settles the question the thesis has so far answered only by argument:
why RAG instead of the four deep-learning architectures originally planned
(BACKLOG D3.4). With a comparator run under the same conditions, that becomes a
measurement.
"""
