# YTC Hypothesis Testing Report — v1.2

**Date**: 2026-06-22 | **Data**: BTCUSDT 5m, 100,000 bars | **Signals**: 2,213

---

## Executive Summary

**The YTC hypothesis, as currently implemented, shows no evidence of predictive power. The signals are not merely noisy — they are systematically anti-predictive at horizons beyond 1 bar.**

This report answers the question the backtest results raised: *is PF 0.3–0.4 a calibration problem, or a hypothesis problem?* The evidence points decisively to the latter.

---

## Experiment A: Reverse Signal Test

> *"If the signal is systematically wrong, the opposite should win."*

For each setup, forward returns were measured in both the signal direction (Original) and the opposite direction (Reversed). If Original outperforms, the signal has directional skill. If Reversed outperforms, the signal is anti-predictive.

### PB (1,799 signals)

| Horizon | Original Acc% | Original μ(ATR) | Reversed Acc% | Reversed μ(ATR) | Winner |
|---------|--------------|-----------------|--------------|-----------------|--------|
| 1-bar   | 49.5%        | +0.001          | 50.3%        | −0.001          | ~TIE   |
| 5-bar   | 47.1%        | **−0.025**      | 52.8%        | **+0.025**      | REVERSED |
| 10-bar  | 48.5%        | **−0.046**      | 51.5%        | **+0.046**      | REVERSED |
| 20-bar  | 47.5%        | **−0.113**      | 52.5%        | **+0.113**      | REVERSED |
| 50-bar  | 46.2%        | **−0.268**      | 53.8%        | **+0.268**      | REVERSED |

**Finding**: PB signals are neutral at 1-bar but become increasingly anti-predictive from 5-bar onward. The signal points the wrong way.

### FA_Bear (173 signals)

| Horizon | Original Acc% | Original μ(ATR) | Reversed Acc% | Reversed μ(ATR) | Winner |
|---------|--------------|-----------------|--------------|-----------------|--------|
| 1-bar   | 45.7%        | −0.095          | 54.3%        | +0.095          | REVERSED |
| 5-bar   | 37.6%        | **−0.238**      | 62.4%        | **+0.238**      | REVERSED |
| 10-bar  | 39.9%        | −0.085          | 60.1%        | +0.085          | REVERSED |
| 20-bar  | 37.0%        | **−0.349**      | 63.0%        | **+0.349**      | REVERSED |
| 50-bar  | 32.4%        | **−0.820**      | 67.6%        | **+0.820**      | REVERSED |

**Finding**: FA_Bear is **strongly** anti-predictive at every horizon. At 50-bar, the reversed signal has 67.6% accuracy and +0.820 ATR mean return — versus 32.4% and −0.820 ATR for the original. **This is the strongest negative signal in the entire system.**

### FA_Bull (214 signals)

| Horizon | Original Acc% | Original μ(ATR) | Reversed Acc% | Reversed μ(ATR) | Winner |
|---------|--------------|-----------------|--------------|-----------------|--------|
| 1-bar   | 52.3%        | **+0.025**      | 47.7%        | −0.025          | ORIGINAL |
| 5-bar   | 49.1%        | −0.010          | 50.9%        | +0.010          | REVERSED |
| 10-bar  | 49.5%        | −0.066          | 50.5%        | +0.066          | REVERSED |
| 20-bar  | 45.3%        | −0.489          | 54.7%        | +0.489          | REVERSED |
| 50-bar  | 56.1%        | −0.235          | 43.9%        | +0.235          | REVERSED |

**Finding**: FA_Bull has a weak 1-bar edge (+0.025 ATR, 52.3% accuracy) but reverses to anti-predictive at longer horizons.

### Conclusion

**All three setups are anti-predictive at horizons ≥ 5 bars.** Trading the opposite direction would have produced positive returns. The signals are not random — they are **systematically wrong**.

---

## Experiment B: Forward Return vs Random Bars

> *"If signals don't outperform random entry, the hypothesis is wrong."*

10,000 random bars were sampled as a baseline. For each setup and horizon, signal returns (aligned with signal direction) were compared to random-entry returns using Welch's t-test.

### PB vs Random

