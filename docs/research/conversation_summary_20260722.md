# Conversation Summary — 2026-07-17 to 2026-07-22

This file captures the key actions, design decisions, and code changes from the  
last four research‑planning and implementation discussions.  It serves as a  
single record of what was done and why.

---

## 1. High‑Level Roadmap Revision (2026-07-17)

**Objective**: Shift from a software‑maintenance mindset to a **mechanism‑discovery  
velocity** mindset.  The bottleneck is no longer engineering quality but the rate  
at which statistically robust, economically meaningful market mechanisms are  
validated.

**Decisions taken**:
- Introduce a **Research Director / ExperimentScheduler** that autonomously  
  cycles through mechanism‑symbol‑timeframe combinations.
- Use **expected information gain** as the priority metric, not roster order.
- De‑emphasise report generation, test‑suite runs, and bootstrap maintenance  
  until results materially change the evidence ladder.
- Build an **autonomous discovery loop** rather than a pre‑planned sequence.

**Result**: The plan was adopted and translated into the `ExperimentScheduler`  
class in `src/core/experiment_scheduler.py`.

---

## 2. ExperimentScheduler Implementation (2026-07-18 – 2026-07-19)

**Commits**: `1dca6aa` (fix mechanism registry), `c21cef2` (initial scheduler),  
`5c59fc2` (bootstrap seeds), `44da78f` (documentation).

**What was built**:
- `ExperimentScheduler` with a **priority queue** (`data/experiments/research_queue.json`).
- **Trigger factory** mapping mechanism IDs to event‑study condition callables.  
  Initially wired for M001 (z_overbought_2.5) and M002 (roc_5_pos).
- **run_cycle(budget=N)** executes the highest‑priority pending experiments,  
  updates the ladder and mechanism registry, and applies stopping rules.
- **Stopping rules**: blacklist combinations with no significant horizon, p > 0.2,  
  and effect < 5 bp after ≥ 10 events.
- **First cycle results**:
  - M001 on BTC 15m → rejected (consistent with D019).
  - M001 on BTC 1h → significant at h=20 (mean +27.1 bp, p=0.0052) — first time  
    the mechanism was observed at 1h.
- Fixed effect‑summary storage to use composite keys (`symbol_timeframe`).

**State after first cycle**:
- Research queue established.
- Evidence ladder updated with per‑timeframe hypotheses.
- Mechanism registry now stores per‑timeframe effect summaries.

---

## 3. Bayesian Belief Tracking and Exploration (2026-07-20)

**Commit**: `9813195` (Bayesian belief and exploration).

**Additions**:
- `BeliefState` dataclass tracks a **Normal‑conjugate posterior** for the effect  
  size (bp) of each mechanism‑symbol‑timeframe combination.
- `_update_belief()` stores sample mean, variance, and count; computes  
  P(effect > 5 bp) for priority calculations.
- **Priority function** now uses the posterior probability when available,  
  otherwise falls back to the mechanism’s frozen confidence score.
- 20 % **exploration rate**: with probability 0.2, a random pending experiment  
  is inserted into the schedule to avoid missing promising areas.
- Belief state persisted to `data/experiments/belief_state.json`.

**Rationale**: The scheduler now naturally balances exploitation (high‑gain  
experiments) and exploration; confidence evolves smoothly as evidence  
accumulates.

---

## 4. Autonomous Replication (2026-07-20 – 2026-07-21)

**Commits**: `70ae42c` (autonomous replication), `bb07b05` (M002 second cycle  
report), `35b201e` (M002 replication completion report).

**Additions**:
- `_schedule_replications()` automatically enqueues other symbols at the same  
  timeframe and other timeframes for the same symbol whenever an experiment  
  reaches p < 0.05 and mean > 5 bp.
- **Second cycle**: M002 on ETH 4h produced p=0.0025, +54.8 bp → replications  
  enqueued for SOL/4h, BNB/4h, ETH/1d.
- **Replication completion**:
  - SOL/4h: p=0.0085, +69.1 bp
  - BNB/4h: p=0.019, +45.6 bp
  → three cross‑asset confirmations (ETH, SOL, BNB) at 4 h.
- Mechanism counts (`n_assets_replicated`, `n_assets_tested`) automatically  
  updated after every experiment.

**State after replications**: M002 meets ≥3 cross‑asset replications but still  
fails the null‑model gate (naïve SMA20 beats it per D024/D025).

---

## 5. Null‑Model Gate and Walk‑Forward Validation (2026-07-21)

**Commits**: `b29ad79` (advancement checks), `342eea8` (auto‑advance to L3),  
`9d05b4e` (multi‑trigger + OI enrichment), `2d83fc3` (M004/M005 triggers),  
`842fd29` (AlphaStream registration and `--review` mode).

