# YTC Phase 1 Conclusion & Phase 2 Research Plan

**Date**: 2026-06-23 | **Author**: YTC Research Team
**Data**: BTCUSDT 5m, 100,000 bars | **Period**: 2023–2026

---

## 1. What Phase 1 Accomplished

The YTC project set out to build an auction-market-theory trading algorithm with five layers:

1. Market Structure (swing points, SR zones)
2. Auction State (Balance / Imbalance / Transition)
3. Trend Quality (continuous 0–100 score)
4. Volatility Regime (Compression / Normal / Expansion)
5. Execution & Setup Selection (Pullback, Continuation Pullback, Failed Auction)

Phase 1 produced a clean, well-architected codebase (v1.0 → v1.2) with:
- Public API for all engines
- Parameter versioning for experiment reproducibility
- Per-bar CSV/JSON diagnostic export
- Setup-level isolation (`disabled_setups`)
- Three-attribution backtest pipeline (PB Only / FA Only / PB+FA)

**Phase 1 also produced a rigorous hypothesis-testing framework** that subjected every YTC assumption to statistical scrutiny. This is the most valuable output of the project.

---

## 2. The Core Hypothesis — Falsified

**Original hypothesis**:

> Auction states (Imbalance), pullback entries at Fibonacci retracement depths (0.30–0.65), and failed auctions predict directional continuations on BTCUSDT 5m.

**Result**: **Falsified.**

Six experiments were run against 100,000 bars of BTCUSDT 5m data. The evidence is unambiguous.

---

## 3. Five Findings

### Finding 1: PB Is Systematically Anti-Predictive

The Pullback signal points the wrong direction at every horizon beyond 1 bar.

| Horizon | Original Acc% | Reversed Acc% | Winner |
|---------|--------------|---------------|--------|
| 1-bar   | 49.5%        | 50.3%         | ~TIE   |
| 5-bar   | 47.1%        | **52.8%**     | REVERSED |
| 10-bar  | 48.5%        | **51.5%**     | REVERSED |
| 20-bar  | 47.5%        | **52.5%**     | REVERSED |
| 50-bar  | 46.2%        | **53.8%**     | REVERSED |

**Interpretation**: The PB model assumes pullback → continuation. The data says pullback → mean reversion. This is not noise — it persists across 5, 10, 20, and 50-bar horizons.

---

### Finding 2: FA_Bear Is the Strongest Negative Signal

| Horizon | Original Acc% | Original μ(ATR) | Reversed Acc% | Reversed μ(ATR) |
|---------|--------------|-----------------|--------------|-----------------|
| 1-bar   | 45.7%        | −0.095          | 54.3%        | +0.095          |
| 5-bar   | 37.6%        | −0.238          | 62.4%        | +0.238          |
| 20-bar  | 37.0%        | −0.349          | 63.0%        | +0.349          |
| 50-bar  | 32.4%        | −0.820          | **67.6%**    | **+0.820**      |

Reversed FA_Bear at 50-bar: 67.6% accuracy, +0.820 ATR mean return, p = 0.018.

**Interpretation**: This is either a false definition of "failed auction" or an accidentally discovered bullish continuation pattern labeled as bearish. Either way, it is the single strongest signal in the entire study.

---

### Finding 3: The Depth Filter Selects the Wrong Buckets

| Depth Bucket | Count | 20-bar μ(ATR) |
|-------------|-------|---------------|
| 0.0–0.2     | 3,114 | **+0.287**    |
| 0.2–0.4     | 3,086 | +0.164        |
| 0.4–0.6     | 1,135 | +0.149        |
| 0.6–0.8     | 574   | **+0.425**    |
| 0.8–1.0     | 0     | —             |

The current PB depth filter (0.30–0.65):
- **Includes** the weakest bucket (0.4–0.6: +0.149 ATR)
- **Excludes** the two best buckets (0.0–0.2: +0.287 ATR; 0.6–0.8: +0.425 ATR)

**Interpretation**: The Fibonacci retracement zone (0.38–0.62) is a trap on BTCUSDT 5m. Extreme retracements — both shallow (strength) and deep (capitulation/exhaustion) — perform best.

---

### Finding 4: The Alignment Filter Destroys Signal Quality

| Stage | Candidates | 20-bar μ(ATR) |
|-------|-----------|---------------|
| Pre-alignment PB (raw) | 48 | **+0.746** |
| Post-alignment PB (filtered) | 1,799 | **−0.113** |

The alignment filter expands the signal count 37× (48 → 1,799) while flipping the mean return from +0.746 ATR to −0.113 ATR.

**Interpretation**: The sophisticated machinery — Auction State scoring, Trend Quality scoring, Volatility Regime scoring, SR Location scoring — is not improving signals. It is destroying them. The filter is anti-selective.

---

### Finding 5: Failed Auction Is Not a Special Event

| Metric | Count | % of Bars |
|--------|-------|-----------|
| Bars with any SR zone | 99,800 | 100.0% |
| Bars meeting FA criteria (0.5× ATR break) | 80,730 | **80.9%** |
| Actual FA signals (post-alignment) | 387 | 0.4% |

80.9% of all bars qualify as Failed Auction candidates. A genuine FA should be rare (≤ 2%).

**Interpretation**: The current FA definition does not isolate anything. The 0.5× ATR break threshold produces zero reduction from the old "any zone touch" definition. The concept needs a fundamental redesign, not calibration.

