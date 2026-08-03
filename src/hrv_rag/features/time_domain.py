"""
time_domain.py — Time-domain HRV features.

Every function here is pure: arrays in, numbers out, no state retained. That shape
is the easiest to test (BACKLOG U1), because results can be checked against values
computed by hand.

Per the knowledge base, time-domain features — RMSSD above all — are far more
dependable than frequency-domain features on 60-second segments. The features in
this file are therefore the ones given priority during interpretation.
"""

from __future__ import annotations

import numpy as np

#: Names of the features produced by this module, in order.
TIME_FEATURES = ("mean_rr", "mean_hr", "sdnn", "rmssd", "pnn50")


def mean_rr(rr_ms: np.ndarray) -> float:
    """
    Mean RR interval (ms).

    A smaller value means the heart is beating faster — an indication of arousal.
    """
    return float(np.mean(rr_ms))


def mean_hr(rr_ms: np.ndarray) -> float:
    """
    Mean heart rate (bpm).

    Derived from meanRR rather than by averaging instantaneous rates. This matters:
    60000/mean(RR) is NOT the same as mean(60000/RR), because division is
    non-linear. The HRV literature uses the former.
    """
    return 60000.0 / mean_rr(rr_ms)


def sdnn(rr_ms: np.ndarray) -> float:
    """
    Standard deviation of all RR intervals (ms) — total variability.

    Uses ddof=1 (an n-1 denominator) because a segment is a SAMPLE of a longer
    process, not an entire population. Over 60 seconds with ~70 beats the
    difference is small, but the choice must be consistent and defensible.

    SDNN is influenced by both sympathetic and parasympathetic activity, and tends
    to fall under pressure.
    """
    return float(np.std(rr_ms, ddof=1))


def rmssd(rr_ms: np.ndarray) -> float:
    """
    Root mean square of successive differences (ms).

    Because it is built from differences between NEIGHBOURING beats, RMSSD captures
    fast change — which means vagal influence, since the vagus acts far more quickly
    than the sympathetic branch. That is why RMSSD stays reliable in short
    recordings, and why it is this system's primary feature.

    RMSSD decreases as pressure rises.
    """
    diff = np.diff(rr_ms)
    return float(np.sqrt(np.mean(diff ** 2)))


def pnn50(rr_ms: np.ndarray) -> float:
    """
    Percentage of consecutive RR pairs differing by more than 50 ms.

    Like RMSSD it reflects vagal activity, but as a count rather than a magnitude.
    That makes it coarser: in people with low HRV it can bottom out at 0% and stop
    discriminating at all (a floor effect). It is therefore reported alongside
    RMSSD, never as a substitute for it.
    """
    diff = np.abs(np.diff(rr_ms))
    return float(np.mean(diff > 50.0) * 100.0)


def time_domain_features(rr_ms: np.ndarray) -> dict[str, float]:
    """Compute every time-domain feature for one segment."""
    return {
        "mean_rr": mean_rr(rr_ms),
        "mean_hr": mean_hr(rr_ms),
        "sdnn": sdnn(rr_ms),
        "rmssd": rmssd(rr_ms),
        "pnn50": pnn50(rr_ms),
    }
