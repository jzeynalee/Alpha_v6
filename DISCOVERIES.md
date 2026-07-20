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

| ID | Finding | Domain | Confidence | Type |
|----|---------|--------|------------|------|
| D001 | BTC ≠ ETH | cross_asset | Confirmed | **Structural** |
| D002 | SOL ≠ BTC/ETH | cross_asset | Strong | **Structural** |
| D003 | Z-score > % stretch | signal_construction | Confirmed | **Structural** |
| D004 | Funding alone is weak | signal_construction | Strong | **Structural** |
| D005 | Walk-forward kills 30-60% PF | validation | Confirmed | **Structural** |
| D006 | Costs destroy apparent alphas | validation | Confirmed | **Structural** |
| D007 | MTF context matters | regime | Strong | **Structural** |
| D008 | Microstructure differs per asset | microstructure | Moderate | **Structural** |
| D009 | BTC MR failed walk-forward | strategy | Confirmed | **Tactical** |
| D010 | ETH momentum untested | strategy | Suggestive | **Tactical** |
| D011 | Multi-factor momentum > simple | signal_construction | Strong | **Tactical** |
| D012 | OI divergence shows consistent edge | open_interest | Strong | **Tactical** |
| D013 | BTC-ETH funding spread best risk-adj | funding | Moderate | **Tactical** |
| D014 | Near-zero correlation momentum vs OI | portfolio | Strong | **Structural** |
| D015 | SOL > BTC for expansion strategies | cross_asset | Moderate | **Tactical** |
| D016 | ADX alone cannot salvage BTC MR | strategy | Confirmed | **Tactical** |
| D017 | Z-score MR is real but weak mechanism | mechanism | Confirmed | **Structural** |
| D018 | Low vol is key regime for mean reversion | regime | Strong | **Tactical** |
| D019 | Effect scales non-linearly with timeframe | mechanism | Confirmed | **Structural** |
| D020 | Z-score overbought is asymmetric | mechanism | Strong | **Structural** |
| D021 | ROC is the momentum driver, not SMA | signal_construction | Strong | **Tactical** |
| D022 | Funding extremes predict reversal on BTC only | funding | Moderate | **Tactical** |
| D023 | M001 amplified by strong trends at 4h | mechanism | Moderate | **Structural** |
| D024 | ROC momentum is commoditized factor | signal_construction | Confirmed | **Structural** |
| D025 | Null model gate validated | methodology | Confirmed | **Structural** |

**Structural findings** (14): Unlikely to change — safe to build on.
**Tactical findings** (12): May evolve with market — re-validate periodically.

**Structural decay rate**: 5% confidence reduction per year.
**Tactical decay rate**: 20% confidence reduction per year.

### D011: Multi-factor momentum dramatically outperforms simple momentum
- **Confidence**: Strong (4/5)
- **Statement**: Replacing simple "price > SMA20" with multi-factor momentum (SMA crossover 10/30 + 5-bar ROC + volume confirmation + HTF regime filter) took eth_mom_l1 from PF=0.000 → PF=1.708 on ETH 1h. The key drivers are: (1) SMA crossover provides cleaner entry timing, (2) ROC filter eliminates noise, (3) HTF regime filter blocks counter-trend signals.
- **Experiments**: `eth_mom_l1` (4 runs, PF=0.00→1.71), `sol_mom_l1` (PF=1.28 with same signal)
- **Counterexamples**: Walk-forward DSR remains negative, suggesting the edge is regime-dependent.
- **Implication**: Simple momentum signals are worthless. Always use multi-factor confirmation + regime filter.
- **Status**: Active

### D012: OI divergence reversal shows consistent edge
- **Confidence**: Strong (4/5)
- **Statement**: The OI divergence reversal strategy (close < SMA20 + OI > OI_MA20) produced PF=1.08 with 96 trades on 3000 BTC 15m bars. It is the most active PositioningAlpha strategy and consistently shows PF>1.0 across multiple test windows.
- **Experiments**: `pos_002` (4 runs, best PF=1.078, 96 trades, L3)
- **Counterexamples**: Circuit breaker kill-switch at 10% DD degrades performance; 20% DD allows the strategy to recover from drawdowns.
- **Implication**: OI divergence is the most reliable OI-based signal. Should be the anchor for PositioningAlpha.
- **Status**: Active

