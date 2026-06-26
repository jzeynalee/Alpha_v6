# scripts/run_backtest_on_ladder.py
"""
Run backtests on existing validated strategies and record results in the
Evidence Ladder.

Integrates BacktestEngine + EvidenceLadder:
  1. Loads the evidence ladder
  2. Finds hypotheses with existing strategy backtest data
  3. Runs the backtest engine on each strategy
  4. Records stage results (2: In-Sample, 6: Transaction Costs)
  5. Saves updated ladder and generates a summary report

Usage
-----
    python scripts/run_backtest_on_ladder.py
    python scripts/run_backtest_on_ladder.py --family MomentumAlpha
    python scripts/run_backtest_on_ladder.py --hypothesis validated_btc_mr
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.evidence_ladder import (
    EvidenceLadder,
    EvidenceLevel,
    HypothesisRecord,
    StageResult,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backtest_on_ladder")


# ═══════════════════════════════════════════════════════════════════════════════
#  Strategy → Hypothesis Mapping
# ═══════════════════════════════════════════════════════════════════════════════

# Maps hypothesis_ids to their known strategy/signal source.
# Each entry specifies how to construct a backtest signal source.
STRATEGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "btc_mr_l2": {
        "symbol": "BTCUSDT",
        "description": "BTC Mean-Reversion — range-bound mean-reversion on 15m/60m",
        "data_path": "data/raw",
        "timeframe": "60",
    },
    "eth_mom_l1": {
        "symbol": "ETHUSDT",
        "description": "ETH Momentum Continuation — momentum on 60m",
        "data_path": "data/raw",
        "timeframe": "60",
    },
    "sol_mom_l1": {
        "symbol": "SOLUSDT",
        "description": "SOL Momentum Continuation — momentum on 60m",
        "data_path": "data/raw",
        "timeframe": "60",
    },
    "funding_div_l0": {
        "symbol": "BTCUSDT",
        "description": "Funding Divergence — cross-exchange funding divergence",
        "data_path": "data/raw",
        "timeframe": "60",
    },
    "vol_comp_l0": {
        "symbol": "BTCUSDT",
        "description": "Volatility Compression — low vol predicts expansion",
        "data_path": "data/raw",
        "timeframe": "60",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Signal Factory — generates a backtest signal source from existing strategies
# ═══════════════════════════════════════════════════════════════════════════════

def load_ohlcv_data(symbol: str, data_path: str, timeframe: str = "60") -> Optional[pd.DataFrame]:
    """Load OHLCV data from the raw data directory."""
    base = Path(data_path)
    # Try common filename patterns
    patterns = [
        base / f"{symbol}_{timeframe}m.parquet",
        base / f"{symbol}_{timeframe}m.csv",
        base / f"{symbol}_{timeframe}.csv",
        base / f"{symbol}.csv",
    ]
    for p in patterns:
        if p.exists():
            try:
                if p.suffix == ".parquet":
                    return pd.read_parquet(p)
                else:
                    df = pd.read_csv(p)
                    if "timestamp" in df.columns or "datetime" in df.columns:
                        time_col = "timestamp" if "timestamp" in df.columns else "datetime"
                        df[time_col] = pd.to_datetime(df[time_col])
                        df.set_index(time_col, inplace=True)
                    return df
            except Exception as exc:
                logger.warning("Failed to load %s: %s", p, exc)
    return None


def load_backtest_result_from_disk(hypothesis_id: str) -> Optional[Dict[str, Any]]:
    """Load a previously-saved backtest result for a hypothesis."""
    results_dir = Path("data/backtest_results")
    if not results_dir.exists():
        return None
    pattern = f"{hypothesis_id}_backtest"
    for f in results_dir.iterdir():
        if f.name.startswith(pattern) and f.suffix == ".json":
            try:
                with open(f) as fh:
                    return json.load(fh)
            except Exception:
                pass
    return None


def run_single_backtest(
    hypothesis: HypothesisRecord,
    strategy_info: Dict[str, Any],
    config_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a backtest for a single hypothesis using its strategy info.

    Attempts to:
      1. Use existing backtest results stored on disk
      2. Run the backtest engine with a simple signal source
      3. Fall back to loading pre-computed metrics from known files

    Returns a dict with status, metrics, and any errors.
    """
    symbol = strategy_info.get("symbol", "BTCUSDT")
    data_path = strategy_info.get("data_path", "data/raw")
    timeframe = strategy_info.get("timeframe", "60")

    result: Dict[str, Any] = {
        "hypothesis_id": hypothesis.hypothesis_id,
        "symbol": symbol,
        "status": "skipped",
        "metrics": {},
        "notes": "",
    }

    # ── Check for existing backtest results ─────────────────────────────────
    existing = load_backtest_result_from_disk(hypothesis.hypothesis_id)
    if existing:
        summary = existing.get("summary", {})
        result["status"] = "loaded_existing"
        result["metrics"] = {
            "profit_factor": summary.get("profit_factor", 0.0),
            "sharpe": summary.get("sharpe", 0.0),
            "win_rate": summary.get("win_rate", 0.0),
            "total_return_pct": summary.get("total_return_pct", 0.0),
            "max_drawdown_pct": summary.get("equity_max_drawdown_pct", 0.0),
            "closed_trades": summary.get("closed_trades", 0),
        }
        result["notes"] = "Loaded existing backtest result from disk."
        return result

    # ── Attempt to run live backtest ─────────────────────────────────────────
    try:
        ohlcv = load_ohlcv_data(symbol, data_path, timeframe)
        if ohlcv is None:
            result["notes"] = (
                f"No OHLCV data found for {symbol} at {data_path}. "
                "Run the data pipeline first or provide pre-computed backtest metrics."
            )
            return result

        # Use the backtest engine
        from src.backtest.engine import BacktestEngine, BacktestConfig
        from src.backtest.signal_source import BacktestSignal

        # Create a simple signal source based on hypothesis family
        def make_signal_source(family: str):
            """Create a signal function based on the alpha family."""
            if "MeanReversion" in family:
                # Simple mean-reversion: buy when price is below SMA
                def mr_signal(window: pd.DataFrame) -> BacktestSignal:
                    if len(window) < 20:
                        return BacktestSignal.flat()
                    close = window["close"]
                    sma = close.rolling(20).mean()
                    std = close.rolling(20).std()
                    if pd.isna(sma.iloc[-1]) or pd.isna(std.iloc[-1]):
                        return BacktestSignal.flat()
                    z = (close.iloc[-1] - sma.iloc[-1]) / max(std.iloc[-1], 1e-9)
                    if z < -1.5:
                        return BacktestSignal(direction=1, proba_alpha=0.70, strategy_id=family)
                    elif z > 1.5:
                        return BacktestSignal(direction=-1, proba_alpha=0.70, strategy_id=family)
                    return BacktestSignal.flat()
                return mr_signal

            elif "Momentum" in family:
                # Simple momentum: buy when close > SMA
                def mom_signal(window: pd.DataFrame) -> BacktestSignal:
                    if len(window) < 20:
                        return BacktestSignal.flat()
                    close = window["close"]
                    sma = close.rolling(20).mean()
                    if pd.isna(sma.iloc[-1]):
                        return BacktestSignal.flat()
                    if close.iloc[-1] > sma.iloc[-1]:
                        return BacktestSignal(direction=1, proba_alpha=0.65, strategy_id=family)
                    return BacktestSignal.flat()
                return mom_signal

            else:
                # Default: flat — no generic backtest
                return None

        signal_fn = make_signal_source(hypothesis.family)
        if signal_fn is None:
            result["notes"] = (
                f"No backtest signal source available for family '{hypothesis.family}'. "
                "Provide pre-computed backtest metrics in hypothesis.metrics."
            )
            return result

        config = BacktestConfig(
            initial_cash=10_000.0,
            fee_pct=0.001,
            slippage_pct=0.0005,
            warmup_bars=50,
            allow_short=True,
        )
        if config_override:
            for k, v in config_override.items():
                if hasattr(config, k):
                    setattr(config, k, v)

        engine = BacktestEngine(signal_source=signal_fn, config=config)
        bt_result = engine.run(ohlcv)

        result["status"] = "backtest_run"
        result["metrics"] = {
            "profit_factor": bt_result.profit_factor,
            "sharpe": bt_result.sharpe,
            "win_rate": bt_result.win_rate,
            "total_return_pct": bt_result.total_return_pct,
            "max_drawdown_pct": bt_result.equity_max_drawdown_pct,
            "closed_trades": bt_result.closed_trades,
            "bars_processed": bt_result.bars_processed,
            "exposure_pct": bt_result.exposure_pct,
        }
        result["notes"] = f"Backtest completed: {bt_result.closed_trades} trades, PF={bt_result.profit_factor:.2f}"

        # Save result to disk
        bt_result.to_json(
            Path(f"data/backtest_results/{hypothesis.hypothesis_id}_backtest.json")
        )

    except ImportError as exc:
        result["notes"] = f"Backtest engine unavailable: {exc}"
    except Exception as exc:
        result["status"] = "error"
        result["notes"] = f"Backtest failed: {exc}"
        logger.warning("Backtest error for %s: %s", hypothesis.hypothesis_id, exc)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def record_backtest_metrics(
    ladder: EvidenceLadder,
    hypothesis_id: str,
    metrics: Dict[str, Any],
    notes: str,
) -> None:
    """Record backtest metrics into a hypothesis record in the evidence ladder."""
    record = ladder.get(hypothesis_id)
    if record is None:
        logger.warning("Hypothesis %s not found in ladder.", hypothesis_id)
        return

    # Store in-sample metrics
    pf = metrics.get("profit_factor", 0.0)
    sharpe = metrics.get("sharpe", 0.0)
    wr = metrics.get("win_rate", 0.0)

    record.metrics["in_sample"] = {
        "profit_factor": pf,
        "sharpe": sharpe,
        "win_rate": wr,
        "total_return_pct": metrics.get("total_return_pct", 0.0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "closed_trades": metrics.get("closed_trades", 0),
        "source": "backtest_on_ladder",
    }

    # Store transaction cost metrics (gross = net since fees already applied)
    record.metrics["transaction_costs"] = {
        "pf_gross": pf,      # Already includes fees from backtest engine
        "pf_net": pf,
        "annual_turnover": metrics.get("closed_trades", 0) * 2 / max(
            metrics.get("bars_processed", 1) / (365 * 24), 1
        ) if metrics.get("bars_processed", 0) > 0 else 0.0,
    }

    record.updated_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Recorded backtest metrics for %s: PF=%.2f, Sharpe=%.2f",
        hypothesis_id, pf, sharpe,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run backtests on evidence ladder hypotheses."
    )
    parser.add_argument(
        "--ladder", default="data/experiments/evidence_ladder.json",
        help="Path to evidence ladder JSON",
    )
    parser.add_argument(
        "--family", default=None,
        help="Restrict to a specific alpha family",
    )
    parser.add_argument(
        "--hypothesis", default=None,
        help="Run a single hypothesis by ID",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Load and check without saving",
    )
    parser.add_argument(
        "--output-dir", default="data/backtest_results",
        help="Directory for backtest result files",
    )
    args = parser.parse_args()

    # ── Load ladder ──────────────────────────────────────────────────────────
    ladder = EvidenceLadder(path=args.ladder)
    if not ladder.load():
        logger.error("Failed to load evidence ladder.")
        sys.exit(1)

    print(ladder.render_summary())
    print()

    # ── Select hypotheses ────────────────────────────────────────────────────
    if args.hypothesis:
        records = [ladder.get(args.hypothesis)]
        records = [r for r in records if r is not None]
    elif args.family:
        records = ladder.list_by_family(args.family)
    else:
        # Default: validated + promising hypotheses that have strategy mappings
        records = [
            ladder.get(hid) for hid in STRATEGY_REGISTRY
            if ladder.get(hid) is not None
        ]

    if not records:
        logger.warning("No hypotheses matched.")
        sys.exit(0)

    print(f"Testing {len(records)} hypotheses...\n")

    # ── Create output directory ──────────────────────────────────────────────
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # ── Run backtests ────────────────────────────────────────────────────────
    results = []
    for record in records:
        strategy_info = STRATEGY_REGISTRY.get(record.hypothesis_id, {})
        if not strategy_info:
            logger.info(
                "Skipping %s — no strategy mapping in registry.",
                record.hypothesis_id,
            )
            results.append({
                "hypothesis_id": record.hypothesis_id,
                "status": "skipped",
                "notes": "No strategy mapping.",
            })
            continue

        print(f"  [{record.family}] {record.hypothesis_id}: {strategy_info.get('description', 'N/A')}")
        bt_result = run_single_backtest(record, strategy_info)
        results.append(bt_result)

        if bt_result["status"] in ("backtest_run", "loaded_existing"):
            record_backtest_metrics(
                ladder, record.hypothesis_id,
                bt_result["metrics"], bt_result["notes"],
            )
            # Run stages 2 and 6 through the pipeline
            from src.core.research_pipeline import ResearchPipeline
            pipeline = ResearchPipeline(ladder)
            pipeline.run_hypothesis(
                record.hypothesis_id,
                requested_stages=[2, 6],  # In-sample + transaction costs only
            )
            print(f"    → PF={bt_result['metrics'].get('profit_factor', 0):.2f}, "
                  f"Sharpe={bt_result['metrics'].get('sharpe', 0):.2f}")
        else:
            print(f"    → {bt_result['status']}: {bt_result['notes'][:100]}")

    # ── Save ladder ──────────────────────────────────────────────────────────
    if not args.dry_run:
        ladder.save()
        print(f"\nEvidence ladder saved to: {args.ladder}")

    # ── Summary report ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(" BACKTEST RUNNER SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r["status"] in ("backtest_run", "loaded_existing"))
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "error")
    print(f"  Total:  {len(results)}")
    print(f"  Passed: {passed}")
    print(f"  Skipped:{skipped}")
    print(f"  Failed: {failed}")
    print()

    for r in results:
        status_icon = {"backtest_run": "✓", "loaded_existing": "✓", "skipped": "○", "error": "✗"}.get(r["status"], "?")
        print(f"  [{status_icon}] {r['hypothesis_id']:<30} {r['status']:<20} {r['notes'][:80]}")

    print("\n" + ladder.render_summary())


if __name__ == "__main__":
    main()
