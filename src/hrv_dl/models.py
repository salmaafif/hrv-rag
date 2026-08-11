"""
models.py — the 1D-CNN comparator, built to the proposal's Tabel 3.3.

WHY THIS ARCHITECTURE AND NOT THE OTHER THREE

The proposal compares four. Only one is run, and the choice is not a shortcut:

- **Capacity against data.** WESAD yields roughly 854 labelled segments. Counted
  from the proposal's own hyperparameters, the Transformer carries about 540k
  parameters, BiLSTM about 141k, CNN-LSTM about 81k, and this network about 80k.
  Half a million parameters over 854 examples does not lose narrowly; it memorises
  the training set outright. Self-attention also has little to work with on
  sequences of 60-141 steps.

- **A failure that can be interpreted.** Had the heaviest model been chosen and
  lost to the scoring rule, "your dataset was too small" would answer it. Choosing
  the architecture with the healthiest capacity-to-data ratio means a loss says
  something about the DATA rather than about an under-powered model.

- **Kernel 7 means something physiological.** At 75 bpm with a resting breathing
  rate of 12-15 per minute, one respiratory cycle spans 5-6 beats. A kernel of 7
  therefore covers roughly one full breath — and respiratory sinus arrhythmia is
  the beat-to-beat structure that carries the vagal signal, the very thing RMSSD
  and HF measure. After pooling, the second block sees about 2.5 cycles and the
  third about 5. The receptive field grows along the same hierarchy as the
  physiology. None of the other three admits a justification that concrete.

TWO CLASSES, NOT THREE

The proposal specifies `softmax` over three classes. That is not reachable with
the data actually in hand: WESAD is binary, the SWELL package carries no usable
beat series for a sequence model, and UBFC-Phys is a direction-of-change test
rather than a classification one. Binary is also what the thesis already reports
its scientific claims in, so the two sides stay comparable.
"""

from __future__ import annotations

import torch
from torch import nn

#: Padding value in the input tensors. Real intervals are baseline-normalised and
#: sit near 1.0, so zero is unambiguous — but it is never relied upon: the mask
#: decides what is real, not the value.
PAD_VALUE = 0.0


class CNN1D(nn.Module):
    """
    Three 1D convolution blocks, masked pooling, two dense layers, two classes.

    MASKING IS NOT A DETAIL HERE. Sequences run 60-141 beats and are padded to
    200, so up to 70% of a row can be padding — and how much padding a row carries
    is a direct function of heart rate. Two things follow:

    1. Each convolution has a BIAS, so padded positions do not stay zero after the
       first layer. Left alone they would flow through max-pooling into the
       representation, and the network could read heart rate off the shape of the
       padding rather than off the intervals. The mask is therefore reapplied
       after every block.

    2. The final pooling averages over REAL positions only. A naive mean over all
       200 slots would divide by a constant while the numerator came from a
       variable number of beats — arithmetic that happens to encode heart rate,
       but by accident and in a form nothing downstream could inspect.

    Heart rate is not lost by masking, and that is the point of normalising the
    input by the subject's own resting meanRR: the masked average of the
    normalised series IS mean-RR-relative-to-baseline, which is heart-rate
    reactivity expressed the way Mandatory Rule #2 requires. The model gets the
    strongest available signal through the values themselves rather than through
    an artefact of tensor shape.
    """

    def __init__(self, n_classes: int = 2, dropout: float = 0.3) -> None:
        super().__init__()
        # padding=3 with kernel 7 preserves length, which keeps the mask aligned
        # with the feature map without any index arithmetic.
        self.block1 = nn.Sequential(nn.Conv1d(1, 32, 7, padding=3), nn.ReLU())
        self.block2 = nn.Sequential(nn.Conv1d(32, 64, 7, padding=3), nn.ReLU())
        self.block3 = nn.Sequential(nn.Conv1d(64, 128, 7, padding=3), nn.ReLU())

        # "max pooling dengan stride 2 di antara blok" — between the blocks, so
        # two pools for three blocks. 200 -> 100 -> 50.
        self.pool = nn.MaxPool1d(2)

        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, n_classes),
        )

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """
        `x` and `mask` are both (batch, length). Returns logits (batch, n_classes).
        """
        h = x.unsqueeze(1)                      # (b, 1, L)
        m = mask.unsqueeze(1).float()           # (b, 1, L)

        # Mask the INPUT too, not only the block outputs.
        #
        # This line was missing at first and a test caught it. The leak is not the
        # convolution bias, which was the obvious suspect — it is the kernel
        # reaching ACROSS the boundary. With kernel 7 and padding 3, the output at
        # the last real position reads three padded slots, so whatever sits in the
        # padding enters the representation of a genuine beat. The dataset builder
        # happens to write zeros there, but relying on that would make correctness
        # here depend on a convention two files away.
        h = h * m
        h = self.block1(h) * m
        h, m = self.pool(h), self.pool(m)
        h = self.block2(h) * m
        h, m = self.pool(h), self.pool(m)
        h = self.block3(h) * m

        # Masked global average pooling. The clamp guards a row whose mask has
        # been pooled away entirely; it cannot happen for a segment that passed
        # the 30-beat gate, but dividing by zero silently produces NaNs that then
        # spread through every subsequent batch.
        pooled = h.sum(dim=2) / m.sum(dim=2).clamp(min=1.0)
        return self.head(pooled)

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def make_model(n_classes: int = 2, dropout: float = 0.3,
               seed: int | None = None) -> CNN1D:
    """
    Build the network, optionally with a fixed initialisation.

    The seed is threaded through rather than set globally so that a caller running
    fifteen LOSO folds can give each fold the SAME starting point. Otherwise a
    fold-to-fold difference in the reported score would mix two causes — the
    subject held out, and where the weights happened to start — and there would be
    no way afterwards to say which one moved the number.
    """
    if seed is not None:
        torch.manual_seed(seed)
    return CNN1D(n_classes=n_classes, dropout=dropout)