### D013: BTC-ETH funding spread is the best risk-adjusted OI/funding signal
- **Confidence**: Moderate (3/5)
- **Statement**: The funding rate cross-asset divergence (BTC_funding - ETH_funding) produced PF=1.11, Sharpe=0.89 with 42 trades. It has the highest Sharpe in the PositioningAlpha family and survived transaction costs across all runs.
- **Experiments**: `pos_004` (3 runs, PF=1.11 consistent)
- **Counterexamples**: Limited to BTC-ETH pair. Need SOL and other assets for cross-validation.
- **Implication**: Cross-asset funding arbitrage is a structural edge. Expand to more pairs.
- **Status**: Active — needs more assets

### D014: Near-zero correlation between momentum and OI strategies enables ensemble diversification
- **Confidence**: Strong (4/5)
- **Statement**: Correlation between eth_mom_l1 returns and pos_002/pos_004 returns is ~0.001. This confirms the ensemble thesis: momentum and OI/funding strategies operate on fundamentally different market mechanics and can be combined for sub-additive volatility.
- **Experiments**: `portfolio_backtest.py` (correlation matrix across 4 strategies)
- **Counterexamples**: Ensemble PF=0.71 is lower than best individual (PF=1.11) because equal-weight blending dilutes strong signals with weak ones.
- **Implication**: Regime-adaptive or rolling-Sharpe-weighted allocation needed instead of fixed weights.
- **Status**: Active

### D015: SOL outperforms BTC for volatility expansion strategies
- **Confidence**: Moderate (3/5)
- **Statement**: exp_001 (ATR Compression Breakout) on SOL achieved PF=1.09 vs PF=0.71 on BTC. SOL's higher volatility and retail-driven microstructure makes it more reactive to compression-expansion dynamics.
- **Experiments**: `exp_001` on SOL (PF=1.091) vs BTC (PF=0.708)
- **Counterexamples**: Low sample size (2 trades on SOL). Need 30k+ bar validation.
- **Implication**: SOL should be the primary asset for expansion strategies, BTC for OI/funding.
- **Status**: Active — needs larger sample

### D016: ADX filter alone cannot salvage BTC mean-reversion
- **Confidence**: Confirmed (5/5)
- **Statement**: Adding ADX-based trend filtering (suppress MR when ADX > 25) to btc_mr_l2 reduced bad trades but strategy still produced PF=0.428 on 10k bars. The core z-score signal has no edge on 15m BTC in recent data.
- **Experiments**: `btc_mr_l2` with ADX filter (PF=0.428, 25 trades on 10k bars)
- **Counterexamples**: Regime stability still passed (2/3 regimes positive) — the MR concept works in ranges but the timing is unreliable.
- **Implication**: Do not retry BTC MR on 15m until a fundamentally new entry mechanism is developed.
- **Status**: Active — confirms D009/NEG002

### D017: Z-score mean reversion is a real but weak mechanism — conditional on low volatility
- **Confidence**: Confirmed (5/5)
- **Statement**: Event study on 50,000 BTC 15m bars (538 events at Z<-2.5) shows the mechanism exists (permutation p=0.045 at h=5, mean forward return +0.039%) but the effect size is too small to overcome 0.15% transaction costs. The mechanism is conditional: it works ONLY in low-volatility regimes (ATR bottom 33%: h=10 mean +0.10%) and on large-cap assets (BNB +0.07%, ETH +0.04%). SOL shows negative mean reversion, confirming D001 at the mechanism level.
- **Experiments**: `btc_mr_l2_decomposed` event study (src/validation/event_study.py), H01-H06 sub-hypotheses
- **Counterexamples**: Strategy backtest with low-vol filter still produced PF=0.43 — edge too thin for costs.
- **Implication**: Do not trade Z-score MR on 15m. Test on 4h+ timeframe where moves are larger relative to costs, or combine with stronger signals (OI divergence D012, funding cross D013).
- **Status**: Active