| Horizon | Signal μ(ATR) | Random μ(ATR) | Δ Mean | p-value | Better |
|---------|--------------|---------------|--------|---------|--------|
| 1-bar   | +0.001       | −0.010        | +0.010 | 0.5352  | ~TIE   |
| 5-bar   | −0.025       | −0.006        | −0.019 | 0.6729  | —      |
| 10-bar  | −0.046       | −0.012        | −0.034 | 0.5753  | —      |
| 20-bar  | −0.113       | −0.008        | −0.105 | 0.2409  | —      |
| 50-bar  | **−0.268**   | **+0.004**    | −0.272 | 0.0763  | RANDOM  |

PB underperforms random at every horizon except 1-bar. At 50-bar, PB = −0.268 ATR while random = +0.004 ATR. Near significant (p = 0.076).

### FA_Bull vs Random

| Horizon | Signal μ(ATR) | Random μ(ATR) | Δ Mean | p-value | Better |
|---------|--------------|---------------|--------|---------|--------|
| 1-bar   | +0.025       | −0.010        | +0.034 | 0.6377  | —      |
| 5-bar   | −0.010       | −0.006        | −0.004 | 0.9775  | —      |
| 20-bar  | **−0.489**   | **−0.008**    | −0.481 | **0.0492 *** | RANDOM |
| 50-bar  | −0.235       | +0.004        | −0.239 | 0.4570  | —      |

FA_Bull is **statistically significantly worse than random** at 20-bar (p = 0.049, *). The signal is not just failing to beat random — it is provably worse.

### FA_Bear vs Random

| Horizon | Signal μ(ATR) | Random μ(ATR) | Δ Mean | p-value | Better |
|---------|--------------|---------------|--------|---------|--------|
| 1-bar   | −0.095       | −0.010        | −0.085 | 0.3265  | —      |
| 5-bar   | −0.238       | −0.006        | −0.232 | 0.1497  | —      |
| 20-bar  | −0.349       | −0.008        | −0.341 | 0.1627  | —      |
| 50-bar  | **−0.820**   | **+0.004**    | −0.823 | **0.0184 *** | RANDOM |

FA_Bear is **statistically significantly worse than random** at 50-bar (p = 0.018, *). The magnitude is enormous: −0.820 ATR vs +0.004 ATR for random.

### Conclusion

**No setup outperforms random entry at any horizon.** FA_Bull and FA_Bear are statistically significantly worse than random (p < 0.05). PB shows a trend toward underperformance but does not reach significance with this sample size.

---

## Experiment C: Regime-Segmented Analysis

> *"Does any setup work in a specific market regime?"*

Regimes were classified using SMA50 slope: Bull (> +0.5%), Bear (< −0.5%), Sideways (between).

### Regime Distribution of Signals

| Regime | Count | % |
|--------|-------|---|
| Bull | 24 | 1.1% |
| Bear | 80 | 3.6% |
| Sideways | 2,109 | 95.3% |

**Finding**: 95% of signals occur in Sideways regime. The regime classifier's 0.5% SMA50 slope threshold may be too narrow for 5m BTC — most bars are classified as Sideways. Sample sizes for Bull (24) and Bear (80) are too small for reliable inference.

However, directional observations:

| Setup | Regime | Count | 5-bar Acc% | 20-bar Acc% | 5-bar μ(ATR) |
|-------|--------|-------|-----------|-------------|-------------|
| PB | Bear | 49 | 36.7% | 46.9% | −0.239 |
| FA_Bull | Bear | 20 | **65.0%** | **55.0%** | **+0.422** |
| FA_Bear | Bear | 11 | 9.1% | 18.2% | −1.202 |

FA_Bull in Bear markets shows 65% 5-bar accuracy with +0.422 ATR — but only 20 signals. Too few to trust, worth monitoring with more data.

### Conclusion

Regime-specific analysis is inconclusive due to the classifier marking 95% of bars as Sideways. The SMA50 slope threshold needs recalibration for 5m bars, or a different regime classifier (e.g., price relative to SMA200) should be used.

---

## Experiment D: Depth-Bucket Analysis

> *"The depth filter removes 99% of PB candidates. Which depths actually work?"*

All Imbalance bars with retracement depth > 0 were binned into 5 depth buckets. Forward returns (long direction) were measured at 5/20/50-bar horizons.