**Additions**:
- `run_advancement_checks(mechanism_id)`:
  - **Null‑model gate**: compares mechanism’s best horizon forward return with a  
    naïve `close > SMA20` trigger; requires majority of assets to beat the  
    null model AND p < 0.05 for the mechanism.
  - **Walk‑forward validation**: runs a 6‑fold purged walk‑forward backtest  
    using the mechanism trigger as a long‑only signal; at least 2 positive  
    folds across all tested assets required.
  - If both pass → mechanism acceptance level set to **4 (Walk‑Forward Validated)**,  
    evidence‑ladder hypothesis promoted to L3, and an `AlphaStream` definition  
    persisted to `data/experiments/alpha_streams.json`.
- `_auto_advance_mechanisms()` called at the end of each cycle; automatically  
  triggers `run_advancement_checks` for any mechanism with ≥3 cross‑asset  
  replications that has not yet passed the null‑model gate.
- **Multi‑trigger support**: mechanisms can have multiple trigger variants  
  (e.g., M003 bearish/bullish OI divergence), each tracked separately.
- **OI/funding enrichment**: `_enrich_data()` automatically calls  
  `positioning_enricher.enrich_ohlcv()` for M003 and M004.
- Trigger definitions added for M004 (`funding_over_2p0`, `funding_under_neg2p0`)  
  and M005 (`vol_comp_low`).
- `--review` flag in `run_research_cycle.py` prints a formatted mechanism review  
  table with effect summaries and promotion readiness.
- Persistent AlphaStream records written to `data/experiments/alpha_streams.json`.

**State after these changes**: The scheduler is now capable of autonomously  
discovering, replicating, null‑model‑checking, walk‑forward‑validating, and  
registering mechanisms as portfolio‑ready alpha streams.  M001 and M002 have  
been partially validated; M003‑M005 are queued for testing with their new  
triggers.

---

## 6. Policy and Architecture Decisions (recorded in this conversation)

- Renamed the orchestrator concept from “ResearchDirector” to **ExperimentScheduler**,  
  reflecting the generic scheduler/policy separation.
- Kept the priority function plug‑in and belief state separate to allow future  
  policies (Bayesian, economic, portfolio) without refactoring.
- Adopted a **Bayesian evidence accumulation** model rather than discrete  
  promotion steps; promotion is now based on posterior probability and  
  multi‑factor checks, not just a single p‑value.
- Added **stopping rules** to prevent looping on dead‑ends; blacklisted  
  combinations are never retested unless explicitly requested.
- Ensured that **no new architectural modules** were created (Freeze v1.0):  
  the scheduler is built on existing `EventStudy`, `MechanismRegistry`, and  
  `EvidenceLadder`.

---

## 7. Key Commits Summary

| Hash | Message |
|------|---------|
| `1dca6aa` | fix: correct attribute mapping in mechanism registry load |
| `c21cef2` | feat: add ExperimentScheduler and research cycle script |
| `5c59fc2` | feat: seed validated mechanisms and negative knowledge into ladder |
| `44da78f` | docs: document experiment scheduler implementation |
| `dfdc150` | fix: store per-timeframe effect summaries and document first cycle |
| `9813195` | feat: add Bayesian belief tracking and exploration to scheduler |
| `70ae42c` | feat: add autonomous replication to experiment scheduler |
| `bb07b05` | docs: add second cycle experiment scheduler report for M002 |
| `35b201e` | docs: add M002 replication completion report |
| `b29ad79` | feat: add null-model gate & walk-forward validation for L3 promotion |
| `9d05b4e` | feat: add multi‑trigger support and OI enrichment for M003 |
| `2d83fc3` | feat: add trigger mappings for M004 and M005 and data enrichment |
| `342eea8` | feat: add auto-advance to L3 after 3+ cross-asset replications |
| `842fd29` | feat: auto-register L3 mechanisms as AlphaStreams and add --review mode |

---

## 8. Current System State (2026-07-22)

- **5 mechanisms** registered; 2 (M001, M002) partially validated.
- **3 cross‑asset replications** achieved for M002 (ETH, SOL, BNB) at 4 h.
- **Null‑model gate** available; M002 currently fails (commoditized factor).
- **Walk‑forward** runs pending for M001 after enough replications.
- **Scheduler queue** contains experiments for all mechanisms × symbols × timeframes.
- **AlphaStream definitions** are auto‑created when L3 is reached.
- **Evidence ladder** holds >45 hypotheses, including mechanism‑specific entries.
- **171 tests** passing; no regression introduced by new modules.

---

*Generated by LLM assistant on 2026-07-22 15:00 UTC*
