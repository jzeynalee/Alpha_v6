"""
Event-Study Engine — Tests market mechanism hypotheses, not trading strategies.

Core principle: before building a strategy, validate that a measurable condition
actually predicts future returns. This separates mechanism validation from
strategy construction.

Architecture:
  1. Define trigger condition (e.g., Z-score < -2.5)
  2. Collect all trigger events across full history
  3. Measure forward returns at multiple horizons (1, 3, 5, 10, 20 bars)
  4. Test statistical significance (t-test, bootstrap, permutation)
  5. Split by regime (trend, vol, funding, OI)
  6. Cross-asset validation
  7. Only then build strategy rules

Usage:
    from src.validation.event_study import EventStudy
    study = EventStudy("BTCUSDT", "15m")
    study.add_trigger("z_score_neg2.5", lambda df: df["z_score"] < -2.5)
    study.add_trigger("z_score_pos2.5", lambda df: df["z_score"] > 2.5)
    results = study.run()
    study.report(results)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class EventStudyResult:
    """Results for one trigger condition at multiple horizons."""
    trigger_name: str
    n_events: int
    n_total_bars: int
    event_rate_pct: float
    horizons: List[int] = field(default_factory=lambda: [1, 3, 5, 10, 20])
    # Per-horizon statistics
    mean_return: Dict[int, float] = field(default_factory=dict)
    median_return: Dict[int, float] = field(default_factory=dict)
    std_return: Dict[int, float] = field(default_factory=dict)
    win_rate: Dict[int, float] = field(default_factory=dict)
    # Statistical tests
    t_statistic: Dict[int, float] = field(default_factory=dict)
    t_pvalue: Dict[int, float] = field(default_factory=dict)
    bootstrap_ci_lower: Dict[int, float] = field(default_factory=dict)
    bootstrap_ci_upper: Dict[int, float] = field(default_factory=dict)
    permutation_pvalue: Dict[int, float] = field(default_factory=dict)
    # Significant horizons
    significant_horizons: List[int] = field(default_factory=list)
    # Regime splits
    regime_results: Dict[str, Dict[int, float]] = field(default_factory=dict)
    # Raw event data for inspection
    event_timestamps: List[Any] = field(default_factory=list)
    raw_returns: Dict[int, np.ndarray] = field(default_factory=dict)


class EventStudy:
    """
    Event-study engine for mechanism hypothesis testing.

    Parameters
    ----------
    symbol : str
        e.g. "BTCUSDT"
    timeframe : str
        e.g. "15m", "1h"
    max_bars : int
        Maximum bars to analyze (None = all)
    min_bars_between_events : int
        Minimum bars between trigger events to avoid overlap
    """

    HORIZONS = [1, 3, 5, 10, 20]

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        max_bars: Optional[int] = None,
        min_bars_between_events: int = 10,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_bars = max_bars
        self.min_bars_between_events = min_bars_between_events
        self._triggers: Dict[str, Callable] = {}
        self._df: Optional[pd.DataFrame] = None
        self._results: List[EventStudyResult] = []

    # ── Data loading ────────────────────────────────────────────────────────

    def load_data(self) -> pd.DataFrame:
        """Load OHLCV data via DatasetRegistry."""
        from src.core.dataset_registry import registry

        df = registry.get_ohlcv("binance", self.symbol, self.timeframe)
        if df is None:
            raise ValueError(f"No data for {self.symbol}/{self.timeframe}")
        if self.max_bars and len(df) > self.max_bars:
            df = df.iloc[-self.max_bars:].copy()
        return df

    # ── Trigger registration ────────────────────────────────────────────────

    def add_trigger(self, name: str, condition_fn: Callable[[pd.DataFrame], pd.Series]):
        """
        Register a trigger condition.

        Parameters
        ----------
        name : str
            e.g. "z_score_neg2.5"
        condition_fn : callable
            Takes the DataFrame, returns a boolean Series (True where triggered).
        """
        self._triggers[name] = condition_fn

    # ── Feature computation ─────────────────────────────────────────────────

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all feature columns needed for trigger conditions."""
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Z-score
        df["sma20"] = close.rolling(20).mean()
        df["std20"] = close.rolling(20).std()
        df["z_score"] = (close - df["sma20"]) / df["std20"].clip(lower=1e-9)

        # Z-score variants
        df["sma100"] = close.rolling(100).mean()
        df["std100"] = close.rolling(100).std()
        df["z_score_100"] = (close - df["sma100"]) / df["std100"].clip(lower=1e-9)

        # Returns
        df["ret_1"] = close.pct_change(1)
        df["ret_5"] = close.pct_change(5)
        df["ret_20"] = close.pct_change(20)

        # Regime: Trend (ADX approximation via SMA slopes)
        df["sma50"] = close.rolling(50).mean()
        df["trend_strength"] = (df["sma50"] - df["sma50"].shift(20)) / df["sma50"].shift(20)
        df["regime_trend"] = "neutral"
        df.loc[df["trend_strength"] > 0.02, "regime_trend"] = "bull"
        df.loc[df["trend_strength"] < -0.02, "regime_trend"] = "bear"

        # Regime: Volatility (ATR percentile)
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        df["atr_percentile"] = atr14.rolling(100).rank(pct=True)
        df["regime_vol"] = "medium"
        df.loc[df["atr_percentile"] > 0.67, "regime_vol"] = "high"
        df.loc[df["atr_percentile"] < 0.33, "regime_vol"] = "low"

        # Regime: Volume
        df["vol_ratio"] = volume / volume.rolling(20).mean()
        df["regime_volume"] = "normal"
        df.loc[df["vol_ratio"] > 1.5, "regime_volume"] = "high"
        df.loc[df["vol_ratio"] < 0.5, "regime_volume"] = "low"

        return df

    # ── Main execution ──────────────────────────────────────────────────────

    def run(self) -> List[EventStudyResult]:
        """Run event study for all registered triggers."""
        if not self._triggers:
            raise ValueError("No triggers registered. Call add_trigger() first.")

        self._df = self.load_data()
        self._df = self.compute_features(self._df)
        n_bars = len(self._df)

        self._results = []
        for trigger_name, condition_fn in self._triggers.items():
            logger.info("Event study: %s on %s/%s", trigger_name, self.symbol, self.timeframe)

            # Detect trigger events
            trigger_mask = condition_fn(self._df)
            # Enforce min bars between events
            event_indices = self._find_events(trigger_mask)

            result = EventStudyResult(
                trigger_name=trigger_name,
                n_events=len(event_indices),
                n_total_bars=n_bars,
                event_rate_pct=len(event_indices) / max(n_bars, 1) * 100,
            )

            if len(event_indices) < 5:
                logger.warning("  Only %d events — insufficient for statistics", len(event_indices))
                self._results.append(result)
                continue

            # ── Forward returns analysis ─────────────────────────────────
            for h in self.HORIZONS:
                fwd_rets = self._compute_forward_returns(event_indices, h)

                result.mean_return[h] = float(np.mean(fwd_rets))
                result.median_return[h] = float(np.median(fwd_rets))
                result.std_return[h] = float(np.std(fwd_rets, ddof=1))
                result.win_rate[h] = float(np.mean(fwd_rets > 0))
                result.raw_returns[h] = fwd_rets

                # Statistical tests
                t_stat, t_pval = self._t_test(fwd_rets)
                result.t_statistic[h] = float(t_stat)
                result.t_pvalue[h] = float(t_pval)

                ci_low, ci_high = self._bootstrap_ci(fwd_rets)
                result.bootstrap_ci_lower[h] = float(ci_low)
                result.bootstrap_ci_upper[h] = float(ci_high)

                perm_pval = self._permutation_test(fwd_rets, event_indices, h)
                result.permutation_pvalue[h] = float(perm_pval)

                # Significance check
                if t_pval < 0.05 and ci_low > 0:
                    result.significant_horizons.append(h)

                logger.info(
                    "  h=%2d: mean=%+.5f median=%+.5f std=%.4f win=%.1f%% "
                    "t=%.2f p=%.3f CI=[%+.4f, %+.4f] perm_p=%.3f %s",
                    h, result.mean_return[h], result.median_return[h],
                    result.std_return[h], result.win_rate[h] * 100,
                    t_stat, t_pval, ci_low, ci_high, perm_pval,
                    "★" if h in result.significant_horizons else "",
                )

            # ── Regime dependence ───────────────────────────────────────
            result.regime_results = self._analyze_regimes(event_indices)

            self._results.append(result)

        return self._results

    # ── Internal methods ────────────────────────────────────────────────────

    def _find_events(self, trigger_mask: pd.Series) -> List[int]:
        """Find trigger event indices with minimum bar separation."""
        indices = []
        last_event = -self.min_bars_between_events - 1
        for i in range(len(trigger_mask)):
            if trigger_mask.iloc[i] and (i - last_event) > self.min_bars_between_events:
                # Skip last bars where we can't compute forward returns
                if i + max(self.HORIZONS) < len(trigger_mask):
                    indices.append(i)
                    last_event = i
        return indices

    def _compute_forward_returns(self, event_indices: List[int], horizon: int) -> np.ndarray:
        """Compute forward returns from event indices to horizon bars later."""
        close = self._df["close"].values
        returns = []
        for idx in event_indices:
            if idx + horizon < len(close):
                ret = (close[idx + horizon] - close[idx]) / close[idx]
                returns.append(ret)
        return np.array(returns)

    # ── Statistical tests ───────────────────────────────────────────────────

    @staticmethod
    def _t_test(returns: np.ndarray) -> Tuple[float, float]:
        """One-sample t-test: H0: mean = 0 vs H1: mean > 0."""
        from math import sqrt

        n = len(returns)
        if n < 3:
            return 0.0, 1.0
        mean = float(np.mean(returns))
        std = float(np.std(returns, ddof=1))
        if std == 0:
            return 0.0, 1.0
        t_stat = mean / (std / sqrt(n))
        # Approximate p-value from t-distribution (one-sided)
        # Using normal approximation for simplicity
        from math import erf
        p_val = 1.0 - 0.5 * (1.0 + erf(t_stat / sqrt(2.0)))
        return t_stat, p_val

    @staticmethod
    def _bootstrap_ci(returns: np.ndarray, n_bootstrap: int = 5000, alpha: float = 0.05) -> Tuple[float, float]:
        """Bootstrap 95% confidence interval for mean return."""
        n = len(returns)
        if n < 10:
            return -1.0, 1.0
        rng = np.random.default_rng(42)
        means = np.zeros(n_bootstrap)
        for i in range(n_bootstrap):
            sample = rng.choice(returns, size=n, replace=True)
            means[i] = float(np.mean(sample))
        ci_low = float(np.percentile(means, alpha / 2 * 100))
        ci_high = float(np.percentile(means, (1 - alpha / 2) * 100))
        return ci_low, ci_high

    def _permutation_test(self, returns: np.ndarray, event_indices: List[int], horizon: int, n_perms: int = 2000) -> float:
        """Permutation test: randomize event times, compare to observed mean."""
        observed_mean = float(np.mean(returns))
        close = self._df["close"].values
        n_bars = len(close)

        rng = np.random.default_rng(42)
        perm_means = np.zeros(n_perms)
        n_events = len(event_indices)
        for p in range(n_perms):
            # Random event times (avoiding overlap)
            random_indices = rng.choice(
                n_bars - horizon - 1, size=min(n_events, n_bars // self.min_bars_between_events), replace=False
            )
            perm_rets = []
            for idx in random_indices:
                if idx + horizon < n_bars:
                    perm_rets.append((close[idx + horizon] - close[idx]) / close[idx])
            if perm_rets:
                perm_means[p] = float(np.mean(perm_rets))

        # One-sided: fraction of permutations with mean >= observed
        p_val = float(np.mean(perm_means >= observed_mean))
        return p_val

    # ── Regime analysis ─────────────────────────────────────────────────────

    def _analyze_regimes(self, event_indices: List[int]) -> Dict[str, Dict[int, float]]:
        """Split events by regime and compute forward returns."""
        regime_results: Dict[str, Dict[int, float]] = {}

        regime_cols = ["regime_trend", "regime_vol", "regime_volume"]
        for col in regime_cols:
            if col not in self._df.columns:
                continue
            unique_regimes = self._df[col].dropna().unique()
            for regime_val in unique_regimes:
                regime_key = f"{col}={regime_val}"
                regime_indices = [
                    idx for idx in event_indices
                    if idx < len(self._df) and self._df[col].iloc[idx] == regime_val
                ]
                if len(regime_indices) < 5:
                    continue
                regime_results[regime_key] = {}
                for h in self.HORIZONS:
                    fwd_rets = self._compute_forward_returns(regime_indices, h)
                    regime_results[regime_key][h] = float(np.mean(fwd_rets))

        return regime_results

    # ── Cross-asset validation ──────────────────────────────────────────────

    def cross_asset(self, trigger_name: str, symbols: List[str]) -> Dict[str, Dict[int, float]]:
        """Run the same trigger condition on multiple symbols."""
        results = {}
        trigger_fn = self._triggers.get(trigger_name)
        if trigger_fn is None:
            raise ValueError(f"Trigger '{trigger_name}' not registered")

        from src.core.dataset_registry import registry

        for sym in symbols:
            df = registry.get_ohlcv("binance", sym, self.timeframe)
            if df is None:
                logger.warning("No data for %s", sym)
                continue
            if self.max_bars and len(df) > self.max_bars:
                df = df.iloc[-self.max_bars:].copy()
            df = self.compute_features(df)
            trigger_mask = trigger_fn(df)
            event_indices = self._find_events(trigger_mask)

            results[sym] = {}
            for h in self.HORIZONS:
                fwd_rets = self._compute_forward_returns(event_indices, h)
                results[sym][h] = float(np.mean(fwd_rets)) if len(fwd_rets) > 0 else float("nan")

        return results

    # ── Report ──────────────────────────────────────────────────────────────

    def report(self, results: Optional[List[EventStudyResult]] = None) -> str:
        """Generate a formatted report."""
        if results is None:
            results = self._results

        lines = []
        lines.append("# Event Study Report")
        lines.append("")
        lines.append(f"**Symbol**: {self.symbol} | **Timeframe**: {self.timeframe}")
        lines.append(f"**Bars analyzed**: {len(self._df) if self._df is not None else 'N/A'}")
        lines.append(f"**Triggers tested**: {len(results)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for r in results:
            lines.append(f"## Trigger: {r.trigger_name}")
            lines.append("")
            lines.append(f"- **Events detected**: {r.n_events} ({r.event_rate_pct:.2f}% of bars)")
            lines.append(f"- **Significant horizons**: {r.significant_horizons if r.significant_horizons else 'NONE'}")
            lines.append("")

            lines.append("### Forward Returns by Horizon")
            lines.append("")
            lines.append("| Horizon | Mean | Median | Std | Win Rate | t-stat | p-value | Bootstrap 95% CI | Perm p |")
            lines.append("|---------|------|--------|-----|----------|--------|---------|-------------------|--------|")
            for h in r.horizons:
                sig = " ★" if h in r.significant_horizons else ""
                lines.append(
                    f"| {h:>2} bar{sig} | {r.mean_return.get(h, 0):+.5f} | {r.median_return.get(h, 0):+.5f} | "
                    f"{r.std_return.get(h, 0):.4f} | {r.win_rate.get(h, 0):.1%} | "
                    f"{r.t_statistic.get(h, 0):+.2f} | {r.t_pvalue.get(h, 1):.4f} | "
                    f"[{r.bootstrap_ci_lower.get(h, 0):+.4f}, {r.bootstrap_ci_upper.get(h, 0):+.4f}] | "
                    f"{r.permutation_pvalue.get(h, 1):.4f} |"
                )
            lines.append("")

            # Regime splits
            if r.regime_results:
                lines.append("### Regime Dependence (Mean Return by Horizon)")
                lines.append("")
                regime_categories = {}
                for key in r.regime_results:
                    cat = key.split("=")[0]
                    regime_categories.setdefault(cat, []).append(key)

                for cat, keys in regime_categories.items():
                    lines.append(f"**{cat}**:")
                    lines.append("")
                    header = "| Regime | " + " | ".join(f"h={h}" for h in r.horizons) + " |"
                    lines.append(header)
                    sep = "|--------|" + "|".join(["------" for _ in r.horizons]) + "|"
                    lines.append(sep)
                    for key in keys:
                        regime_name = key.split("=", 1)[1]
                        vals = " | ".join(
                            f"{r.regime_results[key].get(h, float('nan')):+.5f}"
                            for h in r.horizons
                        )
                        lines.append(f"| {regime_name} | {vals} |")
                    lines.append("")

            # Verdict
            if r.significant_horizons:
                best_h = min(r.significant_horizons, key=lambda h: r.t_pvalue.get(h, 1))
                lines.append(f"**Verdict**: MECHANISM CONFIRMED at horizon {best_h} (p={r.t_pvalue[best_h]:.4f})")
            else:
                lines.append("**Verdict**: HYPOTHESIS REJECTED — no significant predictive power")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def best_result(self) -> Optional[EventStudyResult]:
        """Return the result with the most significant horizon, or None."""
        if not self._results:
            return None
        best = None
        best_p = 1.0
        for r in self._results:
            for h, p in r.t_pvalue.items():
                if p < best_p and h in r.significant_horizons:
                    best_p = p
                    best = r
        return best
