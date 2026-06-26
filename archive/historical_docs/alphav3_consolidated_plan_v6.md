# Alpha V3 — Consolidated strategic plan
*Drafted 2026-05-27. Four amendment cycles same day: v2 (A/B framework), v3 (DSR + edge taxonomy + regime fragmentation + interpretability rubric), v4 (cross-walk + Phases E-G), v5 (experiment budget + tradeability floor + result classification + pre-OOS leakage recheck + soft/hard regime tiers + A/B trade-off reporting), v6 (thesis-family registry + Phase A rough cost gate + effective-sample-size deferred work + profitability-dominance policy stance + edge half-life monitoring + gate covariance extension + project-identity criteria). Integrates the profitability audit and four rounds of external auditor review. Governance maturity reaches a stable point at v6; further amendments are deferred until Phase A produces data.*

---

## Document scope and naming

This plan supersedes nothing — it complements `docs/alphav3_profitability_plan_v3.md` (the profitability roadmap) by adding the thesis-first discipline and A/B framework that the roadmap implicitly assumed but did not formalize.

**Phase naming**:
- The profitability roadmap uses numeric Phases 0-5.
- This consolidated plan uses lettered Phases A-G to avoid numeric collision.
- Phase A-D were introduced in v1-v3. Phase E-G (added in v4) explicitly carry forward profitability-roadmap Phases 3-5.

**The mapping table below makes every roadmap item findable in this plan.**

---

## Project identity criteria — what counts as "still Alpha V3" vs. "a new project"

Per the v5 auditor's concern #7: the stop rule ("3 thesis failures → re-evaluate") has a loophole. "Re-evaluation" can silently become "try a totally different project under the same name" — with the same researcher and the same psychological investment, but with completely different assumptions. This is the long-tail version of data dredging that no statistical correction can catch.

The project remains "Alpha V3" — and any prior statistical accounting (DSR n_trials, experiment budget consumption) carries forward — only if ALL of the following stay constant:

| Identity dimension | Must remain |
|---|---|
| Timeframe | 60m bars (changing to 5m or daily = new project) |
| Data source | Nobitex live + LBank training (changing to Bybit/Binance/others = new project) |
| Asset class | BTC + ETH spot (changing to perpetuals, options, or equities = new project) |
| Execution style | Directional event-driven entries (changing to market-making or arbitrage = new project) |
| Label structure | Triple-barrier on ATR (changing to tick-imbalance, holding-period returns, or any other label = new project) |
| Holding period | Sub-week (changing to multi-week or intraday = new project) |

If any single dimension is changed beyond these bounds during a "re-evaluation," the project formally exits Alpha V3 and enters a new branch (Alpha V4, or whatever name is appropriate). The new branch starts with:

- DSR n_trials reset to 0
- Experiment budget reset to 8 theses, 1 retry each, 6 weeks
- A fresh research log under a new project name
- Explicit acknowledgement that all Alpha V3 conclusions DO NOT TRANSFER

**Why this rule exists**: the auditor framed it well — "Otherwise 're-evaluation' can silently become infinite exploration." A change in timeframe or data source is a research decision; it's not wrong to make. But pretending it's a continuation of the same project lets the operator accumulate informal "tries" that aren't counted against statistical accounting.

**What this rule allows**: minor parameter tuning of existing theses, new event-detection rules within the same edge taxonomy class, switching between BTC and ETH within the same Nobitex/LBank universe, refining triple-barrier multipliers (TP/SL/timeout). These are all "still Alpha V3" and consume budget normally.

**The honest interpretation**: this rule may force a decision the operator doesn't want to make. If three theses fail on 60m BTC and the natural next thought is "let me try 5m" or "let me try perpetuals," the rule forces explicitly naming that as a project pivot rather than another retry. That naming has real value — it preserves the scientific integrity of any prior Alpha V3 conclusions and prevents the project name from becoming meaningless.

---

## Mapping to the profitability roadmap

| Profitability roadmap | Status as of v4 | Lives in this plan as |
|---|---|---|
| Phase 0 (data + governance + leakage audit) | Done (shipped earlier) | Implicit pre-requisite; not re-litigated |
| Phase 1 (signal-flow loosening — deter_alpha, entropy, CSS bypass) | Done | Implicit pre-requisite |
| Phase 2.0 (alpha_theses.md) | Template shipped; concrete theses written in Phase A | **Phase A** of this plan (active) |
| Phase 2.1 (triple-barrier labels) | Done (`src/labels/triple_barrier.py`) | Used by Phase A thesis tests |
| Phase 2.2 (two-model meta-labeling) | Code shipped, never trained on passing labels | Phase B if a thesis passes Phase A |
| Phase 2.3 (25-feature selection) | Done (`scripts/select_features.py`) | Phase B input |
| Phase 2.4 (isotonic calibration) | Done; ran; Brier ≈ 0.25 outcome | Diagnostic input to Phase A. Recall: result told us *individual features don't predict next-bar direction*; thesis test goal is to find an event/setup that *does* produce asymmetric outcomes |
| Phase 2.5 (purged walk-forward CV) | Done (`src/cv/walk_forward.py`) | Used in every Phase A thesis test |
| Phase 2.6 (4 benchmarks: BH, EMA-X, ATR breakout, random-same-exits) | Done (`src/backtest/strategies.py`) | Used by **Phase F** (Phase 2.7 14-criterion verifier on integrated strategy) |
| Phase 2.7 (14-criterion verifier) | Built (`src/validation/phase2_verifier.py`); never run on a trained model | **Phase F** of this plan — runs only if Phase A produces a passing thesis and Phase B/C integrate it |
| **Phase 3 (regime specialisation: 5-regime structural classifier; regime-as-feature or per-regime LightGBM)** | Not done | **Phase E** of this plan |
| **Phase 4 (robustness: adaptive thresholds, incremental penalty re-enable, frozen-OOS single-evaluation)** | Not done | **Phase F** of this plan |
| **Phase 5 (live hardening: PSI drift, Almgren-Chriss slippage, kill switches, paper trade)** | Not done | **Phase G** of this plan |

**Phase ordering rule**: A → B → C → D → E → F → G. Each phase strictly gated on the previous one's exit criterion. No skipping ahead.

**The "if Phase A passes" gate runs deep**: if Phase A fails (no thesis survives strict + DSR criteria), Phases B-G are all moot. The plan does not pretend otherwise.

---

## Executive summary

Alpha V3 has matured from infrastructure construction to thesis validation. This is the correct evolution. The remaining strategic risk is no longer engineering quality — it is whether genuine edge exists, and whether the existing architecture preserves or destroys that edge once found.

This plan commits to nine things:

1. **A frozen architecture during thesis discovery.** No new layers, models, features, or adaptive systems until at least one thesis passes honestly.
2. **Information decay measurement at every pipeline stage.** Currently missing. Without it we cannot tell which architectural components help vs. hurt — and we cannot detect the most serious risk: multiplicative gating collapse.
3. **A sequenced thesis-validation pipeline** that runs up to five pre-registered experiments before re-evaluating the project's overall direction.
4. **A formal A/B test framework for component replacement.** Any proposed replacement of an existing component (HMM → price-action regime engine, Granger → entropy-only causal layer, etc.) must pass a pre-registered five-dimensional A/B test against the incumbent before adoption. Close ties go to the incumbent because change has its own cost.
5. **Formal multiple-testing correction via Deflated Sharpe Ratio + thesis-family registry.** Every thesis test must produce a DSR with n_trials reflecting the total number of theses tested to date, with within-family variants inflated at 1.5× / 2.0× multipliers to prevent soft re-parameterization from understating sequential-testing contamination.
6. **Regime fragmentation diagnostics in Phase C.** Per-regime sample sizes, transition matrix stability, and calibrator availability across folds must be measured. Statistical starvation in any regime invalidates results in that regime. Three-tier classification (Healthy/Sparse/Starved) distinguishes "informational caution" from "results invalid."
7. **Explicit carrying-forward of profitability-roadmap Phases 3, 4, 5 as Phases E, F, G** with no implicit deletions. Phase E = regime specialisation; Phase F = robustness + frozen-OOS verifier; Phase G = live hardening + kill switches + paper trade + edge half-life monitoring.
8. **Hard scope ceilings, tradeability minimums, pre-OOS leakage recheck, and Phase A rough cost gate.** Together these prevent: Phase A sprawling beyond budget, economically irrelevant strategies advancing, silent leakage introduced during iteration, and untradeable raw edges passing Phase A only to die in Phase B.
9. **Project identity criteria.** Changing timeframe, data source, asset class, execution style, or label structure beyond defined bounds is formally a new project (Alpha V4), not a continuation. Prevents "re-evaluation" from becoming infinite drift.

The plan integrates:

- Recommendations from the external profitability audit (verbatim where adopted)
- The auditor's review of v2 (DSR, edge taxonomy, regime fragmentation, objective interpretability)
- Prior thesis-first analysis from the in-conversation review
- Explicit disagreements with the audit and the reviewer, with reasoning, where they exist
- The operator's principle that replacement requires *measured* improvement, not academic preference

---

## What is decided vs. what remains open

