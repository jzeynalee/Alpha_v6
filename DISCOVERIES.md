# DISCOVERIES.md

> **Scientific notebook of validated empirical findings.**
> Every entry has: observation, confidence, evidence, experiments, counterexamples, status.
> This file is the persistent research memory. It grows over time.

---

## 1. Cross-Asset Behavior

### D001: BTC behaves differently from ETH
- **Confidence**: Confirmed (5/5)
- **Statement**: Strategies that work on BTC often fail on ETH and vice versa. BTC shows stronger mean-reversion at intraday timeframes; ETH is more momentum-driven.
- **Experiments**: `experiment_family_a_btc_validation`, `btc_vs_eth_comparison`, `compare_cross_asset`
- **Counterexamples**: None found. The effect persists across 2022-2026.
- **Implication**: Never assume a strategy transfers. Always run cross-asset validation (Stage 8).
- **Status**: Active

### D002: SOL behaves differently from BTC and ETH
- **Confidence**: Strong (4/5)
- **Statement**: SOL has higher volatility, stronger momentum persistence, and distinct regime behavior due to high retail participation.
- **Experiments**: `experiment_family_b_altcoin_momentum`, `sol_momentum_60m`
- **Counterexamples**: None. Consistent across available data.
- **Implication**: SOL strategies must account for higher slippage, wider spreads, and faster regime changes.
- **Status**: Active

---

## 2. Signal Construction

### D003: Z-score outperforms percentage-stretch for mean-reversion
- **Confidence**: Confirmed (5/5)
- **Statement**: Z-score (deviation from mean in units of standard deviation) produces more robust mean-reversion signals than fixed percentage thresholds (e.g., "price down 5%"). The advantage is regime-adaptivity: z-score normalizes by recent volatility.
- **Experiments**: `failed_mr_thesis`, `zscore_vs_pct_stretch`, `experiment_phase3_multi_asset_zscore`
- **Counterexamples**: In extremely low-volatility regimes, percentage-stretch can outperform because z-score amplifies noise.
- **Implication**: Always use z-score or adaptive thresholds for mean-reversion. Never use fixed percentage.
- **Status**: Active

### D004: Funding rate as a standalone signal is weak
- **Confidence**: Strong (4/5)
- **Statement**: Extreme funding rates do precede reversals, but timing is unreliable. Funding alone has a ~52% win rate with poor risk-adjusted returns. Must be combined with OI divergence or price confirmation.
- **Experiments**: `experiment_family_c_funding`, `funding_standalone_test`, `decompose_funding_pnl`
- **Counterexamples**: None. Consistent across BTC and ETH.
- **Implication**: Never trade funding in isolation. Always pair with OI or price action confirmation.
- **Status**: Active

---

## 3. Validation Methodology

### D005: Walk-forward validation kills 30-60% of in-sample profit factor
- **Confidence**: Confirmed (5/5)
- **Statement**: Strategies that show PF 1.5-3.0 in-sample typically degrade to PF 0.8-1.3 in walk-forward. This is the single most important lesson from 2025-2026 research.
- **Experiments**: `walk_forward_btc_mr`, `walk_forward_eth_mom`, `experiment_b1_walkforward`, `experiment_track_a_walkforward`
- **Counterexamples**: None. The effect is universal across all tested strategy types.
- **Implication**: Stage 3 (walk-forward) is the hardest gate. Never trust in-sample results. Always run purged walk-forward.
- **Status**: Active

### D006: Transaction costs destroy many apparent alphas
- **Confidence**: Confirmed (5/5)
- **Statement**: Strategies with gross PF 1.5+ frequently fall below 1.0 after 10bp fee + 5bp slippage. High-turnover strategies (>50 trades/year) are especially vulnerable.
- **Experiments**: `cost_sensitivity_analysis`, `l4_realistic_cost_test`, `evaluate_l4_comparison`
- **Counterexamples**: Low-frequency strategies (<10 trades/year) are relatively cost-immune.
- **Implication**: Always backtest with realistic costs (Stage 6). Maker-order execution can recover ~5bp but introduces fill risk.
- **Status**: Active

---

## 4. Regime & Context

### D007: Multi-timeframe context significantly impacts strategy performance
- **Confidence**: Strong (4/5)
- **Statement**: A strategy's performance varies dramatically depending on the higher-timeframe regime. A mean-reversion strategy that works in a range-bound 4H regime may fail in a trending 4H regime.
- **Experiments**: `experiment_mtf_zscore`, `experiment_phase2b_mtf`, `mtf_context_analysis`
- **Counterexamples**: Purely trend-following strategies show less MTF sensitivity.
- **Implication**: HTF regime should gate or modulate LTF signal thresholds. This is the basis for the Context Engine (Program F).
- **Status**: Active

