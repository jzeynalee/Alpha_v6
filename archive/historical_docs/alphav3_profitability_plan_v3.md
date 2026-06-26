# Alpha V3 — Final Profitability Roadmap (v3)

**Status:** v2 + Amendments A-H (leakage audit, latency budgets, turnover,
stability, benchmarks, capacity, kill-switches, SHAP discipline).
**Approach:** edge-first sequencing, with process governance promoted to
load-bearing status. Every step has file paths, exact thresholds, and
numeric success criteria.

---

## 0. v3 deltas (what changed from v2)

For traceability:

| # | Change | Source |
|---|---|---|
| 1 | New **Phase 0.7** — programmatic leakage audit with runtime timestamp assertions | A |
| 2 | New **latency budgets** calibrated to 5-min timeframe (not HFT numbers) | B |
| 3 | Phase 2 success criteria add **turnover-adjusted expectancy** and **edge_per_trade > 2× round-trip cost** | C |
| 4 | "No single trade > 15% of PnL" + rolling 30-day Sharpe positivity replace v2's weaker "no month > 40%" | D |
| 5 | New **Phase 2.7** — benchmark comparison vs buy-hold, EMA cross, ATR breakout, random-entry-same-exits | E |
| 6 | **Capacity classification** added to Phase 2.0 hypothesis spec | F |
| 7 | **Phase 5.4** — kill-switch trigger matrix expanded (data lag, spread blow-out, model collapse, latency breach) | G |
| 8 | **Phase 0.3 SHAP wiring changed**: async/batched, not per-bar | H |
| 9 | Phase 4.2 explicitly checks that **PF stays > 1.05 after** each penalty is re-enabled, not "stop at first failure" — minor clarity fix |

---

## 1. Reconciled diagnosis (unchanged from v2)

The "1 trade / 2005 bars / −0.04%" result has three independent causes:
**frequency** (gates), **edge** (labels), **statistical power** (data
volume). All three must be addressed; the phase order is designed
around that fact.

---

## 2. The six phases

### Phase 0 — Data, instrumentation, governance, leakage audit (3-5 days, blocking)

This phase produces nothing tradeable. It establishes the conditions
without which the next five phases are theatre.

#### 0.1 — Data expansion

Minimum **1 year of 5-min OHLCV** (~105,000 bars). Institutional:
2-3 years.

Partition (commit to `src/config/datasets.yml`):

| Window | Bars | Purpose |
|---|---|---|
| Training | 2024-01-01 → 2025-06-30 | All model fitting + WF |
| Validation | 2025-07-01 → 2025-12-31 | Threshold tuning, calibration, benchmarks |
| **Frozen OOS** | 2026-01-01 → 2026-05-01 | **Touched ONCE before going live** |

The loader must programmatically refuse repeated reads of the OOS
window from the same git commit hash. Honor-system is not enough.

#### 0.2 — Gate suppression instrumentation

Wire `AlphaFactorySignalSource.gate_report()` into `run_backtest.py`.
Persist a JSON file per run for trend analysis. The dominant gate
decides Phase 1's first action.

#### 0.3 — Trade attribution (SHAP async, per Amendment H)

Your `TradeEntry` dataclass logs regime, `proba_alpha`, `deter_alpha`,
`c_met_ratio`, etc. Add:

```python
# src/risk/trade_journal.py — TradeEntry
top_features: str = ""   # JSON list of (feature, shap_value), top 5
                         # POPULATED ASYNCHRONOUSLY, not at trade open
```

**Wire it like this, not like v2 said.** SHAP at entry is too slow:

```python
# NEW: src/core/shap_attribution.py
class AsyncShapAttributor:
    """
    Runs SHAP on closed trades, every N trades or every M minutes.
    Latest values are written back to the trade journal via UPDATE.
    Never runs on the hot inference path.
    """
    def __init__(self, journal, model, batch_size=20):
        self._journal, self._model, self._batch = journal, model, batch_size
        self._pending = []

    def enqueue(self, trade_id, feature_vec):
        self._pending.append((trade_id, feature_vec))
        if len(self._pending) >= self._batch:
            self._flush()

    def _flush(self):
        import shap
        ids, vecs = zip(*self._pending)
        explainer = shap.TreeExplainer(self._model)
        values = explainer.shap_values(np.vstack(vecs))
        # Write back top-5 per trade
        for trade_id, sv in zip(ids, values):
            top5 = sorted(enumerate(np.abs(sv)), key=lambda x: -x[1])[:5]
            self._journal.update_attribution(trade_id, top5)
        self._pending.clear()
```