### Decided
- The pullback-continuation thesis test (already shipped, 15/15 smoke tests green) will run as-is. No threshold relaxation. No parameter changes.
- After the pullback result, the next two theses to test are event-driven (per audit recommendation): failed-MR continuation, and volatility compression breakout.
- An information-decay diagnostic will be added to the pipeline before Option 3 (full-architecture test) is run on any passing thesis.
- The architecture is frozen during thesis discovery. Operational definition below.
- **The A/B test framework (see "A/B test framework for component replacement" below) is the binding decision procedure for any future component replacement, including HMM → price-action and Granger removal.**
- **The HMM-replacement and Granger-removal decisions are explicitly deferred to Phase C.** Both proposals have merit, but the data to decide them does not exist until a thesis has passed Phase A. Until then, both decisions are open.

### Open (decided after first thesis result)
- Whether to test the third audit-recommended thesis (liquidity sweep reversal)
- Whether to relax pullback parameters and re-test (deliberately conservative — only if no thesis passes)
- Whether to begin Phase B (minimal integration) or move to architecture simplification
- **HMM → price-action regime engine** (Phase C A/B, only if Phase A produces a passing thesis)
- **Granger removal in favour of entropy-only causal layer** (Phase C A/B, same gating)

---

## Acknowledged data-source limitations

The auditor correctly noted that microstructure, flow, and structural edges are likely more durable than the directional-event edges Phase A will test. This plan accepts the limitation and makes it visible:

| Edge type | Testable with current data? | Why |
|---|---|---|
| Trend continuation (pullback, breakout) | Yes | OHLCV is sufficient |
| Mean reversion (sweep + reclaim) | Yes | OHLCV is sufficient |
| Volatility expansion (compression breakout) | Yes | ATR derived from OHLCV |
| Flow/liquidation cascades | **No** | Requires liquidation feed (not in Nobitex/LBank public APIs) |
| Funding/open-interest distortions | **No** | Requires perpetual futures data; Nobitex is spot |
| Microstructure (queue, order book imbalance) | **No** | Requires L2 / tick data, not OHLCV |

**Operational implication**: Phase A is constrained to directional-event hypotheses. This is a known limitation, not an oversight. If all Phase A theses fail, expanding the data-source set (e.g., adding Bybit perpetual data for funding rates) becomes a candidate for Phase A.2 — a separate, scoped data project. We do not pursue it now.

**Why we accept the limitation**: directional event edges in crypto DO exist (post-news overreaction, momentum continuation around round-number breakouts, mean-reversion after liquidity sweeps) — just not as durably as flow-based edges. Phase A's job is to find ANY edge worth refining. If we find one, Phase B/C will surface whether it's durable enough; if it isn't, that's also an answer.

---

## Edge taxonomy — required for every passing thesis

Per the auditor's v2 review: every thesis that passes Phase A is classified into one of these categories. The classification is recorded in the research log and accompanies the thesis through Phase B, C, D — because the category determines what Phase B should worry about most.

| Edge Type | Examples | Phase B/C primary concerns |
|---|---|---|
| **Trend continuation** | pullback continuation, breakout-after-compression | Decay under trend regime shift; cost sensitivity |
| **Mean reversion** | reclaim after sweep, exhaustion bounce | Asymmetric tail risk; sharp regime breaks |
| **Volatility expansion** | compression → expansion breakout | Requires volatility regime classification; execution timing sensitive |
| **Flow / liquidation** | liquidation cascades, forced unwinds | Requires flow data (not currently available; see limitations above) |
| **Structural** | funding/OI distortions, basis arbitrage | Requires perpetual data (not currently available) |
| **Market microstructure** | queue effects, depth imbalance | Requires L2 data (not currently available) |

For Phase A, all current candidate theses (pullback, failed-MR, volatility breakout, liquidity sweep) fall into the first three rows. **This is acknowledged as a limitation, not a feature.** The taxonomy makes the limitation visible.

A thesis's edge taxonomy classification is the FIRST entry written into its research log entry, before pass/fail is even known.

---

## Experiment budget (hard ceilings)

Per the v4 auditor's review: the "stop rule" (3 thesis failures → re-evaluate) is necessary but not sufficient. Without explicit budget ceilings, "this isn't really a new thesis, just a refined version of the last one" becomes the loophole that lets Phase A sprawl indefinitely.

Hard ceilings, pre-committed:

| Limit | Value | Rationale |
|---|---|---|
| Total Phase A theses + variants | 8 | At cumulative DSR n_trials = 8, the bar for new theses is already high. Beyond 8, we're almost certainly mining noise. |
| Maximum retries per thesis | 1 | A failed thesis gets ONE rewrite (e.g. different ATR multiplier). After that the thesis is closed. |
| Maximum total Phase A duration | 6 calendar weeks | Hard wall-clock limit. If 6 weeks pass without a passing thesis, we exit Phase A even if budget remains. |

**A "variant"** is any modified version of a thesis that re-tests on the same data. Examples:
- Same pullback rule with 3% threshold instead of 2% → variant, counts against budget
- Same triple-barrier with timeout=24 instead of 48 → variant, counts against budget
- Pullback on ETH instead of BTC → variant, counts against budget
- A genuinely new event definition (e.g. "post-volume-spike reversal") → new thesis, counts against budget

**At budget exhaustion**: project-level re-evaluation per the stop rule. Possible outcomes:
- Project pivots to a different timeframe / different data
- Project pivots to a different research direction
- Project enters extended pause for data acquisition (e.g. perpetual futures feed for flow theses)
- Project closes

These are honest outcomes. Sprawling Phase A is not.

### Variant accounting

The research log must record, for each test:
- Whether it's a NEW thesis or a VARIANT
- If variant, what changed from the parent
- Cumulative variant count for the parent thesis (must not exceed 1)
- Cumulative project count (must not exceed 8)
- Cumulative wall-clock time in Phase A (must not exceed 6 weeks)

The budget is enforced by the log, not by the script. The script reports its own n_trials; the operator (you) is responsible for keeping the log honest.

### Thesis family registry (per v5 auditor's concern #1)

DSR with cumulative n_trials corrects for *explicit* trial count. It does not fully correct for **adaptive hypothesis generation** — the human tendency to refine a failed thesis into a "new" thesis that's actually a soft re-parameterization. Without correction, a researcher who tests "pullback at 2%, then 3%, then 4%, then 5%" can claim four data points of evidence when statistically they're closer to one.

The remedy: classify every thesis into a **family**, and inflate DSR n_trials more aggressively for within-family variants than for genuinely new families.

**Initial family taxonomy** (extensible, but new families must be declared in the research log before testing):

| Family | Member theses |
|---|---|
| Trend continuation | pullback continuation, breakout-after-compression, momentum follow-through |
| Mean reversion | reclaim after sweep, exhaustion bounce, range-edge fade |
| Volatility expansion | compression → expansion breakout |
| Event reaction | post-news reversal, post-liquidation rebound (requires data not currently available) |
| Structural | funding/OI distortion (requires data not currently available) |

**The n_trials inflation rule**:

- A genuinely new family-first thesis (e.g., the FIRST mean-reversion test): `n_trials += 1.0` (standard)
- A within-family variant or refinement (e.g., changing pullback threshold from 2% to 3%): `n_trials += 1.5`
- A within-family variant after one prior variant has already been tested (e.g., third pullback parameterization in a row): `n_trials += 2.0`

The 1.5 / 2.0 multipliers are heuristic. The auditor is honest about this: "the exact multiplier is itself heuristic, but the *direction* is correct and the bias is conservative." We accept the conservatism. If anything, the multipliers may be too lenient — the alternative is to use them and document the choice rather than guess at first principles.

**Why this matters operationally**: it makes it computationally expensive to do soft re-parameterization. A fourth pullback-family variant would need to clear DSR with effective n_trials = 1.0 + 1.5 + 2.0 + 2.0 = 6.5, which is meaningfully harder than the literal four trials would suggest. This discourages the failure mode without forbidding it.

**The research log records, for every test**:
- Family classification
- Whether the test is family-first, within-family-variant, or repeated-variant
- Effective n_trials contribution (1.0 / 1.5 / 2.0)
- Cumulative effective n_trials (not just count)

The DSR computation uses the cumulative effective n_trials, not the raw count.

---

## Tradeability floor — what counts as a viable strategy

Per the v4 auditor's review: statistical validity (DSR > 0, expectancy ≥ 0.2R, PF ≥ 1.3) is necessary but not sufficient. A strategy that passes Phase A criteria but trades 4 times a month at $10 per trade is technically valid and economically pointless. The plan needs an explicit floor for "tradeable" that filters out statistically significant but economically irrelevant strategies.

A thesis is "tradeable" (and therefore eligible to advance from Phase A to Phase B) if and only if it satisfies BOTH the statistical criteria AND ALL of:

| Floor | Value | Why |
|---|---|---|
| Trades per week (median over folds) | ≥ 3 | Below this, fixed costs (capital allocation, monitoring overhead) dominate; the strategy doesn't justify operational attention. |
| Expected monthly edge per unit capital | ≥ 1.5% gross | After fees (~0.3% RT × turnover), should yield ≥ 0.5% net monthly. Below this, the strategy doesn't beat a high-yield savings account meaningfully. |
| Turnover (round-trip cost per dollar of capital per month) | ≤ 30% gross | Above this, fees eat the edge. Specifically: a 0.30% RT cost × 30% turnover = 0.09% drag per month, manageable. Higher turnover means edge has to be unrealistic to overcome cost. |
| Capital scalability (Almgren-Chriss notional ceiling before slippage ≥ 5% of expectancy) | ≥ $50K notional | Below this, the strategy is a research curiosity not a vehicle for capital. Adjusted for the actual capital being deployed; this floor is a default. |

