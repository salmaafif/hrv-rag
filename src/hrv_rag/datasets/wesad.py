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

    #: Wrist accelerometer, used for motion-artefact rejection on PPG.
    _ACC_KEY = ("wrist", "ACC")
    _ACC_FS = 32

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

    def load_phase_accelerometer(self, subject: str, phase: Phase,
                                 target_fs: int) -> np.ndarray:
        """
        Wrist acceleration for one phase, resampled to `target_fs`.

        WESAD records wrist ACC at 32 Hz but BVP at 64 Hz, so the two do not line up
        sample for sample. Acceleration is therefore stretched onto the BVP time
        grid before it can be used to reject beats — otherwise a movement flagged at
        one index would correspond to a quite different moment in the pulse signal.

        Nearest-neighbour interpolation is used rather than a smooth one. What is
        needed here is "was the wrist moving around this instant", and interpolating
        smoothly between acceleration samples would invent motion values that were
        never measured.
        """
        acc = np.asarray(self.data["signal"][self._ACC_KEY[0]][self._ACC_KEY[1]],
                         dtype=float)
        labels = np.asarray(self.data["label"]).reshape(-1)

        mask = labels == self._PHASE_TO_LABEL[phase]
        start, end = self.longest_contiguous_run(mask)

        scale = acc.shape[0] / labels.size
        acc = acc[int(round(start * scale)):int(round(end * scale))]

        n_target = int(round(acc.shape[0] * target_fs / self._ACC_FS))
        if n_target <= 0 or acc.shape[0] == 0:
            return np.zeros((0, acc.shape[1] if acc.ndim > 1 else 1))

        idx = np.clip((np.arange(n_target) * self._ACC_FS / target_fs)
                      .round().astype(int), 0, acc.shape[0] - 1)
        return acc[idx]