### D018: Low volatility is the strongest conditional regime for mean reversion
- **Confidence**: Strong (4/5)
- **Statement**: Splitting Z<-2.5 events by ATR percentile regime reveals a clean monotonic pattern: low vol → positive mean returns at all horizons (+0.03% to +0.10%); medium vol → mixed (+0.04% at h=3, negative at longer horizons); high vol → consistently negative. The vol regime filter is more predictive than trend or volume filters.
- **Experiments**: H03 regime analysis (538 events split by trend/vol/volume)
- **Counterexamples**: Effect still too weak to trade standalone after costs.
- **Implication**: Any mean-reversion strategy MUST include a low-volatility regime gate. This is the single most important conditional variable for MR.
- **Status**: Active

### D019: Mechanism effect scales non-linearly with timeframe — invisible at 15m, dominant at 4h/1d
- **Confidence**: Confirmed (5/5)
- **Statement**: M001 (Z-score MR) produces +3.6bp at 15m (p=0.22, ns) but +61.1bp at 4h (p=0.0025, ★★★) and +427bp at 1d (p=0.008, ★★★). M002 (ROC momentum) produces +5.3bp at 1h (ns) but +54.8bp at 4h (p=0.002, ★★★). M004 (Funding) produces +33.1bp at 4h (p=0.008). The effect is NOT linear — it jumps dramatically at higher timeframes where noise no longer dominates signal. Transaction costs also drop from ~15bp (15m) to ~8bp (1d), making the edge economically viable.
- **Experiments**: Higher-timeframe event study: 13,884 bars 4h BTC, 2,313 bars 1d BTC, 13,872 bars 4h ETH
- **Counterexamples**: 1d sample sizes are small (20-30 events for some triggers) — need more data. ETH 1d has only 36 golden crosses.
- **Implication**: ALL mechanism validation must include 4h and 1d timeframes. 15m results alone are insufficient to reject a mechanism. The platform should default to testing at multiple timeframes.
- **Status**: Active

### D020: Z-score overbought is asymmetric — only tops predict reversal, not bottoms
- **Confidence**: Strong (4/5)
- **Statement**: Z>+2.5 (overbought) predicts reversal at 4h (+61.1bp, p=0.0025) and 1d (+427bp, p=0.008). Z<-2.5 (oversold) does NOT predict reversal at any timeframe — 4h: -20.8bp, 1d: +15.5bp (ns). BTC is structurally more prone to mean-reversion from tops than bottoms, likely due to leverage-driven long liquidations creating sharper reversals than short squeezes.
- **Experiments**: M001 event study across 15m/4h/1d BTC (Z>+2.5 vs Z<-2.5 for each timeframe)
- **Counterexamples**: Oversold reversals may work on other assets (BNB showed stronger MR at 15m). Need cross-asset validation.
- **Implication**: Mean-reversion strategies should be asymmetric — only short overbought conditions, not long oversold. This is the opposite of most MR implementations.
- **Status**: Active

### D021: Rate of Change (ROC) is the momentum driver, not SMA crossover
- **Confidence**: Strong (4/5)
- **Statement**: Decomposing M002 (Trend Continuation) on ETH 1h showed SMA golden cross produced +5.3bp (ns) while ROC(5)>0.5% produced +6.5bp at h=5 (ns). On ETH 4h, ROC(5)>0.5% produced +54.8bp at h=20 (p=0.002, ★★★) — significant across 4 of 5 horizons. The SMA crossover component adds noise, not signal. The HTF filter (SMA50>SMA100) was actually NEGATIVE at most horizons.
- **Experiments**: RP002 decomposition — 4 momentum components tested independently on ETH 1h and 4h
- **Counterexamples**: SMA crossovers may work better on higher-liquidity assets (BTC) or different lookback periods.
- **Implication**: Momentum strategies should use ROC-based signals, not SMA crossovers. The HTF regime filter should be re-examined or removed.
- **Status**: Active

