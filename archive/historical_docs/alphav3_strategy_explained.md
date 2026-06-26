# Alpha V3 — How the strategy works, step by step

*A plain-language walkthrough of the live signal path: the six-layer `alpha_factory` pipeline and the `deter_alpha` confirmation gate. Written to be read top to bottom by someone who knows trading but hasn't memorised the codebase.*

---

## The one-sentence version

Alpha V3 is **one strategy with two cooperating halves**: `alpha_factory` produces a machine-learning alpha signal through six sequential layers, and `deter_alpha` independently re-derives a yes/no directional opinion from causal feature analysis — and a trade fires only when *both* agree on direction and strength. It is a refinery, not a generator: every layer's job is to take a candidate signal and either sharpen it or kill it. Nothing in the pipeline invents edge; the layers exist to avoid trading when the edge isn't there.

That design is also its central risk, which is worth stating up front: a stack of multiplicative gates can attenuate a real-but-weak signal down to zero. Keep that in mind as you read — almost every layer below *multiplies* or *zeroes* the signal rather than adding to it.

---

## The two halves at a glance

```
                    ┌─────────────────────────────────────────┐
   OHLCV + DOM ───► │            alpha_factory                 │
                    │  (six layers, ML alpha generation)       │
                    │                                          │
                    │  L1 Market Structure  → regime, swings   │
                    │  L2 Feature Evidence  → calibrated E      │
                    │  L3 Causal Stability  → CSS gate         │
                    │  L4 Adaptive Decision → α_final (the ML) │
                    │  L5 Survival Gate     → offline DSR/IR   │
                    │  L6 Strategy Repo     → lifecycle/kill   │
                    └───────────────┬──────────────────────────┘
                                    │ proba_alpha, proba_direction
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │            deter_alpha                   │
                    │  (eight steps, deterministic gate)       │
                    │                                          │
                    │  Swing → Region → FeatureEval →          │
                    │  CausalSets → DeterministicFilter →      │
                    │  (ML proba) → FinalGate → LiveAdapt      │
                    └───────────────┬──────────────────────────┘
                                    │ final_decision ∈ {+1, 0, -1}
                                    ▼
                              RiskManager → order
```

`alpha_factory` is the brain; `deter_alpha` is the second opinion that has veto power. A signal that the ML loves but the causal gate distrusts does not trade.

---

# Part 1 — `alpha_factory`: the six-layer ML pipeline

The entry point is `AlphaFactory.compute_alpha(...)`. It runs the layers in sequence, threading the output of each into the next. Here is what each layer does and — crucially — *how it can suppress the signal*.

## Layer 1 — Market Structure Engine

**What it does**: builds the market's structural context. Two sub-parts:

- **Swing detection** (`AdaptiveSwingDetector`): identifies swing highs and lows using an ATR-gated rule. A swing is only confirmed after `min_confirm_bars` (default 3) and a violation of `1.5 × N` ATR. This produces the HH / HL / LH / LL structure (higher-high, higher-low, etc.) that tells you whether price is making progress or chopping.
- **Regime inference** (HMM): a 3-state Gaussian hidden Markov model labels each bar as Bull / Bear / Neutral, and — importantly — emits a **regime entropy**, a measure of how *uncertain* that label is. High entropy means "the model can't tell what regime we're in."

**What flows out**: a regime label, the swing structure, and the regime entropy scalar.

**How it suppresses signal**: indirectly. The regime label decides which calibrators and causal tables downstream layers use (so a wrong regime routes you to the wrong evidence), and the entropy feeds Layer 4's uncertainty discount (below). The HMM is also where regime *fragmentation* happens — if one regime (e.g. Bear) is rare in training, its per-regime statistics are starved, which silently weakens everything conditioned on it.

## Layer 2 — Feature Evidence Layer

**What it does**: turns raw features into a calibrated evidence vector `E`. The five feature groups are `["momentum", "structure", "volume", "pullback", "xtf"]`. For each feature, in each regime, an **isotonic calibrator** maps the raw feature value to a probability-like evidence score. Calibration is fitted offline on a purged training set (minimum 500 samples per feature×regime pair).

