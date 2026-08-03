"""
wesad.py — WESAD dataset loader.

WESAD's role in this thesis (CLAUDE.md): the primary anchor. TSST is the
social-evaluative stressor closest to a real job interview, and WESAD is the only
dataset providing ECG and PPG from THE SAME SUBJECTS — the basis for the paired
modality comparison (ICC, Bland-Altman) in Stage 6.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from ..config.settings import DATA_RAW, WESAD_FALLBACK
from ..core.types import Modality, Phase
from .base import BaseDatasetLoader


class WESADLoader(BaseDatasetLoader):
    """
    Loader for a single WESAD subject.

    Label -> phase mapping:
        label 1 (baseline)  -> Phase.CALIBRATION  -> becomes the personal baseline
        label 2 (TSST)      -> Phase.QUESTION     -> the stressed condition
        label 3 (amusement) -> EXCLUDED

    Amusement is excluded because it is POSITIVE arousal, not pressure. Including
    it would mix two different things into one scale and rob the "high" label of
    meaning. (Decision K7: not used at all, not even as a negative control.)
    """

    name = "WESAD"

    # Raw label codes inside the .pkl file
    _LABEL_BASELINE = 1
    _LABEL_STRESS = 2

    _PHASE_TO_LABEL = {
        Phase.CALIBRATION: _LABEL_BASELINE,
        Phase.QUESTION: _LABEL_STRESS,
    }

    # Sampling rates per the WESAD specification.
    _FS = {
        Modality.ECG: 700,   # RespiBAN, chest strap
        Modality.PPG: 64,    # Empatica E4, wrist (BVP channel)
    }

    _SIGNAL_KEY = {
        Modality.ECG: ("chest", "ECG"),
        Modality.PPG: ("wrist", "BVP"),
    }

    def __init__(self, subject: str) -> None:
        self.subject = subject
        self._path = self._locate(subject)
        self._data: dict | None = None       # loaded lazily

    # ------------------------------------------------------------ location
    @staticmethod
    def _locate(subject: str) -> Path:
        """
        Find the SX.pkl file. Tries data/raw inside the repo first, then falls back
        to the copy in Documents/WESAD.
        """
        candidates = [
            DATA_RAW / "wesad" / subject / f"{subject}.pkl",
            DATA_RAW / "wesad" / f"{subject}.pkl",
            WESAD_FALLBACK / subject / f"{subject}.pkl",
        ]
        for path in candidates:
            if path.exists():
                return path
        raise FileNotFoundError(
            f"{subject}.pkl not found. Looked in:\n  "
            + "\n  ".join(str(c) for c in candidates)
        )

    # ---------------------------------------------------------------- load
    @property
    def data(self) -> dict:
        """
        Contents of the .pkl file, loaded once and cached (lazy loading).

        A single WESAD file is hundreds of megabytes, so it must not be re-read
        every time a signal is requested.

        encoding='latin1' is MANDATORY: the file was pickled under Python 2.
        """
        if self._data is None:
            with open(self._path, "rb") as f:
                self._data = pickle.load(f, encoding="latin1")
        return self._data

    # -------------------------------------------------------- base contract
    @property
    def subjects(self) -> tuple[str, ...]:
        """All WESAD subjects. Note that S1 and S12 genuinely do not exist."""
        return tuple(f"S{i}" for i in range(2, 18) if i != 12)

    @property
    def available_modalities(self) -> tuple[Modality, ...]:
        return (Modality.ECG, Modality.PPG)

    def sampling_rate(self, modality: Modality) -> int:
        return self._FS[modality]

    def load_phase_signal(self, subject: str, phase: Phase,
                          modality: Modality) -> np.ndarray:
        """
        Extract one phase's signal as a 1-D array.

        Important note about PPG: the label array follows the chest sampling rate
        (700 Hz), whereas BVP is recorded at 64 Hz. Label indices must therefore be
        RESCALED to the BVP rate — without that, the extracted slice lands in
        completely the wrong place.
        """
        if phase not in self._PHASE_TO_LABEL:
            raise ValueError(
                f"WESAD does not provide phase {phase.value}. "
                f"Available: {[p.value for p in self._PHASE_TO_LABEL]}"
            )

        group, key = self._SIGNAL_KEY[modality]
        signal = np.asarray(self.data["signal"][group][key]).reshape(-1)
        labels = np.asarray(self.data["label"]).reshape(-1)

        # Longest contiguous run, computed at the label rate (700 Hz).
        mask = labels == self._PHASE_TO_LABEL[phase]
        start, end = self.longest_contiguous_run(mask)

        # Rescale to the requested signal's sampling rate.
        scale = signal.size / labels.size
        start = int(round(start * scale))
        end = int(round(end * scale))

        return signal[start:end]