**These are floors for advancing to Phase B, not floors for being "interesting."** A thesis that passes statistical criteria but fails tradeability floors is classified as LOW_TRADEABILITY (see classification system below) — preserved as evidence, not advanced.

These numbers are heuristic. They can be revised at any time, but only BEFORE a thesis is evaluated against them, not after. Pre-registration applies to tradeability floors the same way it applies to PASS criteria.

---

## Result classification system

Per the v4 auditor's review: the binary PASS/FAIL classification is too coarse. Real Phase A outcomes fall into five categories, and treating them differently preserves information without compromising discipline.

| Classification | Definition | Phase B eligibility |
|---|---|---|
| **PASS** | Meets all strict criteria (expectancy ≥ 0.2R, PF ≥ 1.3 per fold, ≥4/5 positive folds, ≥50 events/fold) AND DSR > 0 AND meets all tradeability floors | Yes — proceed to Phase B |
| **BORDERLINE** | Fails exactly one strict criterion, but DSR > 0 AND expectancy > 0 AND meets tradeability floors | No — archive only. Future candidate for ensemble, regime-specific deployment, or richer-data revisit. **Cannot be retroactively re-classified as PASS.** |
| **LOW_SAMPLE_REVIEW** | Strong expectancy and DSR > 0 but events per fold < 50 | No — archive only. May indicate a rare-but-real edge that needs longer/different data. **Not promoted to Phase B alone.** |
| **LOW_TRADEABILITY** | Passes all statistical criteria but fails at least one tradeability floor | No — archive only. Statistically real but economically inert. |
| **FAIL** | Everything else | No — closed |

**The archival categories are not consolation prizes.** They cost the same budget slot as a FAIL. They count against the 8-thesis ceiling. They consume retries the same way a failure does. The discipline is preserved; only the *visibility* of weak-but-real signal improves.

**No retroactive reclassification**: a BORDERLINE thesis stays BORDERLINE forever. We do not "promote" it to PASS after seeing later data or running additional variants. The original pre-registered criteria determine the classification permanently.

---

## Where this plan agrees with the audit

The following audit recommendations are adopted in full:

| Audit recommendation | Status |
|---|---|
| Freeze architecture growth until edge is validated | Adopted (with operational definition below) |
| Build thesis-validation pipeline as core workflow | Adopted — already in motion via pullback experiment |
| Treat Alpha V3 as alpha refinery, not generator | Adopted as framing principle |
| Measure information decay across layers | Adopted — to be built before Option 3 |
| Next three theses should be event-driven | Adopted — sequencing in Phase A below |
| Volatility-normalized pullback threshold (for future thesis variants) | Adopted as future-experiment design rule |

## Where this plan adopts the auditor's v2 review

The auditor reviewed v2 and identified specific operational gaps. Adopted:

| Auditor v2 recommendation | Status |
|---|---|
| Add formal multiple-testing correction (DSR is the chosen method) | **Adopted in A.0** — every Phase A thesis must produce DSR > 0 with cumulative n_trials |
| Add edge taxonomy classification for every passing thesis | **Adopted** — section above, mandatory research log entry |
| Strengthen interpretability scoring (replace Yes/Partial/No with objective rubric) | **Adopted in A/B framework** — 4-question rubric (modified for solo operator) |
| Add regime fragmentation diagnostic | **Adopted in C.2** — measures per-regime sample sizes, transition stability, calibrator availability per fold |
| Acknowledge directional-beta limitation of current theses | **Adopted** — explicit "Known data-source limitations" section |
| Reframe information-decay diagnostic primary purpose as multiplicative gating collapse detection | **Adopted in C.1** — diagnostic re-stated as primarily about gating collapse |

## Where this plan adopts the auditor's v4 review

The auditor reviewed v4 (Phases E-G added) and proposed seven items. Five are adopted; one is declined; one is acknowledged without amendment.

| Auditor v4 recommendation | Status |
|---|---|
| Addition 1: explicit experiment budget (8 theses, 1 retry, 6 weeks) | **Adopted** in "Experiment budget" section above |
| Addition 2: leakage recheck immediately before frozen-OOS | **Adopted as F.3.5**, a mandatory gate before F.4 |
| Addition 3: define "tradeable" with concrete minimums | **Adopted** in "Tradeability floor" section above |
| Risk 1: BORDERLINE classification for one-criterion-fail with DSR > 0 | **Adopted** in "Result classification system" |
| Risk 2: LOW_SAMPLE_REVIEW classification for strong-but-sparse events | **Adopted** in "Result classification system" |
| Risk 4: soft/hard tiers for regime fragmentation | **Adopted in C.2** — three-tier classification (Healthy/Sparse/Starved) replaces v3's binary threshold |
| Risk 3: "production-operability override" letting interpretability/robustness defeat profitability | **Declined as override; adopted as reporting requirement.** The override mechanism would reintroduce subjective judgment exactly where the framework was supposed to remove it. Instead, every REJECTED A/B test now requires explicit trade-off reporting in the log so the rejected-but-interesting cases stay visible. See "Mandatory trade-off reporting" in the A/B framework section. |
| Risk 5: psychological preparation for "most layers may be net negative" | **Acknowledged without amendment.** The plan already commits in Phase D to remove layers that destroy edge. The auditor's reminder is valuable but does not change the document. Operator self-discipline is the only mitigation. |

## Where this plan adopts the auditor's v5 review

The auditor reviewed v5 and identified seven remaining concerns. All seven are addressed in v6 — some as full adoptions, some as scheduled deferrals with explicit triggers.

| Auditor v5 concern | Status |
|---|---|
| #1: Thesis family registry — DSR alone doesn't correct for adaptive hypothesis generation | **Adopted** — see "Thesis family registry" subsection of Experiment Budget. Within-family variants inflate n_trials at 1.5× / 2.0× multipliers (heuristic but bias-conservative). |
| #2: Phase A admits theses that won't survive cost reality | **Adopted as A.0.1** — simple fixed-fee (0.30% RT) subtracted from R-multiples before Phase A pass criteria. Not full slippage; rough order-of-magnitude floor only. |
| #3: 50 events/fold may be 15-20 effective due to clustering | **Deferred to Phase B** with explicit trigger and method (block-bootstrap effective N). Documented in "Deferred work" section. |
| #4: A/B rule encodes profitability dominance, which is a policy choice not a neutral default | **Adopted as documentation** — see "Policy stance" subsection of A/B framework. The rule stays; the policy choice is now explicit, with the conditions under which it could be revisited. |
| #5: Edge half-life is not measured (passes OOS, collapses 2 months later) | **Adopted as G.7** — three post-deployment decay diagnostics (rolling expectancy, rolling PF, retraining sensitivity) with explicit kill-switch thresholds. |
| #6: Information-decay diagnostic misses pairwise gate interactions | **Adopted as C.1 extension** — pairwise ablation triggered when single-layer effects don't sum to measured total. Computationally cheap (15 extra runs) and only when evidence warrants. |
| #7: Stop rule has a loophole — "re-evaluation" can become infinite project drift | **Adopted as "Project identity criteria"** new top-level section near document scope. Six identity dimensions; changing any beyond bounds = new project (Alpha V4), DSR reset, budget reset, no carryover. |

## Where this plan disagrees with the audit

The following audit recommendations are *not* adopted as written, with reasoning:

| Audit recommendation | This plan's position |
|---|---|
| "Make pass criteria looser for first-stage discovery (PF > 1.1 aggregate, mean expectancy > 0)" | **Rejected.** Multiple-testing across 3-5 theses turns a 5% nominal threshold into a 23% family-wise rate. Strict thresholds (0.2R, 1.3 PF per fold, 4/5 folds positive) act as informal Bonferroni protection. **Mitigation**: also report the looser metrics as diagnostics, but pass/fail uses the strict ones. |
| "Treat CSS layer as experimental until proven" | **Modified.** Agreed in direction, but we don't litigate the methodology — we *measure* the layer's effect on edge once a thesis passes. If CSS reduces edge, drop it; if it preserves it, keep it. This is empirical, not philosophical. |
| "HMM contributes only entropy estimation and contextual uncertainty" | **Partially correct.** HMM also drives the regime-aligned series that calibration and CSS depend on. Removing it is a bigger surgery than implied. Keep as context per audit, but understand it has more reach than the audit acknowledges. |
| "Final production system should be far smaller, less mathematically exotic" | **Treated as hypothesis, not foregone conclusion.** Will be tested by information-decay measurement, not assumed. |

---

## The architecture freeze — operational definition

A "freeze" is meaningless without rules. Effective immediately, the following are **prohibited** during thesis discovery (Phase A):

| Prohibited | Allowed |
|---|---|
| New ML model in any layer | Bug fixes to existing models |
| New feature columns in `features_engineering.py` | Fixing the `xtf` resolves-to-zeros bug (already-deferred) |
| New causal-inference methods | Diagnostic scripts that *measure* the existing causal layer |
| New regime-detection logic | Replacing broken HMM artefact files (operational, not architectural) |
| New gating layers in `alpha_factory` | Removing or short-circuiting existing layers for measurement |
| New adaptive online systems | Logging and instrumentation only |
| New pipeline orchestration | Pre-registered thesis test scripts under `scripts/` |