---

## 4. What This Means

### It does NOT mean: "No edge exists."

It means: **The assumed direction of the edge is wrong.**

The results are not random. They are **consistently wrong** — which indicates a repeatable market behavior on BTCUSDT 5m:

```
pullback → mean reversion (not continuation)
```

Consistently wrong is closer to a tradable edge than random, because it means the market is doing something repeatable — just the opposite of what the model predicts.

---

## 5. Backtest Confirmation

Three attribution backtests on 50,000 bars confirm the signal failure at the trade level:

| System | Trades | Win% | PF | Sharpe | Return | DD% |
|--------|--------|------|-----|--------|--------|-----|
| PB Only | 47 | 23.4% | 0.34 | −6.90 | −14.0% | −14.0% |
| FA Only | 30 | 23.3% | 0.30 | −7.91 | −12.6% | −12.6% |
| PB + FA | 48 | 22.9% | 0.40 | −6.12 | −14.3% | −14.3% |

All systems lose money. PF < 0.5 across every configuration. No diversification benefit from combining setups.

---

## 6. What to Abandon (For Now)

These components have failed to demonstrate value and should not consume further research time:

| Component | Reason |
|-----------|--------|
| ❌ Auction State scoring in alignment | Destroyed signal quality |
| ❌ Trend Quality scoring in alignment | Destroyed signal quality |
| ❌ Alignment Score (entire framework) | Anti-selective |
| ❌ Failed Auction detection | 80.9% prevalence — detects nothing |
| ❌ Continuation Pullback (CPB) | 27–32 signals / 100k bars — effectively dead |

Not forever. They may prove useful in other contexts. But they have no place in the next phase of pullback research.

---

## 7. Phase 2 Research Plan

### Research Track A: Reverse PB (Highest Priority)

**Hypothesis**: The PB signal is anti-predictive. Flipping the direction produces positive expectancy.

**Definition**:
```
Current PB Long  → Short
Current PB Short → Long
```

Everything else unchanged: same depth filter, same stop/target logic, same risk management.

**Success criteria**: PF > 1.0, positive expectancy, survives walk-forward split.

---

### Research Track B: Raw PB Without Alignment

**Hypothesis**: Pre-alignment PB candidates (+0.746 ATR at 20-bar) represent a genuine edge that the alignment filter destroyed.

**Definition**:
- Remove Auction State, Trend Quality, Alignment Score from the signal path.
- Keep only: Market Structure + Depth.
- Test all five depth buckets independently.

**Depth bucket test matrix**:

| Bucket | Test | Hypothesis |
|--------|------|------------|
| 0.0–0.2 | Yes | Extreme strength continuation |
| 0.2–0.4 | Yes | Moderate continuation |
| 0.4–0.6 | Yes | Indecision zone (expected weakest) |
| 0.6–0.8 | Yes | Capitulation / exhaustion reversal |
| 0.8–1.0 | Yes | Extreme exhaustion (low sample) |

**Success criteria**: At least one bucket with PF > 1.0 and > 50 signals.

---

### Research Track C: Regime Segmentation

**Hypothesis**: Pullback behavior differs by market regime (bull / bear / sideways).

**Action**: Replace the SMA50 slope classifier (95% Sideways) with a more discriminating regime detector (e.g., price vs SMA200, rolling regression slope).

**Then**: Re-run depth-bucket analysis segmented by regime.

---

### Research Track D: Walk-Forward Validation

**Hypothesis**: Any edge discovered in Tracks A–C survives out-of-sample.

**Action**: Split data into train/validation/test periods. Optimize on train, confirm on validation, report on test.

---

### Research Track E: Multi-Asset Validation

**Hypothesis**: Pullback behavior generalizes beyond BTCUSDT.

**Action**: If any strategy survives walk-forward, test on ETHUSDT and SOLUSDT 5m.

---

## 8. Phase 2 Research Sequence

```
Week 1:  Track A — Reverse PB strategy
Week 2:  Track B — Raw PB + depth buckets
Week 3:  Track C — Regime segmentation
Week 4:  Track D — Walk-forward validation
Week 5+: Track E — Multi-asset validation
```

Each track gates the next. If Reverse PB shows PF < 1.0, revisit the approach before proceeding.

---

## 9. Entry Criteria for Returning to Architecture Work

Only return to building new indicators, state machines, or alignment frameworks if:

1. **Reverse PB or Raw PB produces PF > 1.3** in walk-forward testing on BTCUSDT 5m.
2. **The edge is not explainable by a single known factor** (momentum, mean reversion, volatility).
3. **The edge persists across at least two assets.**

Until then: **no new architecture. No new indicators. No ML. No state machines.** Just rigorous hypothesis testing of the simplest possible pullback variants.

---

## 10. Final Assessment

The YTC project did not produce a profitable trading strategy.

It produced something more valuable: **falsified hypotheses with clear data about where the truth might lie.**

The most important finding is not that a specific threshold was wrong. It is that the market on BTCUSDT 5m appears to mean-revert after pullbacks, not continue. The entire model's directional assumption was inverted.

If Reverse PB produces PF > 1.0, Phase 2 will have converted a falsified hypothesis into a tradable edge — which is exactly how quantitative research should work.

---

*End of Phase 1. Phase 2 begins with Research Track A: Reverse PB.*