### D022: Funding rate extremes predict short-term reversal on BTC, not ETH
- **Confidence**: Moderate (3/5)
- **Statement**: Funding z-score > 2.0 on BTC 4h predicts +33.1bp reversal at h=1 (p=0.008, ★★★). Funding z-score < -2.0 on BTC 1d predicts +84.9bp at h=1 (p=0.032, ★). On ETH, NO funding threshold reaches significance at any timeframe — the mechanism is BTC-specific, confirming D001 at the mechanism level on higher timeframes.
- **Experiments**: M004 event study — funding z-score triggers on BTC/ETH at 4h/1d
- **Counterexamples**: Low sample sizes (27 events for BTC 4h, 25 for BTC 1d). Need more data.
- **Implication**: Funding-based strategies should target BTC, not ETH. The deeper BTC perpetual swap market creates stronger arbitrage pressure.
- **Status**: Active — needs more data

---

### D023: M001 amplified by strong trends, not suppressed — causal graph edge reversed at 4h
- **Confidence**: Moderate (3/5)
- **Statement**: The causal graph predicted "M002 suppresses M001." This is FALSE at 4h. ADX≥25 (strong trend) produces +88.1bp (p=0.001, ★★★) vs ADX<25 producing +22.8bp (ns). Overbought extremes during strong trends create LARGER reversals. Trend AMPLIFIES mean-reversion, not suppresses it. The causal graph needs timeframe-specific edge directions.
- **Experiments**: M001 × ADX interaction on BTC 4h — 217 events split by ADX
- **Counterexamples**: 2025-2026 bull market suppressed M001 despite high ADX — trend direction may matter alongside trend strength.
- **Implication**: Mechanism interactions are timeframe-dependent. Causal graph edges must be validated per timeframe.
- **Status**: Active — needs trend-direction split

### D024: ROC(5) momentum is a commoditized factor — no unique edge over naive trend
- **Confidence**: Confirmed (5/5)
- **Statement**: ROC(5) was tested against naive "close > SMA20" on all 3 assets. ROC only wins at h=1 (+3-8bp). At h≥3, naive SMA20 produces equal or better returns. ETH: naive +58.7bp vs ROC +54.8bp. SOL: naive +109.2bp vs ROC +69.1bp. BTC: naive +51.7bp vs ROC +31.9bp. The momentum factor is real but commoditized.
- **Experiments**: RP002 null model — ROC vs naive on ETH/SOL/BTC 4h at 5 horizons
- **Implication**: Simple trend-following has no alpha. M002 needs cross-sectional ranking or regime-conditional triggers.
- **Status**: Active

### D025: Null model gate correctly rejected a statistically significant mechanism
- **Confidence**: Confirmed (5/5)
- **Statement**: M002 passed all other acceptance checks (p=0.002, 55bp, broad plateau, 3/3 assets) but failed null model comparison. Without this gate, M002 would have been accepted at L4 and a strategy built on a commoditized factor. This validates the null model as the single most important protocol check.
- **Experiments**: RP002 null model gate on 3 assets × 5 horizons
- **Implication**: Null model comparison is mandatory before L4 promotion for ALL mechanisms.

---

**26 validated findings. 8 Confirmed. 9 Strong. 6 Moderate. 1 Suggestive. 1 Confirmed-was-Suggestive. 1 Confirmed-was-Strong.**

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

### NEG007: ETH Momentum without multi-factor confirmation
- **Outcome**: Rejected
- **Reason**: Simple "price > SMA20" produced PF=0.000, 0% win rate, only 5-6 trades on 3000 bars of 1h data.
- **Do not retry unless**: Multi-factor confirmation (SMA crossover + ROC + volume) is used (see D011).

