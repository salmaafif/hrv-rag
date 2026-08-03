"""
base.py — Shared contract for every dataset loader.

Why an abstract class here? Because this project uses three datasets whose file
layouts and label structures differ completely, while everything downstream
(preprocessing, features, RAG) must treat all three uniformly.

With this contract, adding SWELL-KW or UBFC-Phys later means writing one new
subclass and touching NONE of the code that already works.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..core.types import Modality, Phase


class BaseDatasetLoader(ABC):
    """
    Standard interface for dataset loaders.

    Subclasses must answer three questions:
      1. Which subjects exist?                    -> subjects
      2. Which modalities are available?          -> available_modalities
      3. How is one phase's signal extracted?     -> load_phase_signal
    """

    #: Dataset name, used for naming output files and for reporting metrics per
    #: dataset (CLAUDE.md forbids pooling results across datasets).
    name: str = "base"

    # ------------------------------------------------------------- required
    @property
    @abstractmethod
    def subjects(self) -> tuple[str, ...]:
        """List of available subject IDs."""

    @property
    @abstractmethod
    def available_modalities(self) -> tuple[Modality, ...]:
        """Modalities this dataset provides."""

    @abstractmethod
    def sampling_rate(self, modality: Modality) -> int:
        """Sampling rate in Hz for the given modality."""

    @abstractmethod
    def load_phase_signal(self, subject: str, phase: Phase,
                          modality: Modality) -> np.ndarray:
        """
        Extract the raw signal for one phase of one subject.

        Subclasses are responsible for mapping dataset labels onto `Phase`.
        """

    # -------------------------------------------------------------- shared
    @staticmethod
    def longest_contiguous_run(mask: np.ndarray) -> tuple[int, int]:
        """
        Find the longest unbroken run of True values in `mask`.

        Why this is needed: extracting with plain `signal[mask]` would splice
        together stretches of time that were never adjacent. The splice point
        creates an abrupt step that peak detection reads as a spurious R peak,
        which then shows up as a bogus RR interval. Taking a single contiguous run
        avoids that entirely.

        Returns: (start_index, end_index) with the end exclusive.
        """
        if not mask.any():
            raise ValueError("Empty mask — the requested phase does not exist.")

        # Differencing the mask as integers marks rising (+1) and falling (-1) edges.
        edges = np.diff(mask.astype(np.int8))
        starts = np.flatnonzero(edges == 1) + 1
        ends = np.flatnonzero(edges == -1) + 1

        if mask[0]:                       # already True at the first sample
            starts = np.r_[0, starts]
        if mask[-1]:                      # still True at the last sample
            ends = np.r_[ends, mask.size]

        longest = int(np.argmax(ends - starts))
        return int(starts[longest]), int(ends[longest])
