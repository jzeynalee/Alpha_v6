"""Regression tests for defects identified by the repository audit."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from src.core.research_pipeline import ResearchPipeline
from src.cv.walk_forward import PurgedWalkForward
from src.validation.event_study import EventStudy


def _synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    close = np.exp(np.linspace(0.0, 1.0, n))
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": np.ones(n),
        },
        index=index,
    )


def test_event_study_uses_student_t_p_value() -> None:
    returns = np.array([0.01, 0.02, -0.005, 0.015, 0.008, -0.003])
    statistic, p_value = EventStudy._t_test(returns)

    expected = float(student_t.sf(statistic, df=len(returns) - 1))
    assert p_value == expected


def test_event_study_rejects_sentinel_small_sample_interval() -> None:
    lower, upper = EventStudy._bootstrap_ci(np.ones(5))

    assert np.isnan(lower)
    assert np.isnan(upper)


def test_event_study_stability_uses_window_local_data() -> None:
    study = EventStudy("SYNTH", "1h")
    study._df = study.compute_features(_synthetic_ohlcv())
    study.add_trigger(
        "periodic",
        lambda frame: pd.Series(
            [index % 15 == 0 for index in range(len(frame))],
            index=frame.index,
        ),
    )

    result = study.stability_analysis("periodic", window_bars=120)

    assert result["n_windows"] > 0
    assert len(result["rolling_means_bp"]) == result["n_windows"]


def test_walk_forward_applies_embargo() -> None:
    embargo = 5
    folds = list(PurgedWalkForward(
        n_folds=3,
        max_horizon=2,
        embargo=embargo,
    ).split(40))

    for previous, current in zip(folds, folds[1:]):
        forbidden = set(range(
            previous.test_span[1] + 1,
            previous.test_span[1] + 1 + embargo,
        ))
        assert forbidden.isdisjoint(current.train_indices.tolist())


def test_pipeline_profit_factor_is_gross_profit_over_gross_loss() -> None:
    returns = np.array([0.10, 0.05, -0.05, -0.025])

    assert ResearchPipeline._profit_factor(returns) == 2.0


def test_pipeline_bootstrap_p_value_is_null_centered() -> None:
    returns = np.array([0.01] * 30)

    result = ResearchPipeline.evaluate_bootstrap(returns, n_bootstrap=500, seed=7)

    assert result["p_value"] > 0.0
    assert result["p_value"] <= 1.0
    assert result["ci_lower_95"] > 0.0