**What flows out**: a 5-element evidence vector `E`, one calibrated score per feature group.

**How it suppresses signal**: this is where the project's central empirical finding lives. When we retrained the calibrators, **Brier ≈ 0.25 across all feature×regime pairs** — which is exactly the Brier score of a coin flip. That means the individual features, on their own, don't predict next-bar direction. It does *not* prove the whole strategy has no edge (the downstream layers train on triple-barrier outcomes, not next-bar direction), but it does mean Layer 2 is not contributing strong directional evidence. There's also a known bug: the `xtf` (cross-timeframe) feature currently resolves to zeros, so it contributes nothing.

## Layer 3 — Causal Stability Filter (CSS)

**What it does**: scores how *causally stable* each feature is in the current regime, producing a composite CSS scalar and per-feature gates (`stable` / `conditional` / `discard`). The CSS table is built offline by `causal_trainer.py` using a Granger-causality pre-filter followed by normalised transfer entropy. The idea: a feature that was only spuriously correlated with returns gets a low stability score and is down-weighted or discarded.

**What flows out**: a CSS scalar (multiplies the alpha), and a gate per feature. Features gated `discard` are zeroed in the input vector before Layer 4 sees them.

**How it suppresses signal**: directly and multiplicatively. `alpha_final *= css`. The fallback CSS table (used when no trained table is present) fills every cell with **0.5**, which *halves* the alpha. The Phase 1 overlay notes this is "the most impactful single change" — bypassing the CSS multiplier when it's just the 0.5 fallback. So if the offline CSS table is missing or weak, this layer alone can cut the signal in half before it reaches the decision model.

## Layer 4 — Adaptive Decision Layer (the ML heart)

**What it does**: this is where the actual alpha number is produced. A walk-forward-trained model (logistic with causal-graph constraints) takes the evidence vector, CSS gate, and regime, and produces a raw alpha. Then it applies a cascade of **execution-aware adjustments**:

```
spread_cost  = 0.5 × bid_ask_spread × q                 (half the spread)
slippage     = λ_temp × σ × √(q / ADV)                  (Almgren-Chriss temporary impact)
α_net        = α_scaled − spread_cost − slippage
P_fill       = exp(−queue_position / ADV)               (limit-order fill probability)
decay_factor = exp(−δ × Δt)                             (latency-to-fill decay)
α_exec       = α_net × P_fill × decay_factor
```

On top of that:
- **Regime entropy discount**: if regime entropy is high (> `entropy_high_threshold`), the alpha is multiplied by an `uncertainty_discount` (e.g. 0.5). Don't bet big when you don't know the regime.
- **Capacity constraint**: an online-learned limit on position size, updated by an EMA of realised vs target market impact after each trade.
- **Min-edge gate**: if `α_exec < min_edge_threshold`, the signal is zeroed — not worth trading after costs.
- **Staleness gate**: if the signal is older than `max_latency_ms`, it's zeroed.
- **EQS (execution quality score) suspension**: if execution quality stays poor for several bars, the strategy self-suspends.

**What flows out**: `α_final` — positive for long, negative for short, zero for no-trade — plus a diagnostics dictionary.

**How it suppresses signal**: this layer is a *gauntlet*. Every line above either multiplies the alpha by something ≤ 1 or zeroes it outright. A signal entering at 0.20 can exit at 0.05 after CSS, entropy, spread, slippage, fill-probability, and latency discounts — and then get zeroed by the min-edge gate because 0.05 is below threshold. This is the single most likely place the strategy "dies": not because any one discount is wrong, but because they compound.

## Layer 5 — Survival Gate (offline)

**What it does**: a statistical gate that runs offline, not per-bar. It computes the **Deflated Sharpe Ratio** (DSR), Bayesian information ratio, and a decay class for each strategy variant. DSR is the key one — it corrects a strategy's apparent Sharpe for the number of trials that were run to find it, guarding against the "test 20 ideas, one looks good by luck" problem. The `_compute_dsr` method takes an `n_trials` parameter that inflates with how many variants you've tried.

**What flows out**: an admit/reject decision for whether a strategy variant is statistically allowed to trade at all.