Inference loop calls only `enqueue()` — O(1), one list append. The
heavy work batches in a separate thread or after-close hook.

#### 0.4 — MFE/MAE analytics notebook

Build `notebooks/exit_quality.ipynb` scaffolding now. No data yet, but
the analysis code is ready when Phase 1+ produces closed trades.

#### 0.5 — Experiment registry

```bash
mkdir -p data/experiments
# Append after every backtest:
echo "$(git rev-parse HEAD)\t$(date -Iseconds)\t<desc>\t<final_eq>\t<n_trades>\t<pf>" \
    >> data/experiments/log.tsv
```

#### 0.6 — Latency budgeting (per Amendment B, calibrated to 5-min)

Your code already has `LAT_BUDGET_MS = 50.0` and a `_lat_sample_window`
in `alpha_factory.py`. The HFT-style table in the amendment
(`<5ms feature, <10ms inference, <25ms loop`) is wrong for your
timeframe — you have 300 seconds between bars. Calibrated budgets:

| Stage | Soft target | Hard ceiling | Action on breach |
|---|---|---|---|
| Feature update (incremental) | < 100 ms | < 300 ms | Log warning, sample rate |
| Model inference (Model A + Model B) | < 50 ms | < 150 ms | Log warning |
| Full bar decision loop | < 250 ms | < 1000 ms | Alert + degrade |
| Order dispatch | < 500 ms | < 2000 ms | Alert; cancel if stale |
| End-to-end (bar close → order ack) | < 1000 ms | < 3000 ms | Skip bar |

Wire `MetricsRegistry.set("latency_p99_ms", ...)` (already in your
codebase) with these labels and ensure p99 alerts fire. The
end-to-end metric is the only one that matters for catching latency
creep over time — log it on every decision, plot it weekly.

The point of doing this now (not later, per B): the architecture
grows monotonically. Adding SHAP, PSI, structural regime, meta-model
each cost milliseconds. Without a budget you discover at Phase 5
that your loop takes 8 seconds and you can't ship.

#### 0.7 — Leakage audit (per Amendment A, MANDATORY)

This is the most important addition in v3. Do not skip.

Two layers: a **static audit checklist** and a **runtime assertion**.

##### 0.7.1 — Static audit checklist

For each item, document in `docs/leakage_audit.md` how the code
guarantees it. If you can't write the guarantee, the leak exists.

| # | Check | Where to verify |
|---|---|---|
| 1 | Scaler fits on train fold only, transforms validation/OOS | `src/offline/decision_trainer.py` — confirm `scaler.fit(X_train)` then `scaler.transform(X_val)`, never `fit_transform` on combined data |
| 2 | ATR rolling windows use only past bars | `features_engineering.py` — confirm `bn.move_mean(..., min_count=window)` produces NaN for the warmup, no forward fill |
| 3 | Swing detection requires `min_confirm_bars` lag | `market_structure.py` — confirmed by the `confirmed: bool` field; verify it's enforced before any feature uses it |
| 4 | Triple-barrier labels use only `[t+1, t+max_horizon]` | New `triple_barrier_labels()` function (Phase 2.1) — already correct by construction |
| 5 | Regime labels generated causally (`label_timestamp_lag >= 1`) | `RegimeIsolationCertificate` already enforces this — verify it's checked |
| 6 | Calibration fit on validation, applied to OOS | Phase 2.4 — `CalibratedClassifierCV(cv='prefit').fit(X_val, y_val)` |
| 7 | Feature selection uses train labels only | Phase 2.3 — `scripts/select_features.py` runs on training window |
| 8 | SHAP explainer fits on train, evaluates on closed trades | Phase 0.3 — `TreeExplainer(model)` where model was fit on train |
| 9 | Rolling quantile for adaptive threshold uses only past proba values | Phase 4.1 — `deque(maxlen=2000)` only appends past observations |
| 10 | No global normalisation across train/val/OOS | Audit every `scaler` instance for `fit_transform` calls |

##### 0.7.2 — Runtime assertion harness (NEW FILE)

