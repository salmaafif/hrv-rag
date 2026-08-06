"""
Tests for the dataset loaders.

These skip themselves when WESAD is not on the machine, because the raw data is
not committed. What they cover is the contract mismatch that made the loader
dangerous rather than anything about the signal itself.
"""

import pytest

from hrv_rag.core.types import Modality, Phase
from hrv_rag.datasets.wesad import WESADLoader


@pytest.fixture
def loader():
    """A loader for S2, or a skip when the dataset is not installed here."""
    try:
        return WESADLoader("S2")
    except FileNotFoundError:
        pytest.skip("WESAD not available on this machine")


def test_asking_for_another_subject_raises(loader):
    """
    `BaseDatasetLoader` is written per DATASET, so every call takes a `subject`,
    but WESAD ships one file per person and this loader is bound to one of them.

    The argument used to be accepted and ignored: asking an S2 loader for S6
    returned S2's recording under S6's name, silently. A loop over subjects that
    forgot to build a fresh loader would analyse one person fifteen times and
    report it as fifteen — a failure that survives every downstream check, since
    the numbers are all perfectly valid, just all from the same person.
    """
    with pytest.raises(ValueError, match="S2"):
        loader.load_phase_signal("S6", Phase.CALIBRATION, Modality.ECG)

    with pytest.raises(ValueError, match="S2"):
        loader.load_phase_accelerometer("S6", Phase.CALIBRATION, target_fs=64)


def test_its_own_subject_is_served(loader):
    signal = loader.load_phase_signal("S2", Phase.CALIBRATION, Modality.ECG)
    assert signal.size > 0


def test_unmapped_phase_is_refused(loader):
    """WESAD has no briefing phase, and inventing one would silently mislabel."""
    with pytest.raises(ValueError):
        loader.load_phase_signal("S2", Phase.BRIEFING, Modality.ECG)
