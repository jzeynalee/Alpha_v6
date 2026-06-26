# src/core/constants.py
"""
Single source of truth for cross-module constants (M3).

Before this module, two constants were duplicated by hand across files and
had drifted out of sync:

  * ``TF_MULTIPLIERS`` existed in BOTH ``src/data/orchestrator.py`` and
    ``src/core/layers/market_structure.py`` — and the two copies disagreed:
    orchestrator used {micro:1, intermediate:3, macro:12} while
    market_structure used {micro:1, intermediate:4, macro:16}. That is a
    real bug: the resampler and the market-structure engine were segmenting
    the same bar stream on different timeframe ratios.

  * ``MAX_LOOKBACK`` lived only on ``FeatureEngineerOptimized`` but was
    referenced (and re-derived as "+200") in ``alpha_factory.py`` and
    assumed in ``warmup_tracker.py`` and ``settings.py``.

Everything that needs these values now imports them from here.

⚠️  Changing ``MAX_LOOKBACK`` or ``TF_MULTIPLIERS`` invalidates every offline
    artefact (decision models, CSS table, calibration, HMM) because the bar
    indexing and feature windows shift. After changing either, retrain all
    artefacts before going live.
"""

from __future__ import annotations

# ─── Timeframe multipliers ───────────────────────────────────────────────────
# Multipliers relative to the base bar interval (the orchestrator's
# base_interval, 300 s = 5 min in production).
#
#   micro        =  5 min  (1  × base)
#   intermediate = 15 min  (3  × base)
#   macro        = 60 min  (12 × base)
#
# These MUST match the resolutions the decision models were trained on —
# confirmed by the artefact filenames decision_model_{version}_{symbol}_{tf}.pkl
# (e.g. decision_model_v1_BTCUSDT_5.pkl / _15.pkl / _60.pkl). NOTE: there is
# NO "_c0_" segment — decision_layer._load_all_models() splits the filename
# stem on "_" and reads exactly five tokens: decision, model, version, symbol,
# timeframe. The earlier "_c0_" form documented here was incorrect (F9). The
# previous market_structure.py copy (1/4/16) was wrong and is corrected by
# importing this dict.
TF_MULTIPLIERS: dict[str, int] = {
    "micro":        1,
    "intermediate": 3,
    "macro":        12,
}

# Ordered timeframe names — useful where iteration order matters.
TIMEFRAMES: tuple[str, ...] = ("micro", "intermediate", "macro")


# ─── Feature engineering lookback ────────────────────────────────────────────
# Maximum rolling window (in bars) across every indicator computed by
# FeatureEngineerOptimized. Feature rows before bar index MAX_LOOKBACK are not
# fully formed (long-period indicators are still NaN).
#
# FeatureEngineerOptimized.MAX_LOOKBACK is kept as a class attribute for
# backward compatibility but is assigned FROM this constant (see
# features_engineering.py M3 patch) so there is exactly one literal.
MAX_LOOKBACK: int = 1050

# Safety margin appended to MAX_LOOKBACK when sizing rolling OHLCV buffers
# (e.g. AlphaFactory._ohlcv_maxlen = MAX_LOOKBACK + OHLCV_BUFFER_MARGIN).
OHLCV_BUFFER_MARGIN: int = 200

# ─── Default data snapshot version ───────────────────────────────────────────
# Single fallback default for the versioned-data identifier. AlphaFactory and
# layers 2/3/4 accept data_version as a constructor argument; production
# callers (main_v3.py, run_backtest.py) read config["data_version"] and pass
# it explicitly. This constant exists so the literal "v1" is not duplicated as
# a per-module default (F10). It only applies to direct instantiation — e.g.
# in tests.
DEFAULT_DATA_VERSION: str = "v1"


__all__ = [
    "TF_MULTIPLIERS",
    "TIMEFRAMES",
    "MAX_LOOKBACK",
    "OHLCV_BUFFER_MARGIN",
]