```python
# src/core/leakage_guard.py
"""
Catches lookahead silently — installed in the backtest engine and the
live signal path. Asserts every feature timestamp <= prediction timestamp.
"""
import logging
logger = logging.getLogger(__name__)

class LeakageGuard:
    def __init__(self, strict: bool = True):
        self.strict = strict
        self._violations = 0

    def check(self, feature_ts: int, prediction_ts: int, source: str = "?") -> None:
        if feature_ts > prediction_ts:
            self._violations += 1
            msg = (f"LEAKAGE: feature_ts={feature_ts} > prediction_ts={prediction_ts} "
                   f"(source={source})")
            if self.strict:
                raise AssertionError(msg)
            logger.error(msg)

    def check_window(self, window_df, prediction_ts: int, source: str = "?") -> None:
        # The whole window must end at or before the prediction time.
        if len(window_df) == 0:
            return
        last_ts = int(window_df["timestamp"].iloc[-1])
        self.check(last_ts, prediction_ts, source)

    @property
    def violations(self) -> int:
        return self._violations
```

Install in two places:

```python
# 1. Backtest engine (src/backtest/engine.py — wherever the per-bar
# call to signal_source.generate happens):
self._leakage_guard.check_window(window, bar.timestamp, source="backtest")

# 2. Live alpha factory (src/core/alpha_factory.py — at the top of
# _process_bar_sync):
self._leakage_guard.check_window(ohlcv, current_ts, source="live")
```

Run with `strict=True` during research; `strict=False` (log only) in
live to avoid crashing on a clock-skew edge case. **Any violation
during Phase 0-2 invalidates that phase's results.**

#### 0.8 — Phase 0 exit criterion

- [ ] ≥ 100,000 5-min bars in `data/raw/v2/`
- [ ] `src/config/datasets.yml` exists, loader enforces frozen-OOS
- [ ] `gate_report()` wired and one JSON saved
- [ ] `TradeEntry.top_features` field added + async SHAP attributor
      stubbed (no actual model yet)
- [ ] Latency budgets defined in YAML; metrics emit
- [ ] `docs/leakage_audit.md` filled in for all 10 checks
- [ ] `LeakageGuard` installed in backtest + factory paths
- [ ] One backtest on train window runs with zero leakage violations

---

### Phase 1 — Restore signal flow (1-2 days)

Same as v2. No changes.

#### 1.1 — Loosen FinalGate

```yaml
deter_alpha:
  proba_threshold:   0.52
  c_threshold:       0.55
  precision_floor:   0.45
  invalidation_floor: 0.40
```

#### 1.2 — Disable entropy discount

```yaml
layer4:
  entropy_high_threshold: 0.99
  uncertainty_discount:   1.0
```

#### 1.3 — Disable CSS multiplier

Bypass via `layer3.bypass: true` flag, OR change fallback CSS table
from 0.5 to 1.0.

#### 1.4 — Loosen EQS

```yaml
layer4:
  eqs_alert_threshold:   0.10
  eqs_suspend_threshold: 0.05
```

#### 1.5 — Maker-rate fees

```python
BacktestConfig(fee_pct=0.0004, slippage_pct=0.0002, ...)
```

If your exchange doesn't offer maker rebates, keep 0.001 but note
that your edge-per-trade requirement (Phase 2) becomes harder.

#### 1.6 — Phase 1 exit criterion

Run on **train** window:

- [ ] ≥ 200 trades
- [ ] `directional_pct > 10%`
- [ ] Final equity within ±5% of initial
- [ ] **Zero leakage violations** (per 0.7)

---

### Phase 2 — Build a real signal (2-4 weeks)

This phase creates edge. Five sub-phases.

#### 2.0 — Alpha hypotheses + capacity classification (4-8 hours of thinking)

For each of 2-3 chosen hypotheses, `docs/alpha_theses.md` must contain:

```markdown
## Hypothesis 1 — <Name>

**Economic rationale:** Why this inefficiency should exist (e.g.,
"stop-loss clusters above prior swing-high create predictable
liquidations").

**Falsification condition:** What single observation would kill this
(e.g., "fails if hit-rate of post-sweep mean-reversion < 45% on
any 6-month window").

**Encoding features:** Which existing or new features represent this
(e.g., "swing-high distance, volume z-score on the sweep bar,
candle-body ratio").

**Capacity classification (per Amendment F):**
- Type: [low-freq swing | intraday directional | microstructure |
  latency]
- Expected hold time: <X bars>
- Expected trades per day: <N>
- Notional ceiling estimate: <$M> before slippage degrades it
- Scalability tier: [high | moderate | low | fragile]

**Why this tier matters:** If "low" or "fragile", the strategy is a
research curiosity, not a business. Plan accordingly.
```