### D008: Market microstructure differs meaningfully across assets
- **Confidence**: Moderate (3/5)
- **Statement**: BTC has deepest order books and tightest spreads. Altcoins (ETH, SOL, DOGE) have wider spreads and shallower books. LOB imbalance signals that work on BTC may fail on thinner markets.
- **Experiments**: `microstructure_comparison`
- **Counterexamples**: Limited sample. Needs more cross-asset microstructure experiments.
- **Implication**: Microstructure strategies should be validated per-asset. Do not assume BTC-tuned parameters transfer.
- **Status**: Active — more evidence needed

---

## 5. Strategy-Specific

### D009: BTC Mean-Reversion failed walk-forward
- **Confidence**: Confirmed (5/5)
- **Statement**: BTC mean-reversion strategies that showed PF 1.8-2.2 in-sample degraded to PF 0.9-1.1 in walk-forward. The edge exists but is regime-dependent — it appears only during neutral/range-bound conditions.
- **Experiments**: `failed_mr_thesis`, `failed_mr_thesis_retry`, `btc_mr_walkforward`
- **Counterexamples**: None. The pattern is consistent.
- **Implication**: BTC MR is not a standalone alpha. It can work as a regime-conditioned component if gated by HTF context.
- **Status**: Hypothesis at L2 — needs re-discovery with MTF filtering

### D010: ETH Momentum needs walk-forward
- **Confidence**: Suggestive (2/5)
- **Statement**: ETH momentum continuation showed promising in-sample results but has not been walk-forward tested. The in-sample edge may not survive.
- **Experiments**: Pending
- **Counterexamples**: N/A — insufficient evidence
- **Implication**: Run Stage 3 (walk-forward) on ETH momentum before any further development.
- **Status**: Hypothesis at L1 — awaiting walk-forward

---

## Summary

| ID | Finding | Domain | Confidence |
|----|---------|--------|------------|
| D001 | BTC ≠ ETH | cross_asset | Confirmed |
| D002 | SOL ≠ BTC/ETH | cross_asset | Strong |
| D003 | Z-score > % stretch | signal_construction | Confirmed |
| D004 | Funding alone is weak | signal_construction | Strong |
| D005 | Walk-forward kills 30-60% PF | validation | Confirmed |
| D006 | Costs destroy apparent alphas | validation | Confirmed |
| D007 | MTF context matters | regime | Strong |
| D008 | Microstructure differs per asset | microstructure | Moderate |
| D009 | BTC MR failed walk-forward | strategy | Confirmed |
| D010 | ETH momentum untested | strategy | Suggestive |

**10 validated findings. 4 Confirmed. 3 Strong. 1 Moderate. 1 Suggestive.**

---

## Negative Knowledge — Failed Hypotheses (Do Not Retry Unless Condition Met)

Each entry records a dead-end to prevent repeated experiments.

### NEG001: Funding rate alone predicts reversals
- **Outcome**: Rejected
- **Reason**: Walk-forward PF = 0.81. Timing unreliable. 52% win rate with poor risk-adjusted returns.
- **Do not retry unless**: Funding is combined with OI divergence or price confirmation (see D004).

### NEG002: BTC Mean-Reversion without regime filter
- **Outcome**: Rejected
- **Reason**: Walk-forward PF = 0.90–1.10. Edge exists only during neutral/range-bound conditions.
- **Do not retry unless**: Strategy includes MTF regime gate that filters trending regimes (see D009).

### NEG003: Fixed percentage thresholds for mean-reversion
- **Outcome**: Rejected
- **Reason**: Regime-dependent performance. PF = 1.08 vs z-score PF = 1.35 in same conditions.
- **Do not retry unless**: Thresholds are regime-adaptive (see D003).

### NEG004: YTC Continuation on BTC 5m
- **Outcome**: Archived
- **Reason**: No persistent edge found. Hypothesis falsified across multiple experiments.
- **Do not retry unless**: New data reveals structural market change.

### NEG005: Fibonacci-based continuation patterns
- **Outcome**: Archived
- **Reason**: No economic mechanism. Purely pattern-based. Falsified.
- **Do not retry unless**: A testable economic theory of Fibonacci levels in crypto is proposed and validated.

### NEG006: VSA Capitulation patterns
- **Outcome**: Archived
- **Reason**: Volume spread analysis patterns not predictive after transaction costs.
- **Do not retry unless**: Combined with order flow confirmation (CVD, delta).

---

**10 validated findings + 6 negative-knowledge entries.**