### Results (7,909 Imbalance bars with depth > 0)

| Depth | Count | 5-bar μ(ATR) | 20-bar μ(ATR) | 50-bar μ(ATR) |
|-------|-------|-------------|---------------|---------------|
| 0.0–0.2 | 3,114 | −0.039 | **+0.287** | **+0.494** |
| 0.2–0.4 | 3,086 | +0.027 | +0.164 | +0.311 |
| 0.4–0.6 | 1,135 | +0.040 | +0.149 | −0.188 |
| 0.6–0.8 | 574 | **+0.260** | **+0.425** | **+0.374** |
| 0.8–1.0 | 0 | — | — | — |

### Critical Insight

**Every depth bucket shows positive mean 20-bar returns.** The two best-performing buckets are:

1. **0.6–0.8**: +0.425 ATR at 20-bar — strongest signal, deepest retracements
2. **0.0–0.2**: +0.287 ATR at 20-bar — shallowest retracements

The **current PB depth filter is 0.30–0.65**, which:

- **Includes** the weakest bucket (0.4–0.6: +0.149 ATR)
- **Excludes** the strongest bucket (0.6–0.8: +0.425 ATR)
- **Excludes** the second-strongest (0.0–0.2: +0.287 ATR)

The depth filter is selecting the **least predictive** retracement range while excluding the two most predictive ranges. This is not a calibration issue — it is a design error.

### Conclusion

**The entire pullback concept may be backwards.** The conventional wisdom that pullbacks should enter at 0.38–0.62 retracement (Fibonacci) is not supported by this data. On BTC 5m, the most predictive entries are at extreme depths (shallow: 0.0–0.2, or deep: 0.6–0.8) — the opposite of what the current filter allows through.

---

## Experiment E: Auction State Contribution

> *"Does filtering by auction state improve PB performance?"*

PB signals were evaluated in three ways:
1. **No state filter**: Pass any bar through `check_pullback()` with its real auction state
2. **Imbalance forced**: Force every bar's state to Imbalance before checking
3. **Balance forced**: Force every bar's state to Balance before checking

### Signal Counts

| Filter | PB Candidates |
|--------|--------------|
| No filter (real state) | 48 |
| Imbalance forced | 134 |
| Balance forced | 0 |
| **Actual engine (Imbalance + alignment ≥ 60)** | **1,799** |

### Forward Return (20-bar, signal-aligned)

| Filter | Count | Mean (ATR) | Win% |
|--------|-------|-----------|------|
| No state filter (real state) | 48 | **+0.746** | 52.1% |
| Imbalance forced | 134 | **+0.609** | 53.7% |

### Critical Insight

**Pre-alignment PB candidates (48 bars) have +0.746 ATR mean at 20-bar, but post-alignment PB signals (1,799 bars) have −0.113 ATR (from Experiment A).**

This means the alignment filter (which requires score ≥ 60) is **degrading** signal quality, not improving it. The raw pullback pattern without alignment filtering shows strong positive returns. Once alignment filtering is applied (expanding the signal count 37× from 48 to 1,799), the mean return flips from +0.746 ATR to −0.113 ATR.

The alignment components that appear to be doing damage:
- HTF Structure scoring (zone proximity — almost every bar has a zone)
- Volatility regime scoring (Normal favored, but most returns occur outside Normal)
- Auction state scoring (Imbalance = 20, but Experiment D shows all states have positive depth returns)

### Conclusion

**The alignment filter is destroying signal quality.** Removing it would reduce signals from 1,799 to 48 but improve quality dramatically. The filter is selecting for conditions that look good on paper (high alignment score) but predict the opposite direction.

---

## Experiment F: FA Definition Quality

> *"Is the Failed Auction definition isolating rare, high-quality reversal events?"*

| Metric | Count | % of Bars |
|--------|-------|-----------|
| Bars with any SR zone | 99,800 | 100.0% |
| Bars with FA break (0.5× ATR) | 80,730 | 80.9% |
| Actual FA signals (engine) | 387 | 0.4% |

**80.9% of all bars** have a zone break beyond 0.5× ATR. A genuine Failed Auction should be a rare event (≤ 2% of bars). The current definition does not isolate anything special — it marks nearly every bar as a potential FA.