If you can't write the falsification condition or the capacity tier,
the hypothesis isn't ready. Discard it.

#### 2.1 — Triple-barrier labels (3-class)

```python
def triple_barrier_labels(close, high, low, atr, tp_atr=2.0, sl_atr=1.0, max_horizon=24):
    """Returns {-1, 0, +1}. The 0 class IS no-trade (Amendment 13)."""
    n = len(close)
    y = np.zeros(n, dtype=np.int8)
    for t in range(n - max_horizon):
        a = atr[t]
        if not np.isfinite(a) or a <= 0: continue
        upper, lower = close[t] + tp_atr*a, close[t] - sl_atr*a
        for k in range(t + 1, min(t + max_horizon + 1, n)):
            if high[k] >= upper: y[t] = +1; break
            if low[k]  <= lower: y[t] = -1; break
    return y
```

Expected distribution: ~30% +1, ~30% −1, ~40% 0. Strong skew = wrong
`tp_atr / sl_atr`.

#### 2.2 — Two-model meta-labeling

```
features → Model A (multi-class) → proba_{long, no, short}
                                    │
features + Model A probas ──→ Model B (binary) → take_trade ∈ {0, 1}
```

- Model A: LightGBM multi-class on 3-class triple-barrier
- Model B: trained on bars where Model A emits strong directional
  conviction (`max(p_long, p_short) > 0.45`); target = did predicted
  direction actually win
- Trade only when `take_trade == 1`; direction = `argmax(p_long, p_short)`

#### 2.3 — Feature selection: 220 → 25

`scripts/select_features.py`:

1. MI(feature, "Model A picked winning direction") on training set only
2. Top 60 by MI
3. Greedy prune by |Spearman| > 0.85
4. Stop at 25, save to `data/offline/feature_set_v1.json`

#### 2.4 — Probability calibration (mandatory)

```python
calibrated = CalibratedClassifierCV(estimator=raw_model, cv="prefit",
                                     method="isotonic")
calibrated.fit(X_val, y_val)
```

Acceptance:
- Brier score lower after than before
- Reliability curve on diagonal in `[0.3, 0.8]`
- ECE < 0.05

#### 2.5 — Purged walk-forward

`src/offline/walk_forward.py`:
- 6 folds on **train** only
- Embargo = `max_horizon + 1` bars between train and test
- Purge training observations whose label window overlaps test
- Calibrate inside each fold's test split

#### 2.6 — Benchmark comparison (per Amendment E, NEW)

Run on **validation** window. Build these baselines as separate
strategies in the same backtest engine:

| Benchmark | Implementation | Purpose |
|---|---|---|
| Buy & hold BTC | Single position, never closed | Market beta |
| EMA(20)/EMA(50) crossover | Long when fast > slow, flat when fast < slow | Naive trend |
| ATR breakout | Long when close > 20-bar high + 0.5×ATR; flat otherwise | Naive volatility |
| Random entry, same exits | Coin-flip direction per bar where Model A says "directional"; same TP/SL as system | **Exit-quality test** |

Your system must beat **all four** after fees on the validation
window. If it loses to EMA crossover, you have not justified the
architecture. If it loses to random-entry-same-exits, your direction
prediction adds nothing and only your exit logic matters — fix the
direction model.

#### 2.7 — Phase 2 exit criterion (success metric updated for C+D+E)

Run full pipeline on **validation** window:

**Profitability (basic):**
- [ ] ≥ 300 trades
- [ ] Profit factor after fees > 1.10
- [ ] Net Sharpe (annualised, after fees) > 0.8

**Turnover constraints (Amendment C, NEW):**
- [ ] Average gross edge per trade ≥ 2 × round-trip cost (e.g., at
      0.30% RT cost, edge ≥ 0.60% gross)
- [ ] Net edge per trade (after fees) > 0
- [ ] Median holding time > 6 bars (30 minutes) — prevents micro-churn