**How it suppresses signal**: it can reject an entire strategy variant before it ever trades, if the variant's edge is indistinguishable from multiple-testing luck. (This is the same DSR machinery the thesis-discovery plan reuses to judge whether a discovered edge is real.)

## Layer 6 — Strategy Repository

**What it does**: lifecycle management. Tracks each strategy variant's state (active / suspended / retired), enforces kill switches, and manages promotion and demotion. This is the bookkeeping layer that decides which strategies are live.

**How it suppresses signal**: kill switches and suspension. If a strategy trips a risk limit or a kill condition, this layer takes it offline regardless of what the other layers say.

---

# Part 2 — `deter_alpha`: the deterministic confirmation gate

`deter_alpha` is **not a second strategy**. It is an independent, deterministic re-derivation of the directional opinion, built so that the ML signal must be *confirmed* by a separate method before trading. The philosophy: "only trade when multiple independent lines of evidence align." It runs in eight steps.

## Step 1 — Adaptive Swing Detector

Same idea as Layer 1's swing detection but maintained independently inside `deter_alpha`: ATR-14-gated swing points producing HH / HL / LH / LL labels. O(1) per bar online.

## Step 2 — Region Labeler

Uses Heikin-Ashi candle transforms: compares the change in HA-close against `0.5 × ATR` to label the current bar's local regime (trending up, trending down, or neutral). A smoothing step so single-bar noise doesn't flip the regime.

## Step 3 — Feature Evaluator

For the current bar, evaluates every feature column (from the feature engineering module) as "true" or "false" *for a given direction*. For example, for a long hypothesis: is momentum positive? Are we making higher-lows? Is volume confirming? Each feature group gets a boolean verdict relative to the proposed direction.

## Step 4 — Rolling Causal Analyser

This is the analytical core. Every N bars (default 240) it re-derives which features actually *cause* the target versus merely correlate:

- **Granger pre-filter**: a linear baseline test (with first-differencing for stationarity) to screen candidate causal features.
- **Normalised Transfer Entropy** (NTE): `NTE = TE(X→Y) / H(Y)`, a nonlinear, information-theoretic measure normalised to [0,1] so the threshold is meaningful across instruments. Transfer entropy captures nonlinear dependence that Granger (being linear) misses.

It sorts features into three sets:
- **C_set** (Causing): high NTE — these features genuinely drive the target
- **A_set** (Affecting): low NTE but high Pearson correlation — associated but not causal
- **Neutral_set**: neither

Each `CausalSets` object carries a **validity window** (`valid_until_bar`) — stale causal sets expire and return no-trade until the next refit. It also records its exact provenance (the feature list, TE bins, bin edges) so a backtest and a live run can be *proven* to have used the same causal configuration.

## Step 5 — Deterministic Filter

The gate itself:

```
C_met_ratio = #{c in C_set : feature_signal[c] is True} / |C_set|
c_ok        = C_met_ratio ≥ c_threshold        (default 0.80)
a_ok        = ANY(a in A_set : feature_signal[a] is True)
deter_alpha = c_ok AND a_ok AND precision_ewma > precision_floor
```

In plain terms: at least 80% of the *causing* features must agree with the proposed direction, AND at least one *affecting* feature must agree, AND the filter's recent track record (precision) must be above the floor.

**Precision tracking**: after every bar where `deter_alpha` fired, it records one bar later whether the regime actually agreed. This updates an EWMA precision with a 1000-bar half-life. If precision drops below the invalidation floor (0.50), the filter **suspends itself** until it recovers. This is a self-policing mechanism — the gate stops trusting itself when it's been wrong too often.

## Step 6 — ML probability (supplied by the caller)

`deter_alpha` receives `proba_alpha` (the ML model's confidence) and `proba_direction` (the ML model's directional call, +1/-1) from `alpha_factory`. This is the handshake point between the two halves.

## Step 7 — Final Gate (dual confirmation)

The decision that actually matters:

```
1. proba_alpha ≥ proba_threshold          (default 0.65)
2. deter_alpha == True                     (Step 5 passed)
3. sign(proba_direction) == sign(deter_direction)   (they agree on direction)
→ final_decision = sign(deter_direction)   else 0
```