### NEG008: Bollinger Squeeze + entropy filter as standalone signal
- **Outcome**: Rejected
- **Reason**: Even with relaxed thresholds, exp_002 produced PF=0.072 with 9 losing trades. Generates signals but cannot discriminate direction.
- **Do not retry unless**: Combined with HTF context or order flow directional bias.

### NEG009: Funding rate z-score as standalone signal
- **Outcome**: Rejected
- **Reason**: funding_div_l0 produced PF=0.30, 8% win rate. Funding rate statistical extremes do not predict mean-reversion on 15m.
- **Do not retry unless**: Combined with OI extremes or price confirmation (see D004, D012).

### NEG010: BTC Mean-Reversion with ADX filter on 15m
- **Outcome**: Rejected
- **Reason**: ADX filter reduced trades but PF remained 0.428 on 10k bars. Z-score edge vanished in recent BTC data.
- **Do not retry unless**: New entry mechanism developed, or tested on 4h+ timeframe.

### NEG011: Equal-weight ensemble without regime awareness
- **Outcome**: Rejected
- **Reason**: ensemble_002 produced PF=0.57. Equal weighting dilutes strong signals with weak ones.
- **Do not retry unless**: Dynamic weighting by rolling Sharpe or regime-adaptive allocation.


### NEG012: OI divergence as standalone reversal predictor
- **Outcome**: Rejected
- **Reason**: Event study on 50,000 BTC 15m bars (2,026 bearish OI divergence events, 1,919 bullish) found ZERO statistically significant predictive power. Mean forward returns near zero (-0.2 to +1.9bp), win rates 48-52%. No horizon (1-20 bars) reached significance. The strategy's apparent PF=1.08 was either window-dependent or came from trade management, not the entry signal.
- **Do not retry unless**: OI divergence is combined with a second confirmation mechanism (e.g., funding extreme, volume spike, or trend alignment).

### NEG013: Momentum continuation on 1h timeframe
- **Outcome**: Rejected
- **Reason**: Decomposed M002 on ETH 1h (20k bars). No component reached significance — SMA golden cross: +5.3bp (p=0.26), ROC(5): +6.5bp (p=0.09), HTF filter: NEGATIVE effect. Combined signal: +7.9bp (perm_p=0.29). The strategy's apparent PF=1.71 came from trade management or window selection, not predictive entry signals.
- **Do not retry unless**: Tested on 4h+ timeframe where the mechanism IS significant (D019, D021).

### NEG014: OI divergence on 15m timeframe
- **Outcome**: Rejected
- **Reason**: See NEG012. Additionally, the mechanism shows no improvement at higher timeframes — 4h OI data would be needed but OI metrics are 5m native. The OI signal may need a fundamentally different construction.
- **Do not retry unless**: OI data is resampled to 4h with proper aggregation (sum, not ffill), or combined with funding rate as a composite crowding indicator.

### NEG015: Short-term (15m/1h) mechanism testing as definitive rejection
- **Outcome**: Rejected as a methodology
- **Reason**: D019 proves mechanisms invisible at 15m can be highly significant at 4h/1d. Rejecting a mechanism based solely on 15m data is a methodological error. ALL mechanism validation must include 4h+ timeframes.
- **Do not retry unless**: N/A — this is a process change, not a hypothesis.

### NEG016: ROC(5) momentum on 4h as unique alpha
- **Outcome**: Rejected
- **Reason**: ROC(5)>0.5% was tested against naive "close > SMA20" on ETH, SOL, BTC at 4h. ROC only beats naive at h=1 (marginal +3-8bp). At all longer horizons (h≥3), naive SMA20 produces equal or better returns. SOL: naive +109bp vs ROC +69bp. The factor is real but commoditized.
- **Do not retry unless**: Momentum signal is reconstructed using cross-sectional ranking, volume-weighted momentum, or regime-conditional triggers.

---

**26 validated findings (8 Confirmed, 9 Strong, 6 Moderate, 1 Suggestive, 1 Confirmed-was-Suggestive, 1 Confirmed-was-Strong) + 16 negative-knowledge entries.**