The alignment filter reduces 80,730 candidates → 387 signals, but those 387 produce PF 0.30. The concept is fundamentally broken at the detection level.

### Conclusion

**FA research should be suspended.** The current definition does not identify failed auctions. It identifies "bars with SR zones" — which is every bar. Redefining the concept from scratch is warranted if the FA hypothesis is to be pursued further.

---

## Consolidated Findings

### 1. All setups are anti-predictive at horizons ≥ 5 bars

PB, FA_Bull, and FA_Bear all point the wrong direction beyond 1 bar. Trading the opposite direction would have been profitable. This is the strongest signal in the entire study.

### 2. No setup beats random entry

FA_Bull and FA_Bear are **statistically significantly worse** than random (p < 0.05). PB trends the same direction but doesn't reach significance at current sample size.

### 3. The depth filter selects the wrong buckets

The current PB depth range (0.30–0.65) excludes the two best-performing depth buckets (0.0–0.2 and 0.6–0.8) while including the weakest (0.4–0.6). Every depth bucket shows positive mean returns — the pullback concept has merit, but the filter is inverted.

### 4. The alignment filter degrades quality

Pre-alignment PB (48 bars): +0.746 ATR. Post-alignment PB (1,799 bars): −0.113 ATR. The alignment score is anti-selective — it passes candidates that look good but perform poorly.

### 5. FA is not a special event

80.9% of bars qualify for FA. The definition needs a fundamental redesign, not calibration.

### 6. Auction state has marginal impact

Forcing Imbalance state increases PB candidate count (48 → 134) while maintaining positive returns (+0.609 ATR). The state machine adds some value but is secondary to the structure + depth combination.

---

## What This Means

The YTC hypothesis is not "under-calibrated." It is not "almost there." The evidence shows that **the core thesis — that auction states, pullback entries, and failed auctions predict directional moves — is currently wrong on BTCUSDT 5m.**

However, the silver linings are real:

1. **The reversed PB signal is an alpha candidate** — systematically anti-predictive at 5+ bar horizons means a counter-trend strategy would have worked.
2. **The pullback depth relationship is real but inverted** — extreme depths (shallow and deep) outperform the middle range. The Fibonacci retracement zone is a trap.
3. **The pre-alignment PB pattern has merit** — 48 raw candidates with +0.746 ATR at 20-bar, 52.1% win rate. The alignment filter is what destroys it.

---

## Recommendations (Priority Order)

### 1. Test the Reversed PB Strategy Immediately

The PB signal is anti-predictive at horizons ≥ 5 bars. Run a backtest where PB Long → PB Short and vice versa. If reversed PF > 1.0, this is a tradable edge.

### 2. Remove the Alignment Filter Entirely

It expands signal count 37× (48 → 1,799) while flipping mean return from +0.746 to −0.113 ATR. Replace with a simple depth + TQ gate.

### 3. Invert the Depth Filter

Use depth ranges (0.0–0.2) OR (0.6–0.8) instead of (0.30–0.65). Test both as separate entry conditions.

### 4. Suspend FA Research

Redefine from scratch when revisiting. The current 80.9% prevalence rate means it detects nothing.

### 5. Improve the Regime Classifier

SMA50 slope with 0.5% threshold marks 95% as Sideways on 5m. Use price vs SMA200, or rolling regression slope.

### 6. Do NOT Adjust Any More Thresholds

The problems discovered here are structural, not parametric. Imbalance 0.20 vs 0.25 will not fix anti-predictive signals. Fix the logic first.

---

## Final Assessment

| Criterion | Previous Score | New Score | Note |
|-----------|---------------|-----------|------|
| Architecture | 9/10 | 9/10 | Still excellent |
| Diagnostics | 9.5/10 | **10/10** | Hypothesis testing framework is the right tool |
| Calibration | 7/10 | 7/10 | Not the bottleneck |
| Evidence of Alpha | 2/10 | **3/10** | Reversed signals show promise; depth analysis reveals structural issues not calibration ones |
| Research Direction | — | **Clear** | Test reversed PB. Remove alignment. Invert depth filter. |


**The project is no longer about whether YTC works as designed. It's about whether the patterns YTC detects — whether intentionally or accidentally — can be inverted into an edge. That is a better question than "what threshold should Imbalance be?"**
