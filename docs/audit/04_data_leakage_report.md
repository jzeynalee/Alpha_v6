# Data Leakage Report

### DL-001 — Critical — Confidence: High
**Evidence/location:** `src/cv/walk_forward.py`, `PurgedWalkForward.split`.

`self.embargo` is stored but never applied. The next fold's training range includes observations from the previous test interval. A probe with `embargo=5` showed the next training span ending inside the preceding test span.

**Impact:** serial dependence and label contamination can survive the advertised purged walk-forward validation.

**Recommended fix/effort:** enforce the embargo and add gap assertions. Moderate.

### DL-002 — Major — Confidence: High
**Evidence/location:** `EventStudy.cross_asset`.

The method creates an asset-local dataframe and event indices, then calls `_compute_forward_returns`, which reads `self._df` rather than the local asset dataframe.

**Impact:** cross-asset results can use stale/original-asset prices.

**Recommended fix/effort:** make return calculation dataframe-explicit and test distinct synthetic assets. Moderate.

### DL-003 — Major — Confidence: High
**Evidence/location:** `EventStudy.stability_analysis`.

Window-local indices are evaluated against global data. Temporal stability output is therefore misaligned or empty.

**Recommended fix/effort:** fix index/data binding and add chronological-window tests. Moderate.

### DL-004 — Moderate — Confidence: Medium
**Evidence/location:** `event_study.py` and `docs/methodology/event_study_method.md`.

Rolling features use current-bar values and the trigger is measured from the same bar close; no explicit next-bar execution boundary is enforced.

**Impact:** possible close-time look-ahead or optimistic execution assumptions.

**Recommended fix/effort:** define and enforce bar-close/next-open semantics. Small.

### DL-005 — Unable to determine — Confidence: Low
The repository contains forward-fill and resampling for OI, funding, and higher-timeframe signals, but a complete causal timestamp audit of every enrichment path was not possible from the available artifacts.
