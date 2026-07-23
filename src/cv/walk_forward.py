# src/cv/walk_forward.py
"""
Purged walk-forward cross-validation with embargo (Phase 2.5).

For supervised learning on financial time series, plain k-fold CV is
catastrophically wrong: it leaks future information into the training
set whenever labels are computed over a forward window (which is
ALWAYS for triple-barrier and most other label schemes).

This module implements the de-facto standard correction from López de
Prado's "Advances in Financial Machine Learning", chapter 7:

  PURGE
    Remove from the training fold every observation whose LABEL window
    overlaps the test fold. For triple-barrier with max_horizon=24, an
    observation at bar t has a label that depends on bars t+1..t+24.
    If the test fold contains any of those bars, observation t leaks
    into the test set unless purged.

  EMBARGO
    After the test fold ends, skip an additional E bars before the next
    training segment begins. This protects against serial correlation
    that survives the purge — e.g., a feature that auto-correlates with
    its own lag-1 value still ties test/train together unless an
    embargo is enforced.

Standard recommendation:
  embargo = max_horizon + 1

This module provides:
  * PurgedWalkForward — an iterator yielding (train_indices, test_indices)
  * The same class accepts an optional ``min_train_size`` so early folds
    don't get a starvation-sized training set.
  * A small fold-quality diagnostic so failures (overlap, leakage) are
    caught at construction time, not silently.

Why this is its own module
--------------------------
The temptation is to use sklearn.TimeSeriesSplit. Don't — it does not
purge or embargo, and the bug is silent. Every CV result it produces
on label-windowed data is biased upward. Using PurgedWalkForward is
the difference between "PF 1.30 in CV, 0.95 live" and "PF 1.10 in CV,
1.05 live". The first is a disaster; the second is a successful
research project.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FoldSpec:
    """Concrete indices for one fold."""
    fold_id:        int
    train_indices:  np.ndarray   # int64, sorted
    test_indices:   np.ndarray   # int64, sorted
    train_size:     int
    test_size:      int
    purged_count:   int          # how many indices were dropped from train
    train_span:     Tuple[int, int]   # (first_train_idx, last_train_idx)
    test_span:      Tuple[int, int]   # (first_test_idx, last_test_idx)

    def assert_no_overlap(self) -> None:
        """Sanity check — train and test must be disjoint by construction."""
        overlap = np.intersect1d(self.train_indices, self.test_indices)
        if overlap.size > 0:
            raise AssertionError(
                f"Fold {self.fold_id} has {overlap.size} overlapping indices "
                f"between train and test — purge logic is broken."
            )


@dataclass(frozen=True)
class WalkForwardSummary:
    """Aggregated stats over all folds — used in PhaseN verifier checks."""
    n_folds:        int
    total_train_obs: int
    total_test_obs:  int
    purged_total:    int
    avg_train_size:  float
    avg_test_size:   float
    embargo:         int
    max_horizon:     int


class PurgedWalkForward:
    """
    Expanding-window walk-forward CV with purge and embargo.

    Splits an n-observation index into ``n_folds`` non-overlapping test
    segments of size ``test_size = n // (n_folds + 1)``, each preceded
    by an expanding training segment. Then:

      * From each training segment, PURGES observations whose label
        window (defined by ``max_horizon``) reaches into the test
        segment.
      * Between the END of each test segment and the START of the next
        training segment, EMBARGOES ``embargo`` bars.

    Parameters
    ----------
    n_folds : number of folds. Common choice: 6.
    max_horizon : the label horizon. For triple-barrier, this is the
                  same value as TripleBarrierConfig.max_horizon. The
                  purge logic requires this to be set correctly — if
                  you understate it, leaks survive.
    embargo : extra bars between test end and next train start.
              Recommend max_horizon + 1.
    min_train_size : skip folds whose training set would be smaller
                     than this. Default 0 (no skipping).

    Examples
    --------
    >>> wf = PurgedWalkForward(n_folds=6, max_horizon=24, embargo=25)
    >>> for fold in wf.split(n_observations=10000):
    ...     X_train, y_train = X[fold.train_indices], y[fold.train_indices]
    ...     X_test,  y_test  = X[fold.test_indices],  y[fold.test_indices]
    ...     model.fit(X_train, y_train)
    ...     preds = model.predict(X_test)
    """

    def __init__(
        self,
        n_folds: int = 6,
        max_horizon: int = 24,
        embargo: Optional[int] = None,
        min_train_size: int = 0,
    ) -> None:
        if n_folds < 2:
            raise ValueError("n_folds must be >= 2")
        if max_horizon < 1:
            raise ValueError("max_horizon must be >= 1")
        if min_train_size < 0:
            raise ValueError("min_train_size must be >= 0")
        self.n_folds = n_folds
        self.max_horizon = max_horizon
        # Default embargo = max_horizon + 1. This is the standard
        # recommendation; explicit override is allowed for advanced use.
        self.embargo = embargo if embargo is not None else max_horizon + 1
        if self.embargo < 0:
            raise ValueError("embargo must be >= 0")
        self.min_train_size = min_train_size

    # ─── Main API ─────────────────────────────────────────────────────────

    def split(self, n_observations: int) -> Iterator[FoldSpec]:
        """
        Yield FoldSpec objects for each fold.

        The test segments tile the latter portion of the index in
        chronological order. The first ``test_start`` is the smallest
        index such that the prior training segment is non-empty.
        """
        if n_observations < self.n_folds * 2:
            raise ValueError(
                f"n_observations={n_observations} too small for "
                f"n_folds={self.n_folds} (need at least {self.n_folds * 2})"
            )

        # Reserve the first slice for training-only; tile (n_folds) test
        # segments across the rest of the index.
        test_size = n_observations // (self.n_folds + 1)
        if test_size == 0:
            raise ValueError(
                f"n_observations={n_observations} too small to produce "
                f"test_size>0 for n_folds={self.n_folds}"
            )

        all_idx = np.arange(n_observations, dtype=np.int64)

        for k in range(self.n_folds):
            # Test segment for fold k starts after the initial reserved
            # block and tiles forward.
            test_start = test_size * (k + 1)
            test_end   = min(test_start + test_size, n_observations)

            test_indices = all_idx[test_start:test_end]
            if test_indices.size == 0:
                # Index exhausted — stop emitting folds.
                break

            # Training segment is everything before the test segment that
            # is NOT purged. Purge: drop any t whose label window reaches
            # into [test_start, test_end - 1], i.e., t such that
            #   t + max_horizon >= test_start
            # → t >= test_start - max_horizon
            purge_cutoff = test_start - self.max_horizon
            # Training set is [0, purge_cutoff)
            train_indices = all_idx[:max(purge_cutoff, 0)]

            # Exclude the configured embargo interval after the previous test
            # segment from this fold's expanding training history.
            if k > 0:
                previous_test_end = test_size * k
                embargo_cutoff = previous_test_end + self.embargo
                train_indices = train_indices[
                    (train_indices < previous_test_end)
                    | (train_indices >= embargo_cutoff)
                ]

            purged_from_naive = test_start - train_indices.size
            # Naive training would have been all_idx[:test_start]; the
            # purge removed (test_start - train_indices.size) of them.

            if train_indices.size < self.min_train_size:
                logger.info(
                    "Fold %d: train_size=%d below min_train_size=%d — skipping.",
                    k, train_indices.size, self.min_train_size,
                )
                continue

            fold = FoldSpec(
                fold_id=k,
                train_indices=train_indices,
                test_indices=test_indices,
                train_size=int(train_indices.size),
                test_size=int(test_indices.size),
                purged_count=int(purged_from_naive),
                train_span=(
                    int(train_indices[0]) if train_indices.size > 0 else -1,
                    int(train_indices[-1]) if train_indices.size > 0 else -1,
                ),
                test_span=(int(test_indices[0]), int(test_indices[-1])),
            )
            # Hard guarantee: no overlap. If this ever raises, fix the
            # purge logic immediately — every downstream metric is invalid.
            fold.assert_no_overlap()
            yield fold

    def summary(self, n_observations: int) -> WalkForwardSummary:
        """Aggregate stats over all folds. Useful for the Phase 2 verifier."""
        folds = list(self.split(n_observations))
        if not folds:
            return WalkForwardSummary(
                n_folds=0, total_train_obs=0, total_test_obs=0,
                purged_total=0, avg_train_size=0.0, avg_test_size=0.0,
                embargo=self.embargo, max_horizon=self.max_horizon,
            )
        return WalkForwardSummary(
            n_folds=len(folds),
            total_train_obs=sum(f.train_size for f in folds),
            total_test_obs=sum(f.test_size for f in folds),
            purged_total=sum(f.purged_count for f in folds),
            avg_train_size=float(np.mean([f.train_size for f in folds])),
            avg_test_size=float(np.mean([f.test_size for f in folds])),
            embargo=self.embargo,
            max_horizon=self.max_horizon,
        )


__all__ = [
    "PurgedWalkForward",
    "FoldSpec",
    "WalkForwardSummary",
]