**A layer or component can only be added if it passes a measured A/B test showing it preserves or improves edge.** That A/B test does not exist yet. Until it does, no new layers.

The freeze ends when ONE of:
- A thesis passes pre-registered criteria AND Option 3 (full-architecture test) shows the architecture preserves the edge
- Three theses fail and we explicitly re-scope the project

---

## Phase A — Thesis Discovery (immediate)

### A.0 — Formal pass criteria for every Phase A thesis

Per the auditor's v2 review: every thesis test in Phase A must pass ALL of the following. These are pre-registered and not adjusted after seeing results.

**Strict thresholds (already in v2)**:
- Mean expectancy across folds ≥ 0.2R
- Profit factor per fold ≥ 1.3
- At least 4 of 5 folds positive (mean R > 0)
- At least 50 events per fold

**New: formal multiple-testing correction via Deflated Sharpe Ratio**:
- Compute DSR using the realized fold Sharpes
- `n_trials` parameter = total number of Phase A theses + variants tested to date (cumulative, project-lifetime)
- DSR must be > 0 (and report the value; > 0.5 is "strong", > 1.0 is "exceptional")

**Why DSR with cumulative n_trials**: each thesis test increases the project's family-wise error rate. The DSR's `n_trials` argument adjusts for this. The auditor was correct that v2's "informal Bonferroni" was hand-waving; this is the formal correction.

**Practical implication**: a thesis that passes the strict thresholds but produces DSR ≤ 0 is **FAILED**. We do not adopt it for Phase B. It tells us "the expectancy is real but it's likely a sampling artifact given how many things we've tested."

**Where DSR is computed**: existing implementation in `src/core/layers/survival_gate.py` from Phase 2. The thesis test script will be updated to call it and include the result in the pass/fail decision.

**A note on n_trials growth**: as Phase A progresses, n_trials grows. This makes later theses harder to pass than earlier ones, which is statistically correct — but it means DSR for the pullback test (n_trials=1) will be computed differently from the fourth thesis (n_trials=4+). The research log must record n_trials at the time of each test so historical results remain interpretable.

### A.0.1 — Rough cost gate in Phase A (per v5 auditor's concern #2)

The v5 plan deferred all transaction-cost modeling to Phase B. The auditor noted that this risks admitting fragile edges in Phase A that won't survive realistic execution friction. PF ≥ 1.3 raw can become PF ≈ 1.0-1.15 after a 0.30% RT fee × moderate turnover, and Phase A would never see it.

The remedy is a **simple fixed-fee cost approximation in Phase A itself** — not full Almgren-Chriss, just a single fixed RT cost subtracted from each trade's R-multiple before computing expectancy / PF.

**The Phase A cost floor**:

| Parameter | Value | Justification |
|---|---|---|
| Round-trip fee | 0.30% | Conservative for crypto retail (taker 0.10% × 2, plus 0.10% spread+slippage allowance) |
| Per-trade cost in R-multiples | `0.003 × entry_price / atr_at_entry` | Converts fee from price-fraction to ATR-units (R-multiples) |
| Net R-multiple | `gross_R - cost_R` | Subtracted from each trade's R-multiple before any aggregation |

**Where applied**: in the thesis test script's `label_event_bars` function. After computing `r_multiple = pnl / atr`, subtract `cost_R = 0.003 × entry_price / atr`. All Phase A pass criteria (expectancy, PF, fold positivity, DSR) are computed on the NET R-multiple, not the gross.

**What this changes for the in-flight pullback test**: the smoke-tested script is gross-only. Before running on real data, it needs a one-function patch to subtract the fixed cost. The smoke tests can stay as-is — they test the plumbing, not the cost model.

**What this does NOT do**:
- It does not model slippage (next bar's open might differ from current bar's close by more than the spread)
- It does not model market-impact (large positions move the market)
- It does not model spread asymmetry (long vs short cost may differ)

These refinements live in Phase B (full cost model) and Phase F (Almgren-Chriss for > 1% ADV). Phase A only needs to be honest about the rough order of magnitude.

**Honest acknowledgement**: 0.30% RT is conservative for liquid pairs (BTCUSDT/ETHUSDT) but might be optimistic for less liquid pairs or smaller exchanges. The floor stays at 0.30% for Phase A as a uniform standard. Lower fees in production would only make passing theses MORE likely to survive Phase B; higher fees in production would invalidate Phase A passes that don't hold up under realistic costs.

### A.1 — Pullback continuation thesis (in flight, awaiting your run)

**Status**: script shipped, 15/15 smoke tests green, ready for real-data run.

**Action**: run against `v2_lbank` BTCUSDT 60m. Send the full per-fold log.

**Branching**:
- **PASS_BOTH** → proceed to A.2 (information-decay diagnostic), then Option 3 on this thesis.
- **PASS_LONG_ONLY** or **PASS_SHORT_ONLY** → same as PASS_BOTH but restricted to the passing side.
- **FAIL** with healthy event counts → thesis cleanly rejected. Proceed to A.3 (next thesis).
- **FAIL** with too few events per fold → flag for follow-up. Don't relax parameters reflexively. Document and move to A.3.

**Time cost**: ~30 seconds for the run, ~5 minutes for honest interpretation.

### A.2 — Information-decay diagnostic (build only if A.1 passes)

A new script `scripts/measure_information_decay.py` that:

1. Runs the full `alpha_factory` pipeline on the event bars from the passing thesis
2. Captures the alpha value at every stage: raw, post-calibration, post-CSS, post-entropy, post-execution, post-capacity, post-deter_alpha, post-min-edge
3. For each stage, computes the trade outcome correlation: does signal at this stage still predict the triple-barrier label?
4. Outputs a "where signal dies" report

This is the diagnostic the audit demanded. It must exist before Option 3 produces interpretable results.

**Estimated complexity**: ~300 lines. Single experiment script style. No new architecture.

**Does NOT violate the freeze** — it's pure measurement.

### A.3 — Second thesis: failed mean reversion → continuation

If A.1 fails or once A.1/A.2 are complete and we want to expand evidence base.

**Specification (pre-registered)**:
- Universe: BTCUSDT, 60m, LBank
- Event: price closes below `swing_low(lookback=10) - 0.5×ATR` (sweep below recent low), then within 3 bars closes back above swing_low (reclaim)
- Entry: bar after reclaim confirmation
- Triple-barrier: same as pullback (TP=2×ATR, SL=1×ATR, timeout=48)
- Walk-forward: same (5 folds, embargo=24)
- Pass criteria: same strict thresholds

**Time cost**: 1-2 hours to write the script (different event-detection logic from pullback), 30 seconds to run.

### A.4 — Third thesis: volatility compression breakout

**Specification (pre-registered)**:
- Universe: BTCUSDT, 60m, LBank
- Event: ATR(14) percentile rank ≤ 20th over rolling 200-bar window AND range(close, lookback=20) / ATR(14) ≤ 1.5 (range compression)
- Direction: long if `close > SMA(50)` at compression resolution, short otherwise
- Entry: bar after compression breaks (close > recent range high, or < range low)
- Triple-barrier: same as pullback
- Walk-forward: same
- Pass criteria: same

**Time cost**: same as A.3.

### A.5 — Fourth thesis: liquidity sweep reversal (audit recommendation #C)

Run only if A.1-A.4 produce mixed or null results.

**Specification**: pre-registered before running, structurally similar to A.3 but with the reversal-after-sweep framing.

### A.6 — Stop rule

After three thesis failures, re-evaluate. **Do not** keep tweaking thesis definitions to find one that passes — that's data dredging at the project level.

Possible re-evaluation outcomes:
- The feature engineering needs structural rework (event-driven features replacing generic TA)
- The dataset needs a different timeframe or symbol
- The project needs a different question entirely (e.g., volatility arbitrage instead of directional alpha)

This rule prevents the project from looping indefinitely in Phase A.

---

## Phase B — Minimal integration (gated on Phase A success)

This phase runs only if at least one thesis passes A.1's pass criteria.

### B.1 — Strip the architecture to bare bones for the passing thesis

Connect:
- Event detection from the passing thesis
- Triple-barrier labels (Phase 2 module)
- Walk-forward CV (Phase 2 module)
- Risk manager (existing, position sizing only)
- Backtest engine (existing)

Disable for this phase:
- HMM regime gating (or restrict to logging only)
- CSS causal weighting
- Feature evidence layer
- Decision layer ML
- `deter_alpha` confirmation
- Entropy discount
- Capacity discount

Measure end-to-end expectancy at this stripped-down baseline. **This is the number every architectural layer added later must beat.**

### B.2 — Add transaction costs

Realistic maker/taker fees and slippage. Re-measure expectancy. If edge disappears at this stage, the strategy is non-tradeable regardless of architecture.

### B.3 — Out-of-sample held-out test

Fence off the most recent 20% of bars. Refit any thresholds on the earlier 80%. Evaluate the held-out 20%. Real edge survives this. Overfit edges don't.

---

## Phase C — Controlled layer testing (gated on Phase B)

### C.1 — Information-decay diagnostic (FIRST in Phase C)

Run the diagnostic from A.2 (which was built when the first thesis passed). Its **primary purpose is detecting multiplicative gating collapse** — the failure mode the auditor identified as the largest unresolved technical risk in the v2 plan.

Specifically, the diagnostic measures the predictive correlation (signal-to-label) at each stage:

```
raw thesis output  →  calibrated  →  CSS-weighted  →  entropy-discounted  →
execution-adjusted  →  capacity-discounted  →  deter_alpha-gated  →  min-edge-filtered
```

For each stage, compute the correlation between that stage's output and the eventual triple-barrier label.

**The thing to watch for** (paraphrasing the auditor's example):
> raw edge = 0.12R expectancy
> calibration removes 20%
> entropy removes 25%
> deter_alpha removes 40%
> min-edge removes remaining weak tails
> → Final: beautiful confidence metrics, no surviving trades, dead CAGR.

If the diagnostic shows steady attenuation with no single layer being catastrophic, the system is over-gating uniformly. If a single layer destroys most of the signal, that layer is the prime candidate for the layer-by-layer A/B test below.

**Gate covariance extension (per v5 auditor's concern #6, triggered by data)**

Independent attribution of layer effects can miss interaction effects. The auditor's example: "entropy gate alone reduces expectancy 10%, deter_alpha alone reduces expectancy 8%, together they reduce expectancy 65%." This is the canonical nonlinear gating-collapse pattern.

Decision rule: after running single-layer ablations, compute the sum of individual layer attenuations and compare to the measured total attenuation. If:

```
sum_of_individual_attenuations - measured_total_attenuation > 0.10
```

(i.e., individual effects "explain" 10+ percentage points MORE attenuation than what's actually present, meaning the layers have positive interactions and partially cancel each other)

OR

```
measured_total_attenuation - sum_of_individual_attenuations > 0.10  
```

(i.e., layers interact destructively, causing more attenuation together than individually — the nonlinear collapse pattern)

Then extend the diagnostic to **pairwise gate ablation**:
- For each pair of layers (i, j), run the strategy with BOTH disabled and measure expectancy
- Compute the interaction term: `measured_with_both_disabled - (measured_with_i_disabled + measured_with_j_disabled - baseline)`
- Large positive interaction terms indicate destructive pairs that destroy more edge together than individually

With 6 candidate layers (HMM gate, CSS, FeatureEvidence, Decision, deter_alpha, min-edge), pairwise analysis is `C(6,2) = 15` extra runs. Computationally cheap once the single-layer baseline is set up.

**The remediation**: pairs with large destructive interactions become candidates for combined removal in Phase D simplification. Removing one layer of a destructive pair may be insufficient; the architecture may need both removed to recover edge.

**Trigger discipline**: pairwise analysis runs ONLY if the additive-vs-total comparison shows >10% discrepancy. We don't run 15 extra ablations speculatively; we run them when there's evidence of interaction.

### C.2 — Regime fragmentation diagnostic (per auditor's v2 review, refined in v5)

A risk specific to HMM-driven and regime-conditioned pipelines: per-regime calibrators and decision models can become statistically starved when one regime has too few samples. The earlier calibration log already showed this: `Neutral: 30842 / Bull: 13329 / Bear: 5830`. Bear has 1/5 the samples of Neutral. Per-regime fits on Bear are fragile.

Build a fragmentation diagnostic (`scripts/measure_regime_fragmentation.py`) that reports, for each fold:

**Three-tier classification per metric** (per v4 auditor — replaces v3's binary threshold):

| Metric | Healthy | Sparse (informational) | Starved (results invalid for that regime) |
|---|---|---|---|
| Per-regime sample size | ≥ 500 events | 200–499 | < 200 |
| State transition matrix Frobenius distance fold-to-fold | ≤ 0.20 | 0.20–0.35 | > 0.35 |
| Per-(regime, fold) calibrator availability | ≥ 80% | 50–79% | < 50% |
| State occupancy imbalance ratio (max/min coverage) | ≤ 6:1 | 6:1 to 10:1 | > 10:1 |

**Interpretation rules**:
- A regime that is **Healthy on all four metrics** → results valid, included in aggregate metrics
- A regime that is **Sparse on one or more metrics but not Starved on any** → results reported but flagged "low confidence — sparse"; included in aggregate with explicit caveat
- A regime that is **Starved on any metric** → results for that regime are **excluded** from aggregate metrics. The strategy is reported as "no-trade in that regime"

**Why three tiers, not two**: the v3 binary threshold made the diagnostic noisy. A Bear regime with 480 events is meaningfully different from one with 50, but the binary threshold treated both as "failed." Three tiers preserve the diagnostic's purpose (catch statistical starvation) without false binary alarms.

This diagnostic also gates the HMM A/B test: if the existing HMM produces fragmented regimes on the actual data, the comparison against a price-action regime engine is partly testing "does the alternative regime engine produce healthier sample sizes?" — which is a legitimate question but should be measured explicitly.

### C.3 — Layer-by-layer A/B

For each architectural layer (HMM gate, CSS, FeatureEvidence, DecisionLayer, deter_alpha):

1. Run the strategy WITH the layer
2. Run the strategy WITHOUT the layer
3. Compare: expectancy, profit factor, max DD, trade count, Sharpe
4. Adopt the layer only if it strictly improves at least one metric without degrading any other

**Layers that fail this test get removed from the live path.** This is the operational form of the audit's "measure information decay" recommendation.

Specifically watch for:
- `deter_alpha`: high probability of improving Sharpe while destroying CAGR through over-filtering (audit's specific concern). The information-decay diagnostic from C.1 will reveal this BEFORE the A/B is even run.
- Multiplicative gating cascade: the layers most at risk of attenuating signal below the min-edge threshold

### C.4 — Component-replacement A/B tests

Now (and only now) the deferred HMM and Granger questions are evaluated using the framework formalized below. Both decisions are made with measured edge from a passing thesis, regime fragmentation already characterized, and information decay mapped.

---

## Phase D — Production simplification (gated on Phase C)

Once profitable, aggressively simplify. The audit's hypothesis is that the final system will be much smaller than current Alpha V3. This plan treats that as a hypothesis to test, not a foregone conclusion. The data from Phase C decides.

If Phase C shows most layers preserve edge → keep them
If Phase C shows most layers destroy edge → remove them

Either way, the criterion is measured impact, not architectural preference.

---

## Phase E — Regime specialisation (gated on Phase D; profitability-roadmap Phase 3)

Carries forward §3 of the profitability roadmap (`docs/alphav3_profitability_plan_v3.md`).

**Enter only if** Phase D produced a profitable simplified architecture AND the layer-by-layer Phase C A/B retained at least one regime-aware component (HMM or price-action regime engine).

### E.1 — Structural regime classifier

Per profitability-roadmap §3.1. Five regimes:
- TREND_UP_EXPANSION
- TREND_DN_EXPANSION
- COMPRESSION
- MEAN_REVERSION
- HIGH_NOISE

Implementation file: `src/core/structural_regime.py`. Pure rule-based on swing structure, ATR percentile, and trend persistence — no ML training.

If Phase C's HMM A/B selected the price-action regime engine over HMM, the structural classifier built here is the same component. If Phase C kept HMM, the structural classifier is an addition for explicitly slicing performance by structural state.

### E.2 — Regime-conditioned modelling

**Option 1 (default)**: single LightGBM with `regime` as categorical feature.

**Option 2 (only if Option 1 leaves > 0.2 PF on the table by regime)**: one LightGBM per regime, `HIGH_NOISE` → hard no-trade.

The Option-1-vs-Option-2 decision uses the same A/B framework as Phase C: pre-registered thresholds, incumbent (Option 1) wins ties.

### E.3 — Phase E exit criterion

Re-run on validation:
- [ ] PF after fees ≥ Phase D baseline + 0.10
- [ ] Sharpe ≥ Phase D baseline + 0.2
- [ ] No regime has negative expectancy (mark no-trade if so)
- [ ] All Phase A's strict criteria still met (DSR, expectancy, PF, folds, events)
- [ ] Phase F's full 14-criterion verifier (next section) still passes on validation window

If a regime has zero or negative expectancy, mark it no-trade. Do not delete it — operators need to know which regimes the strategy stands aside in.

---

## Phase F — Robustness + frozen-OOS verifier (gated on Phase E; profitability-roadmap Phases 2.7 + 4)

Carries forward §2.7 (14-criterion verifier) + §4 (adaptive thresholds, incremental penalty re-enable, frozen-OOS single evaluation) of the profitability roadmap.

**Enter only if** Phase E produced a profitable, stable, regime-conditioned strategy.

### F.1 — Adaptive threshold (rolling quantile)

Per profitability-roadmap §4.1:

```python
threshold = (0.55 if len(history) < 200
             else float(np.quantile(history, 1 - target_trade_rate)))
```

`target_trade_rate` set to match the observed trade rate from Phase E.

### F.2 — Re-enable execution penalties incrementally

Per profitability-roadmap §4.2. Re-enable in this order. After EACH step run full validation backtest and verify **PF stays > 1.05 net of fees**. Roll back the last change if PF drops below 1.05.

1. CSS multiplier (rebuild CSS table on the 25-feature set from Phase B)
2. Entropy discount (`entropy_high_threshold: 0.7`, `discount: 0.5`)
3. `c_threshold: 0.65`
4. `precision_floor: 0.55`
5. `eqs_alert_threshold: 0.60`, `eqs_suspend_threshold: 0.40`

This is the *empirical* form of the audit's "multiplicative gating collapse" concern. If a penalty drops PF below 1.05, that's evidence the penalty kills more edge than it adds robustness. Roll back.

### F.3 — Run the full 14-criterion Phase 2.7 verifier on validation

Per profitability-roadmap §2.7. Module already exists: `src/validation/phase2_verifier.py`. All 14 criteria must pass on the validation window.

The criteria (re-stated here so the plan is self-contained):

**Profitability (3):**
- closed_trades ≥ 300
- profit_factor (after fees) > 1.10
- net Sharpe (annualised, after fees) > 0.8

**Turnover (3):**
- avg gross edge per trade ≥ 2 × round-trip cost
- net edge per trade > 0
- median holding time > 6 bars

**Stability (4):**
- no single trade > 15% of total PnL
- no single calendar month > 30% of total PnL
- rolling 30-day Sharpe positive on ≥ 4 of 6 windows
- rolling 30-day win rate within ±15 pp of overall

**Benchmark beats (4):**
- beats buy & hold on Sharpe
- beats EMA(20)/EMA(50) crossover on net PF
- beats ATR breakout on net PF
- beats random-entry-same-exits on net PF by margin > 0.15

If any criterion fails, do not proceed to F.4. Re-evaluate at Phase A level (different thesis, different parameters).

### F.3.5 — Pre-OOS leakage recheck (per v4 auditor's review)

**Mandatory gate before F.4 runs.** The leakage audit from Phase 0 was passed at project start. But during iterative development through Phases A-F, leakage can re-enter the pipeline through:

- New features added during Phase B/C/E integration (forward-fill, expanding-window normalization, etc.)
- Recalibration of thresholds that accidentally peeks at validation
- Threshold tuning on validation that's been re-used as the "test" for so long it's effectively training data
- Code refactors that drop the `confirmed:bool` enforcement on swing detection
- Scaler fits that became `fit_transform` on combined data

Re-run all ten checks from `docs/leakage_audit.md` and verify `LeakageGuard(strict=True)` shows zero violations on a fresh backtest of the validation window. Update `docs/leakage_audit.md` with the re-verification date and any new findings.

**If any check fails**: do NOT proceed to F.4. The frozen-OOS window must not be touched until leakage is eliminated. Fix the leak, retrain, rerun F.3, then re-attempt F.3.5.

**Why this gate exists**: F.4 is a one-shot evaluation. If we discover post-F.4 that leakage contaminated the training data, the OOS window is burned — we cannot re-use it after touching it. The pre-OOS recheck is the project's last chance to catch silent leak introduction before the one-shot evaluation.

### F.4 — Single frozen-OOS evaluation

**This is the highest-stakes single check in the entire project.** Per profitability-roadmap §4.3: run ONCE on the frozen-OOS window (2026-01-01 → 2026-05-01 in the original plan; updated to whatever window is current and untouched). **Whatever the result, do not retune.**

Acceptance criteria for "live-capital ready":

**Profitability:**
- OOS PF > 1.05 after fees
- OOS Sharpe > 0.7
- OOS max drawdown < 1.5 × validation max drawdown
- OOS trade count ≥ 0.7 × validation trade count

**Stability:**
- No single OOS trade > 15% of OOS PnL
- Rolling 30-day OOS Sharpe positive on majority of windows

**Drift diagnostic:**
- OOS feature PSI vs training < 0.25 on ≥ 22 of 25 features
- OOS AUC within 0.05 of validation AUC

If OOS fails: **do not trade**. Validation methodology was insufficient. Wait for new data; treat the OOS window as part of training going forward.

The frozen-OOS rule is the project's single strongest defense against overfitting. Honor it.

---

## Phase G — Live hardening + paper trade + deploy (gated on Phase F; profitability-roadmap Phase 5)

Carries forward §5 of the profitability roadmap.

**Enter only if** Phase F.4 passed all criteria on the frozen-OOS window.

### G.1 — PSI drift monitoring

Per profitability-roadmap §5.1:

```python
def psi(reference, current, n_bins=10):
    bins = np.quantile(reference, np.linspace(0, 1, n_bins + 1))
    ref = np.histogram(reference, bins=bins)[0] / len(reference) + 1e-9
    cur = np.histogram(current,   bins=bins)[0] / len(current) + 1e-9
    return float(np.sum((cur - ref) * np.log(cur / ref)))
```

Hooked into `OfflineTrainer` drift-triggered retrain. Thresholds:
- PSI < 0.1 → stable, no action
- 0.1 ≤ PSI < 0.25 → caution, log alert
- PSI ≥ 0.25 → retrain (actionable)

### G.2 — Live-vs-backtest alpha alignment monitor

Mirror every live trade through the backtest engine on the historical-aligned bar; compare `alpha_final` and `proba_alpha`. Alert if mean absolute error > threshold over 10 consecutive trades.

### G.3 — Almgren-Chriss slippage

Enable the slippage model in the live cost calculation when position size > 1% ADV. Below that threshold, fixed-fee approximation is sufficient.

### G.4 — Nine kill-switch triggers

Per profitability-roadmap §5.4 (Amendment G). All nine must be implemented and tested before any live capital. The nine triggers cover:

1. Data feed lag exceeds threshold
2. Bid-ask spread blow-out
3. Model output collapse (probability outputs cluster at one extreme)
4. Latency budget breach
5. Daily PnL drawdown limit
6. Strategy-level drawdown limit
7. Portfolio-level drawdown limit
8. EQS suspension threshold
9. Alpha alignment monitor (G.2) tripped

Each trigger must have:
- Pre-registered threshold
- Tested fire path (a simulated breach actually halts trading in a test environment)
- Documented un-suspend procedure (often manual review only)

### G.5 — Paper-trade for 30 days

Per profitability-roadmap §5.5. After Phase F.4 passes and G.1-G.4 are in place, run the strategy in paper mode for 30 calendar days.

Pass criterion: live PF within 30% of frozen-OOS PF. If paper-trade PF is dramatically lower than OOS PF, something about the live environment (latency, fill model, data feed) differs from the backtest in a way that wasn't captured. Investigate before deploying.

### G.6 — Deploy capital

Only after G.5 passes. Start with the smallest position size the broker allows. Scale up only after at least 3 consecutive months of live performance within ±30% of OOS expectations.

### G.7 — Edge half-life monitoring (per v5 auditor's concern #5)

Phase F and G measure stability *at a point in time* — does the strategy work on OOS? But the canonical crypto failure mode is different: a strategy that passes OOS in May and collapses by August. The v5 auditor noted: "crypto directional edges often decay rapidly. A strategy can pass OOS, survive walk-forward, then collapse within 2 months."

The remedy is **continuous post-deployment decay monitoring**. Three diagnostics run continuously once a strategy is live:

**G.7.1 — Rolling expectancy decay**

Compute trailing-30-day expectancy in R-multiples, then trailing-60-day, trailing-90-day. Plot the ratio:

```
decay_30_to_oos  = expectancy_last_30d / expectancy_oos
decay_60_to_oos  = expectancy_last_60d / expectancy_oos
decay_90_to_oos  = expectancy_last_90d / expectancy_oos
```

Healthy: ratios stay within ±30% of 1.0 (consistent with OOS performance).
Caution: ratios drop to 0.5-0.7 (edge is decaying but still positive).
Action: ratios drop below 0.5 (edge has decayed by half or more).

Action threshold triggers kill switch G.4.* (added as the tenth kill-switch trigger: "edge half-life decay below 50%").

**G.7.2 — Rolling PF decay**

Same structure for profit factor. Trailing 30/60/90 day PF compared to OOS PF. Same Healthy / Caution / Action ratios.

**G.7.3 — Retraining interval sensitivity**

Every 30 calendar days, refit any models (calibrators, decision model if present) on the now-extended training data and compare:
- New model's predictions on the holdout vs the original model's predictions
- If the new model would have made different decisions on >20% of trades, the underlying data distribution has shifted enough to warrant a full retraining (not just calibrator refit)

**Why this lives in Phase G, not earlier**: edge half-life is only measurable post-deployment. Phase F's frozen-OOS evaluation is a single time-slice snapshot. Half-life requires a rolling window of live performance.

**Honest acknowledgement**: this is post-deployment monitoring, not pre-deployment validation. A strategy can pass everything through Phase F and still fail G.7 within months. The plan accepts this: edge decay is real, monitoring catches it, kill switches stop trading before it becomes catastrophic. There's no way to fully predict decay from pre-deployment data.

---

## A/B test framework for component replacement

This section formalizes how *any* architectural replacement decision gets made, including HMM → price-action and Granger removal. It is the binding decision procedure; informal arguments about "this is more principled" or "this is more sophisticated" do not override it.

### The principle

A proposed replacement is adopted if and only if it is **measurably better** along the dimensions that matter, on the actual problem. Academic merit, mathematical elegance, and aesthetic preference do not enter the decision. Close ties favour the incumbent because change has its own cost (engineering time, retraining cost, risk of introduced bugs).

### The five measurements

For each A/B test, the following are computed on the same passing thesis from Phase A, on the same data, with the same triple-barrier and walk-forward parameters:

| # | Dimension | Metric | Direction |
|---|-----------|--------|-----------|
| 1 | **Profitability** | Mean expectancy across walk-forward folds, with transaction costs | Higher better |
| 2 | **Robustness** | Standard deviation of expectancy across folds | Lower better |
| 3 | **Interpretability** | Four-question rubric, see below | Higher better |
| 4 | **Stability** (context) | Proportion of bars where the component's output is consistent with the previous bar | Higher better; informational only |
| 5 | **Cost** (context) | Training time, online compute, lines of code, external dependencies | Lower better; informational only |

Measurements 1-3 are decisive. Measurements 4-5 are reported alongside for transparency but do not by themselves trigger acceptance or rejection.

### Interpretability rubric (objective)

Per the auditor's v2 review: manual interpretability scoring becomes biased once profitability is known. The auditor proposed a 4-question objective rubric. This plan adopts it with one modification for a small-team operational reality.

Each question is binary (1 or 0). Total score is 0-4. The treatment must score at least equal to the incumbent.

| # | Question | Test |
|---|----------|------|
| 1 | Can the output be decomposed into deterministic components? | For a chosen sample bar, can you list the inputs and operations that produced the label? If yes (e.g., "swing high 1.5 ATR above current close, ATR percentile rank 78, three consecutive higher closes → regime=trend_up"), score 1. If "the HMM emission probability was 0.74" → score 0. |
| 2 | Is the explanation written BEFORE profitability is known? | Operational anti-anchoring rule. The interpretability write-up is committed to the research log with a timestamp PRIOR to running the A/B measurement. (Replaces the auditor's "two operators" criterion, which is impractical for solo work.) Score 1 if explanation timestamp < measurement timestamp; else 0. |
| 3 | Are state transitions stable over neighboring bars? | Pick 100 random bars. For each, compare the component's output at bar t vs. bar t-1. If output changes on > 30% of neighboring pairs, the component is "flickering" — score 0. Else score 1. |
| 4 | Can failure cases be enumerated explicitly? | Can you describe, in concrete terms, what inputs would cause this component to produce a wrong output? "Regime label will be wrong when the trend changes within the lookback window" is enumeration. "The neural network might fail in edge cases" is not. Score 1 if at least 2 concrete failure modes are enumerated; else 0. |

A score of 4/4 is "fully interpretable." 3/4 is "operationally acceptable." 2/4 or below means the component is too opaque to debug productively.

### Why these questions, not others

The auditor's original "two operators independently reproduce explanation" is the cleanest objective test but presumes a team of two. For solo work it collapses to "can the operator explain twice consistently?" which is weaker than write-before-measure. The substitution preserves the bias-protection intent.

### The pre-registered decision rule

A replacement is **ADOPTED** if and only if ALL of:

- Improves profitability OR robustness by ≥ 10% relative
- Does NOT degrade the other (profitability or robustness, whichever was not improved) by more than 5% relative
- Interpretability score is at least equal to the incumbent
- Cost is within 2× of the incumbent (no order-of-magnitude regressions)

A replacement is **REJECTED** if any of those conditions fail.

A **close result** (improvement <10% on the primary dimension, even if no degradation elsewhere) is also REJECTED. The incumbent wins ties.

The pre-registration is: these thresholds are committed *before* the A/B test runs. They are not retroactively adjusted after seeing results.

### Mandatory trade-off reporting (added in v5 per auditor's Risk 3)

The v4 auditor noted a legitimate concern: real systems sometimes trade small profitability degradation for substantial robustness or interpretability gains. The plan declined to add a "production-operability override" because subjective override mechanisms tend to reintroduce confirmation bias. Instead, **A/B tests that fail the strict rule but show meaningful trade-offs must report those trade-offs explicitly.**

For every REJECTED A/B test, the log entry must include:

| Field | Value |
|---|---|
| Profitability delta | % change vs incumbent |
| Robustness delta | % change vs incumbent |
| Interpretability delta | Score change (e.g., 3/4 → 4/4) |
| Cost delta | Multiplier vs incumbent |
| Why rejected | Specific criterion that failed |
| Notable trade-off pattern | E.g. "+28% robustness with -3% profitability — would adopt under override-style policy" |

This preserves visibility into rejected replacements without compromising the discipline. Future-you (or a future engineer) reviewing the log can see *what was nearly adopted* and decide whether the project's risk tolerance has shifted enough to warrant revisiting.

**It does NOT allow current-you to override the rule.** Trade-off reporting is for forward visibility, not retrospective re-litigation.

### Policy stance — why the A/B rule encodes profitability dominance (per v5 auditor's concern #4)

The v5 auditor noted, correctly, that the A/B rule's "improve one dimension ≥10%, no degradation >5%" structure functionally encodes **profitability dominance**. A replacement with +35% robustness, +20% interpretability, but -6% profitability gets rejected, even though it might be the better operational choice in many production contexts.

This plan makes the policy stance explicit rather than hiding it:

**Profitability dominance is a deliberate policy choice, not a neutral default.** The reasoning:

1. **Phase A's whole point** is establishing that profitable edge exists. Once we have edge, the dominant project risk is *losing* that edge through architectural changes. Sacrificing profitability for other dimensions inverts the project's value function.

2. **In a research stage**, the asymmetry of error matters. A replacement that destroys 6% of edge is unrecoverable; a replacement we rejected that would have improved robustness is recoverable (we can revisit later when more data is available). Asymmetric error → conservative rule.

3. **Interpretability and robustness without profitability** are infrastructure investments. They have value in scaling and operations but not in proving edge exists. Until we're confident the project has edge to scale, profitability dominance is the right priority.

4. **The trade-off reporting** keeps the rejected-but-interesting cases visible. If at a later phase (say Phase D or beyond) the project's risk tolerance changes — e.g., we have many profitable strategies and now care most about operations — the policy stance can be explicitly revisited, with the trade-off log providing the evidence.

**What this means for HMM → price-action**: if the price-action regime engine produces +25% robustness and +1 point of interpretability at -4% profitability cost, the framework REJECTS it. That's the correct call given the current policy stance.

**What would change the policy stance**: a deliberate, documented decision (probably in Phase D or later) to revisit the rule when the project's bottleneck shifts from edge-discovery to edge-scaling. Not a one-off override.

### Operational protocol

For each A/B test:

1. **Define the swap precisely.** Which file changes. Which interface stays identical. What in the pipeline is held constant. Document in a one-page spec before any code is written.
2. **Build the treatment.** New file alongside the incumbent — do NOT modify the live path. The A/B is run by importing one or the other.
3. **Run on the passing Phase A thesis.** Same data, same triple-barrier params, same walk-forward folds.
4. **Compute all five measurements** for both pipelines. Output a single comparison table.
5. **Apply the decision rule mechanically.** If the rule says ADOPT, integrate the treatment and retire the incumbent. If REJECT, document why and retire the treatment branch.
6. **Log the result** in `docs/research_log.md`. Future engineers (or future-you) need to know what was tried, what passed, what failed.

### Caveats acknowledged

These honest limitations are noted but not solved here:

- **The interpretability score is subjective.** Two operators might score the same component differently. Mitigation: write the explanation BEFORE seeing the profitability number, so the score isn't anchored to the result.
- **The 10%/5% thresholds are heuristic, not derived.** They reflect a bias toward keeping the incumbent unless improvement is meaningful. If you have a stronger basis for different thresholds (e.g., from significance testing), use that — but pre-register the change before running.
- **A/B test depends on Phase A producing a passing thesis.** If no thesis passes, these A/B tests cannot run meaningfully — there's no signal to gate, so gating-mechanism comparisons are meaningless. The HMM and Granger decisions remain genuinely deferred.

### Why this lives in Phase C, not earlier

The temptation is to A/B the HMM and Granger decisions *now*, in parallel with thesis discovery. This plan rejects that for three reasons:

1. **No passing thesis = no meaningful A/B.** We'd be measuring two ways to gate a non-signal. Whichever wins, the result tells us nothing about live performance.
2. **It would violate the freeze rule.** Building a price-action regime engine is 2-3 weeks of architecture work. Doing it before a thesis passes is exactly the infrastructure-first pattern the freeze rule exists to prevent.
3. **Sequencing matters.** Phase A → Phase B → Phase C is the discipline. Parallel tracks dilute the discipline and the project drifts.

The HMM and Granger questions are real and worth answering. They will be answered when there is something concrete to measure them against. Until then they are explicitly deferred.

### What this framework does NOT permit

- Replacing a component because it is "academically newer" or "mathematically more elegant"
- Replacing a component because of intuition, even strong intuition
- Replacing a component because an external audit recommended it
- Tuning the 10%/5% thresholds after seeing the A/B result
- Selecting which measurement to emphasize based on which makes the treatment look better
- Running multiple A/B tests on the same component until one passes (data dredging at the experiment level)

### Applied: HMM → price-action regime engine (Phase C, gated)

**Control**: Phase A's passing thesis with the existing HMM-based regime context.

**Treatment**: same thesis with a price-action regime engine. Engine inputs: swing structure (from existing Layer 1 swing detector), ATR percentile rank over rolling 200 bars, count of consecutive same-direction bars, distance from rolling N-bar median. No new ML training; pure rule-based.

**Build cost**: 2-3 weeks if pursued. Only pursued if Phase A produces a passing thesis worth gating.

**Decision**: by the rule above.

### Applied: Granger removal (entropy-only causal layer)

**Control**: existing CSS table built by `causal_trainer.py` with Granger pre-filter + TE.

**Treatment**: rebuilt CSS table from a sibling script (e.g., `causal_trainer_te_only.py`) that bypasses Granger. TE thresholds may need recalibration since Granger was a pre-filter.

**Build cost**: a few hours of modification + recalibration.

**Decision**: by the rule above.

**Note**: this is closer to the freeze rule's boundary because it modifies an existing component, not adds a new one. The plan allows it because it's a *simplification* and an explicit A/B, but the freeze rule needs interpretation here, not mechanical application.

---

## Disagreements with the audit — detailed

### Disagreement 1: Pass criteria looseness

**Audit recommendation**: For first-stage discovery, relax to `mean expectancy > 0` and `PF > 1.1 aggregate`.

**Plan's position**: Keep strict thresholds. Report looser metrics as diagnostics, not pass conditions.

**Reasoning**: Multiple-testing across 3-5 thesis tests means a 5% nominal threshold becomes ~23% family-wise (1 - 0.95^5). The audit's looser thresholds would worsen this. Strict thresholds act as informal Bonferroni protection. The cost of false acceptance (building Phase B on a noise-passing thesis) is much higher than the cost of false rejection (testing one more thesis).

**Mitigation**: All looser metrics will be reported in the thesis test output for visibility, but the pass/fail decision uses the strict criteria.

### Disagreement 2: Causal layer as "experimental"

**Audit recommendation**: Treat CSS / Granger / TE subsystem as experimental until proven.

**Plan's position**: Measure the layer's effect on edge, don't litigate the methodology.

**Reasoning**: The audit raises legitimate concerns about TE on nonstationary data, but the move is empirical: if Phase C shows CSS reduces edge, drop it. If it preserves edge, keep it. We don't need to reason from first principles about whether PCMCI+ is reliable on crypto regimes — we can measure.

**Operational effect**: identical to what the audit recommends, just framed differently.

### Disagreement 3: HMM scope

**Audit recommendation**: HMM mainly contributes entropy estimation and regime uncertainty.

**Plan's position**: HMM also drives the regime-aligned slicing that calibration and CSS depend on. Bigger surgery than implied.

**Reasoning**: From the actual code review in `alpha_factory.py`, HMM output flows into multiple layers, not just the entropy discount. Replacing it would require co-modifying calibration, CSS, and the decision layer.

**Operational effect**: keep HMM as context (agreed with audit). Don't pursue the "market structure state engine" replacement during Phase A (audit also defers this).

### Disagreement 4: "Production system will be much simpler"

**Audit recommendation**: Final production system should be far smaller, less mathematically exotic.

**Plan's position**: This is a hypothesis to test via Phase C measurement, not a foregone conclusion.

**Reasoning**: While many successful retail trading systems are simple, many profitable institutional systems are quite complex. Without measurement, "simpler is better" is folk wisdom, not strategy.

**Operational effect**: identical to the audit at the next 3-month horizon (run Phase A, then B, then C). Beyond that, the data decides.

---

## What this plan deliberately does not do

| Not doing | Reason |
|---|---|
| Throw away existing infrastructure | Reusable for any future quant project, even if not the current direction. Sunk cost ≠ wasted. |
| Build new architectural components | Forbidden by the freeze rule. Including no new causal methods, no market-structure state engine, no new feature families. |
| Tune the pullback thresholds after seeing results | Data dredging; explicitly prohibited by pre-registration. |
| Optimize for a specific Sharpe ratio target | Phase A is about edge existence, not edge quality. Quality comes later. |
| Add live-trading hooks for any new strategy | Phase B/C is offline-only. Live deployment only after a strategy passes both. |
| **Replace HMM with price-action regime engine YET** | **Deferred to Phase C, decided by A/B test against measured edge. The audit recommended it; this plan agrees it's plausible but requires measurement, not intuition.** |
| **Remove Granger from the causal layer YET** | **Same deferral and same A/B procedure.** |
| **Build the price-action regime engine speculatively** | **2-3 weeks of work that produces useful information only if a thesis passes Phase A. Premature.** |

---

## Deferred work (acknowledged, scheduled, not blocking)

These items are real issues the v5 auditor identified. They are not yet implemented but have explicit triggers and scheduled phases. Documented here so they don't get forgotten.

| Item | Concern source | Trigger condition | Phase to implement |
|---|---|---|---|
| **Effective sample size estimation** (cluster-adjusted CIs) | v5 auditor concern #3 — 50 nominal events may be 15-20 effective due to clustering | A thesis passes Phase A and goes to Phase B | Phase B — measure block-bootstrap effective N alongside nominal N. If effective N < 30 per fold, treat the thesis as LOW_SAMPLE_REVIEW retroactively. |
| **Pairwise gate interaction analysis** | v5 auditor concern #6 — individual layer ablations miss interaction effects | C.1 single-layer information-decay analysis shows attenuation not fully explained by additive layer effects | Phase C — extend C.1 to pairwise gate ablation. Adds C(6,2)=15 extra runs if all six layers are present. |
| **Decay-aware retraining schedule** | v5 auditor concern #5 — edges decay even after passing OOS | Strategy enters Phase G (paper trade or live) | Phase G.7 (newly added) — monitor rolling expectancy and PF; trigger retraining or kill switch on decay |
| **Spread / latency / slippage modeling beyond fixed-fee** | v5 auditor concern #2 — Phase A uses 0.30% RT as a rough approximation | Strategy passes Phase A and enters Phase B | Phase B already covers basic costs; Phase F adds Almgren-Chriss for >1% ADV positions |

The pattern: every deferred item has a specific trigger and a specific phase. None are "we'll think about it later." They are scheduled work, just not yet active.

If Phase A fails entirely (no thesis passes), most of these items become moot — they're improvements to a system that doesn't yet have edge. They remain documented as part of the plan in case Alpha V3 or its successor reaches that stage.

---

## Tracking and accountability

A simple research log under `docs/research_log.md` will record:

- Each thesis test: pre-registration date, parameters, result, JSON/MD report path
- Each freeze-violation candidate: what was proposed, who proposed it, whether the freeze rule applied
- Each information-decay measurement: which layer, what was measured, what was concluded

This is the project's defense against drift back into infrastructure-first habits. Without a log, the freeze rule degrades within weeks.

---

## Immediate next action

Run the pullback thesis script against real data:

```powershell
python scripts/test_pullback_thesis.py --data-version v2_lbank
```

Send the full output. Branching from there per A.1's outcome.

---

## Summary table — what changes this week vs. before

| Aspect | Before | After |
|---|---|---|
| New code commits | Infrastructure-heavy | Pre-registered thesis tests only |
| New layers added | Yes, multiple | Zero (freeze) |
| Pass/fail criteria | Often implicit | Pre-registered strict thresholds PLUS DSR > 0 with cumulative n_trials |
| Multiple-testing correction | Informal hand-waving | Formal DSR per A.0 |
| Architecture trust | Assumed to add value | Tested by A/B measurement in Phase C |
| Component replacement | By intuition or audit recommendation | By pre-registered 5-dimensional A/B with strict thresholds; close ties go to incumbent |
| Interpretability scoring | Subjective Yes/Partial/No | Objective 4-question rubric, including write-before-measure rule |
| Workflow | Build → hope edge emerges | Define thesis → test (with DSR) → integrate minimally → measure |
| HMM / Granger decisions | Under active discussion | Explicitly deferred to Phase C, gated on A/B test |
| Regime fragmentation | Not measured | Measured in C.2 (sample size, transition stability, calibrator availability per fold) |
| Edge taxonomy | Not classified | Required for every passing thesis |
| Acknowledged limitations | Implicit | Explicit data-source limitations section |
| Profitability-roadmap Phases 3-5 | Implicit in v1-v3 (risk of being forgotten) | Explicitly carried forward as Phases E, F, G with full content |
| Frozen-OOS rule | Buried in old plan | Explicit in F.4 — "the single highest-stakes check in the project" |
| Live deployment path | Unclear | Phase G with PSI / kill switches / paper trade explicitly required |
| Experiment budget | No hard cap | 8 theses, 1 retry each, 6 weeks calendar — pre-committed |
| Tradeability floor | Implicit | 4 explicit minimums (trades/week, monthly edge, turnover ceiling, capital scalability) |
| Pre-OOS leakage recheck | Trusted from Phase 0 | Mandatory re-run as F.3.5, immediately before F.4 |
| Result classification | Binary PASS/FAIL | 5 classes (PASS / BORDERLINE / LOW_SAMPLE_REVIEW / LOW_TRADEABILITY / FAIL); only PASS advances |
| Regime fragmentation tiers | Binary threshold | Healthy / Sparse / Starved — three tiers, finer-grained interpretation |
| A/B trade-off visibility | Lost on rejection | Reported in research log for every REJECTED test |
| Adaptive hypothesis generation | DSR n_trials += 1 per test | Within-family variants: n_trials += 1.5 or 2.0 (thesis family registry) |
| Phase A cost reality | Deferred to Phase B | Rough fixed-fee (0.30% RT) subtracted from R-multiples in Phase A itself (A.0.1) |
| A/B profitability dominance | Implicit | Explicit policy stance with the conditions under which it could be revisited |
| Edge half-life monitoring | Not present | Phase G.7 — rolling expectancy/PF decay, retraining sensitivity, kill-switch trigger |
| Gate covariance | Single-layer only | Extended to pairwise (15 ablations) when single-layer effects don't sum to total |
| Project identity | Implicit | Six dimensions; changing any = new project (Alpha V4), DSR reset, budget reset |
| Project pace | Fast forward motion | Slower, more deliberate, more honest |

The last row is the one that matters most. This plan deliberately moves slower than the project has been moving, because the project's biggest risk was no longer slow progress — it was confident progress in the wrong direction.
