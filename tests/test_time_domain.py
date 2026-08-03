"""
U1.1 — Time-domain features checked against hand computation.

Primary test series: RR = [800, 810, 790, 800] ms.

Worked by hand:
    meanRR      = (800+810+790+800)/4 = 800 ms
    meanHR      = 60000/800 = 75 bpm
    differences = [+10, -20, +10]
    RMSSD       = sqrt((100+400+100)/3) = sqrt(200) = 14.1421 ms
    SDNN        = sqrt((0+100+100+0)/3) = sqrt(66.667) = 8.1650 ms   (ddof=1)
    pNN50       = no difference exceeds 50 ms -> 0%
"""

import numpy as np
import pytest

from hrv_rag.features.time_domain import (mean_hr, mean_rr, pnn50, rmssd,
                                          sdnn, time_domain_features)

RR = np.array([800.0, 810.0, 790.0, 800.0])


def test_mean_rr():
    assert mean_rr(RR) == pytest.approx(800.0)


def test_mean_hr():
    """meanHR must be 60000/meanRR, not the average of instantaneous rates."""
    assert mean_hr(RR) == pytest.approx(75.0)


def test_rmssd():
    assert rmssd(RR) == pytest.approx(np.sqrt(200.0), rel=1e-9)


def test_sdnn_uses_ddof_1():
    """
    SDNN uses an n-1 denominator, not n.

    If ddof were ever changed to 0 the value would become sqrt(50)=7.071 and this
    test would fail — which is the point: it locks in a decision already made.
    """
    assert sdnn(RR) == pytest.approx(np.sqrt(200.0 / 3.0), rel=1e-9)
    assert sdnn(RR) != pytest.approx(np.sqrt(50.0))


def test_pnn50_zero_when_differences_small():
    assert pnn50(RR) == pytest.approx(0.0)


def test_pnn50_hundred_when_all_differences_large():
    """RR = [800, 900, 800] -> differences [100, 100], both above 50 ms."""
    assert pnn50(np.array([800.0, 900.0, 800.0])) == pytest.approx(100.0)


def test_pnn50_exactly_50_not_counted():
    """
    The threshold is "more than 50 ms", so a difference of exactly 50 ms is NOT
    counted. A small detail, but it must stay consistent for results to reproduce.
    """
    assert pnn50(np.array([800.0, 850.0, 800.0])) == pytest.approx(0.0)


def test_rmssd_order_sensitive_sdnn_not():
    """
    The fundamental difference between these two features.

    SDNN only looks at the spread of values, so shuffling the order leaves it
    unchanged. RMSSD looks at differences between CONSECUTIVE beats, so order
    matters completely. This is why RMSSD reflects fast (vagal) change.
    """
    shuffled = np.array([790.0, 800.0, 800.0, 810.0])
    assert sdnn(shuffled) == pytest.approx(sdnn(RR))
    assert rmssd(shuffled) != pytest.approx(rmssd(RR))


def test_all_features_present_and_finite():
    result = time_domain_features(RR)
    assert set(result) == {"mean_rr", "mean_hr", "sdnn", "rmssd", "pnn50"}
    assert all(np.isfinite(v) for v in result.values())