**Stability (Amendment D, REPLACES v2's monthly check):**
- [ ] No single trade contributes > 15% of total PnL
- [ ] No single calendar month > 30% of total PnL
- [ ] Rolling 30-day Sharpe positive on ≥ 4 of 6 windows
- [ ] Rolling 30-day win rate within ±15 pp of overall win rate
- [ ] At least 3 regimes (per structural classifier in Phase 3, but
      use month-of-year here as a proxy if Phase 3 not yet done)
      contribute net-positive expectancy

**Benchmark beat (Amendment E, NEW):**
- [ ] Beats Buy & Hold on Sharpe (not just PF — buy-and-hold has
      huge tail risk that Sharpe captures)
- [ ] Beats EMA(20)/EMA(50) crossover on net PF
- [ ] Beats ATR breakout on net PF
- [ ] Beats random-entry-same-exits on net PF **by margin > 0.15**
      (smaller margins = your direction model adds noise)

**Health checks (secondary, logged not gated):**
- [ ] WF AUC > 0.55 across ≥ 4 of 6 folds — drift diagnostic only

If Phase 2 fails on PF or stability: alpha hypothesis is wrong.
Return to 2.0.

If Phase 2 fails the **benchmark beats**: alpha hypothesis may be
right but ML implementation isn't worth the complexity. Either
simplify (e.g., use EMA crossover as the strategy) or rebuild the
ML side.

---

### Phase 3 — Regime specialisation (1-2 weeks, conditional)

Only enter if Phase 2 PF > 1.10 **and** benchmark beats hold.

#### 3.1 — Structural regime classifier (replaces HMM operationally)

Per v2. Five regimes: TREND_UP_EXPANSION, TREND_DN_EXPANSION,
COMPRESSION, MEAN_REVERSION, HIGH_NOISE.

#### 3.2 — Regime-conditioned modelling

Option 1 (default): single LightGBM with `regime` as categorical
feature.

Option 2 (only if Option 1 leaves > 0.2 PF on the table by regime):
one LightGBM per regime, `HIGH_NOISE` → hard no-trade.

#### 3.3 — Phase 3 exit criterion

Re-run on **validation**:
- [ ] PF after fees ≥ Phase 2 baseline + 0.10
- [ ] Sharpe ≥ Phase 2 baseline + 0.2
- [ ] No regime has negative expectancy (mark no-trade if so)
- [ ] All Phase 2.7 stability + benchmark criteria still met

---

### Phase 4 — Robustness (1 week)

Re-introduce production safeguards. Trade some PF for survivability.

#### 4.1 — Adaptive threshold (rolling quantile)

```python
threshold = (0.55 if len(history) < 200
             else float(np.quantile(history, 1 - target_trade_rate)))
```

`target_trade_rate` set to match Phase 2/3 observed trade rate.

#### 4.2 — Re-enable execution penalties incrementally

Re-enable in this order. Run full validation backtest after each.
**After every step, verify PF stays > 1.05 net of fees.** Stop and
roll back the last change if PF drops below 1.05.

1. CSS multiplier (rebuild CSS table on the 25-feature set)
2. Entropy discount (`entropy_high_threshold: 0.7`, `discount: 0.5`)
3. `c_threshold: 0.65` (not original 0.80 — calibrated to smaller C_set)
4. `precision_floor: 0.55`
5. `eqs_alert_threshold: 0.60`, `eqs_suspend_threshold: 0.40`

#### 4.3 — Single OOS evaluation (FROZEN dataset)

**Run ONCE.** Whatever the result, do not retune.

Acceptance for "live-capital ready":

**Profitability:**
- [ ] OOS PF > 1.05 after fees
- [ ] OOS Sharpe > 0.7
- [ ] OOS max drawdown < 1.5 × validation max drawdown
- [ ] OOS trade count ≥ 0.7 × validation trade count

**Stability (Amendment D applied to OOS):**
- [ ] No single OOS trade > 15% of OOS PnL
- [ ] Rolling 30-day OOS Sharpe positive on majority of windows

**Drift diagnostic:**
- [ ] OOS feature PSI vs training < 0.25 on ≥ 22 of 25 features
- [ ] OOS AUC within 0.05 of validation AUC

If OOS fails: do not trade. Validation methodology was insufficient.
Wait for new data; treat the OOS window as part of training going
forward.

---

### Phase 5 — Live hardening (ongoing once live)

Only after Phase 4.3 passes on the frozen OOS.

#### 5.1 — PSI drift monitoring

```python
def psi(reference, current, n_bins=10):
    bins = np.quantile(reference, np.linspace(0, 1, n_bins + 1))
    ref = np.histogram(reference, bins=bins)[0] / len(reference) + 1e-9
    cur = np.histogram(current,   bins=bins)[0] / len(current) + 1e-9
    return float(np.sum((cur - ref) * np.log(cur / ref)))
```

Hooks into `OfflineTrainer` drift-triggered retrain. Thresholds:
< 0.1 stable, 0.1-0.25 caution (log alert), > 0.25 retrain
(actionable).

#### 5.2 — Live-vs-backtest alpha alignment monitor

Mirror every live trade through the backtest engine on the
historical-aligned bar; compare `alpha_final` and `proba_alpha`.
Alert if mean absolute error > threshold over 10 consecutive trades.

#### 5.3 — Capacity & non-linear slippage (per Amendment 11 + F)

Enable Almgren-Chriss square-root impact when typical position size
exceeds 1% of ADV. Until then, constants are fine. Your capacity
classification from Phase 2.0 determines whether you ever cross that
threshold.

#### 5.4 — Kill-switch trigger matrix (per Amendment G, EXPANDED)

Your codebase has `KillSwitch` infrastructure (`src/risk/risk_manager.py`,
`StrategyRepository` per-strategy DD checks) and EQS suspension.
Expand to cover **all** of these triggers. Each must have explicit
test coverage.

| Trigger | Threshold | Action | Owner module |
|---|---|---|---|
| WS data feed lag | > 30 sec since last bar | Disable trading, alert | `data_orchestrator` |
| Spread explosion | > 5 × 30-bar median spread | No-trade this bar | `decision_layer` |
| PSI spike (any feature) | > 0.35 over rolling 24h | Safe mode (size × 0.3) | `OfflineTrainer` drift hook |
| Model confidence collapse | `max(proba) < 0.55` for 50 consecutive bars | No-trade, alert | `decision_layer` |
| Slippage anomaly | Realised vs expected slippage > 3× over 10 trades | Size × 0.5, alert | `decision_layer.update_capacity` |
| Latency breach | End-to-end p99 > 3000 ms | Degrade gracefully (skip bar) | `MetricsRegistry` watcher |
| Per-strategy DD | > 15% (already in place) | Liquidate within 1h | `StrategyRepository` |
| Portfolio DD | > 10% (already in place) | Global kill | `StrategyRepository` |
| Daily loss | > 5% of equity (already in place) | Stop trading until next day | `RiskManager` |

For each trigger, write a test in `tests/test_kill_switches.py` that
simulates the condition and asserts the action fires. **Before live
deployment, every trigger must have a passing test.**

#### 5.5 — Paper trading window

Run live in `dry_run: true` mode for **30 days minimum** before
deploying capital. At the end of the window:

- [ ] Live PF within 30% of OOS PF (mean absolute drift)
- [ ] Zero kill-switch false positives
- [ ] Zero unhandled errors in logs
- [ ] Latency p99 within budget
- [ ] No PSI alerts above 0.25

If any fail, fix and restart the 30-day clock.

---

## 3. Deferred items (acknowledged)

Per v2's deferral list:

- Separation of Alpha → Selection → Sizing → Execution into four
  distinct layers (Amendment 4 from the earlier audit) remains a
  post-Phase-4 code quality milestone, not a Phase 0-4 requirement.
- White's Reality Check / SPA tests are useful but heavyweight;
  frozen OOS does 95% of the same job.

---

## 4. Phase-by-phase checklist

Print this. Tick as you go. Do not skip ahead.

```
PHASE 0 — Data, governance, leakage audit
[ ] 0.1 ≥ 1 year of 5-min OHLCV in data/raw/v2/
[ ] 0.1 src/config/datasets.yml + programmatic frozen-OOS enforcement
[ ] 0.2 gate_report() wired with JSON persist
[ ] 0.3 TradeEntry.top_features field added
[ ] 0.3 AsyncShapAttributor stubbed (NOT in hot path)
[ ] 0.4 notebooks/exit_quality.ipynb scaffolded
[ ] 0.5 data/experiments/log.tsv created
[ ] 0.6 Latency budgets in YAML; MetricsRegistry emitting
[ ] 0.7 docs/leakage_audit.md filled for all 10 checks
[ ] 0.7 LeakageGuard installed in backtest + factory; strict=True
[ ] One backtest run on TRAIN: zero leakage violations

PHASE 1 — Signal flow (no model changes)
[ ] 1.1 deter_alpha thresholds loosened
[ ] 1.2 Entropy discount neutralised
[ ] 1.3 CSS multiplier bypassed
[ ] 1.4 EQS thresholds lowered
[ ] 1.5 Maker fees if available
[ ] TRAIN: ≥ 200 trades, directional_pct > 10%, zero leakage

PHASE 2 — Edge construction
[ ] 2.0 docs/alpha_theses.md with 2-3 hypotheses,
        each including capacity classification (Amendment F)
[ ] 2.1 3-class triple-barrier labels
[ ] 2.2 Model A (multi-class) + Model B (meta-filter)
[ ] 2.3 25-feature set saved to feature_set_v1.json
[ ] 2.4 Isotonic calibration; Brier + ECE checked
[ ] 2.5 walk_forward.py with purge + embargo
[ ] 2.6 4 benchmarks built (BH, EMA-X, ATR breakout, random-same-exits)
[ ] 2.7 VALIDATE: PF > 1.10, Sharpe > 0.8, ≥ 300 trades
[ ] 2.7 VALIDATE: edge/trade ≥ 2× cost, median hold > 6 bars  (C)
[ ] 2.7 VALIDATE: no trade > 15% PnL, no month > 30% PnL,
        rolling 30d Sharpe positive on ≥ 4 of 6 windows         (D)
[ ] 2.7 VALIDATE: beats all 4 benchmarks; random margin > 0.15 (E)

PHASE 3 — Regime specialisation (conditional on Phase 2 success)
[ ] 3.1 structural_regime.py classifier built
[ ] 3.2 Option 1 (regime-as-feature) OR Option 2 (per-regime)
[ ] 3.2 HIGH_NOISE → hard no-trade
[ ] VALIDATE: PF improvement ≥ +0.10; all Phase 2 criteria still met

PHASE 4 — Robustness
[ ] 4.1 Rolling-quantile adaptive proba_threshold
[ ] 4.2 Re-enable penalties incrementally; PF > 1.05 after each
[ ] 4.3 ONE backtest on FROZEN OOS
        PF > 1.05, Sharpe > 0.7, DD < 1.5×, trades > 0.7×,
        no trade > 15% PnL, PSI < 0.25 on ≥ 22 of 25 features

PHASE 5 — Live hardening (after 4.3 passes)
[ ] 5.1 PSI drift monitoring into OfflineTrainer
[ ] 5.2 Live-vs-backtest alpha alignment monitor
[ ] 5.3 Almgren-Chriss slippage enabled if position > 1% ADV
[ ] 5.4 All 9 kill-switch triggers implemented + tested        (G)
[ ] 5.5 30-day paper-trade; live PF within 30% of OOS PF
[ ] Deploy capital
```

---

## 5. Time and effort summary

| Phase | Calendar time | Goes live if successful? |
|---|---|---|
| 0 | 3-5 days | No (data + governance) |
| 1 | 1-2 days | No (config only) |
| 2 | 2-4 weeks | No (research) |
| 3 | 1-2 weeks (conditional) | No |
| 4 | 1 week | OOS-validated |
| 5 | 30+ days paper-trade | Paper → live |

Total to live capital: **8-12 weeks** of focused work. v3 is slightly
longer than v2 because Phase 0 grew from 1-3 days to 3-5 days
(leakage audit + latency budgets + expanded SHAP discipline). That
extra time pays for itself the first time the leakage guard catches
a silent bug in feature engineering — which it will.

---

## 6. The strategic frame (v3 update)

v2 closed by saying: "Your codebase is unusual — strong infrastructure,
unvalidated alpha. The work ahead is bolting edge onto infrastructure,
not building both."

v3 amends that with one observation. With the amendments applied,
the plan crosses a threshold from "research roadmap" to
"research-plus-process governance." That is the right place to be,
because your infrastructure is good enough that ad-hoc research will
produce false positives faster than you can validate them. The
frozen OOS, the benchmark gates, the leakage guard, the stability
metrics, and the kill-switch matrix are not bureaucracy — they are
the operational equivalent of the safeguards that keep institutional
quant desks from blowing up. Honor them, and an honest edge has the
runway to survive contact with live capital. Skip them, and even a
real edge will be drowned in false positives within a quarter.

The dominant risk after these amendments is no longer architecture
quality, but **false alpha discovery** — patterns that look real and
survive validation but are economically transient. The only cure is
long data windows, frozen OOS, paper trading, regime diversity, and
simplicity. v3 addresses each of those operationally. The rest is
discipline.