All three conditions must hold. The ML must be confident, the deterministic gate must pass, and — critically — **both must agree on whether to go long or short**. Disagreement → no trade. This is the veto: the ML can be as confident as it likes, but if the causal gate disagrees on direction, nothing happens.

## Step 8 — Live Adaptation Scheduler

Housekeeping that keeps the gate honest over time: triggers the causal refit every N bars, triggers precision re-estimation, and auto-invalidates the filter if out-of-sample precision falls below 0.5. Maintains a rolling out-of-sample validation buffer so the precision number isn't computed on the same data that set the thresholds.

---

# Part 3 — Why it's built this way, and the risk that creates

## The design intent

Each gate answers a specific failure mode:

| Gate | The failure it's guarding against |
|---|---|
| L1 regime entropy | Trading confidently when the market regime is ambiguous |
| L2 calibration | Treating a raw feature value as if it were a probability |
| L3 CSS | Trading on a feature that's only spuriously correlated |
| L4 execution adjustments | Assuming you'll get filled at the mid-price with no cost |
| L4 min-edge | Trading when the edge is smaller than the cost |
| L5 DSR | Trading a strategy that only looked good because you tried many |
| deter_alpha causal sets | Trading when the "predictive" features aren't actually causal |
| deter_alpha final gate | Trading when your two independent methods disagree |

Every one of these is a *defensible* guard. Individually, each makes the strategy more honest.

## The risk: multiplicative gating collapse

Here's the problem, stated plainly. Most of these gates **multiply** the signal by a factor ≤ 1 or **zero** it. Stack enough of them and a real edge gets ground to dust:

```
raw alpha             = 0.20
× CSS (0.55)          = 0.110
× entropy disc (0.70) = 0.077
× fill prob (0.80)    = 0.062
× latency (0.90)      = 0.055
then: min-edge gate rejects anything below ~0.05–0.10
→ trade rejected, or fires so rarely the strategy never accumulates samples
```

The diagnostic symptom is exactly what we saw in the backtests that started this whole investigation: **1 trade in 2005 bars**. Not because the edge was wrong, but because the gates compounded until almost nothing survived. A sophisticated noise-suppression system wrapped around a weak signal produces beautiful confidence metrics and zero CAGR.

This is *the* reason the project pivoted to thesis-first discovery: before trusting this architecture to refine an edge, we need to (a) confirm a real edge exists in the raw data, and (b) measure how much of it each layer destroys. That second task — the information-decay diagnostic — is specifically designed to instrument the cascade above and show where the signal dies.

## The honest summary

- **`alpha_factory`** is a well-engineered six-layer ML pipeline that is, by design, far better at *suppressing* signal than *creating* it.
- **`deter_alpha`** is a thoughtful independent confirmation gate that adds a direction-agreement veto on top.
- Together they form a refinery: excellent if you feed them a real edge, sterile if you don't.
- The current project status is that no raw edge has yet passed honest walk-forward testing (pullback and failed-mean-reversion theses both failed), so the architecture has nothing to refine yet. That's not a flaw in the architecture's engineering — it's the reason the work right now is edge *discovery*, not architecture refinement.

---

## Quick reference — file map

| Component | File |
|---|---|
| Six-layer orchestration | `src/core/alpha_factory.py` |
| L1 Market Structure | `src/core/layers/` (market structure engine) |
| L2 Feature Evidence | `src/core/layers/` (feature evidence layer) |
| L3 Causal Stability | `src/core/layers/` + `src/offline/causal_trainer.py` |
| L4 Adaptive Decision | `src/core/layers/decision_layer.py` |
| L5 Survival Gate | `src/core/layers/survival_gate.py` |
| L6 Strategy Repository | `src/core/layers/` (strategy repo) |
| Deterministic confirmation | `src/core/deter_alpha.py` |
| Config | `src/config/alpha_factory_config.yml` |
| Phase 1 signal-flow overlay | `src/config/phase1_overlay.yml` |

*This document describes the live signal path as of the v6 plan freeze. The architecture is frozen during thesis discovery; nothing here changes until a thesis passes Phase A and the information-decay diagnostic measures each layer's actual contribution.*
