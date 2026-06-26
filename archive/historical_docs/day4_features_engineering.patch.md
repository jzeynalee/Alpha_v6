# patches/day4_features_engineering.patch
#
# Day 4 — HMSRE-Lite integration into features_engineering.py
#
# This file describes the exact changes needed to features_engineering.py.
# It is NOT a unified diff; it's a documented set of edits because the
# original file (line numbers) may have drifted by the time you apply it.
# All edit anchors are unique within the file as of the audit baseline.
#
# Auditor note: the integration runs HMSRE-Lite ONCE on the assembled
# feature dataframe AFTER batching, NOT inside calculate_indicators().
# Reason: calculate_indicators is called per-batch; running HMSRE inside
# would compute swings on incomplete data with chunk-boundary effects.
# By running HMSRE at the generate_features level (after batching has
# produced the final concat), we get one consistent set of HMSRE features
# across the full timeline.
#
# ─────────────────────────────────────────────────────────────────────
# Edit 1: Add HMSRE import at the top of features_engineering.py
# ─────────────────────────────────────────────────────────────────────
#
# Find the existing imports block. After the last existing import,
# add:
#
# ANCHOR (find this existing line, then insert AFTER it):
#     from src.features.market_structure import ...    # or similar existing line
#
# INSERT:
#
#     try:
#         from src.features.hmsre import compute_hmsre_features
#         _HMSRE_AVAILABLE = True
#     except ImportError as e:
#         logger.warning("HMSRE-Lite not available: %s. Features will be 0.0.", e)
#         compute_hmsre_features = None
#         _HMSRE_AVAILABLE = False
#
# ─────────────────────────────────────────────────────────────────────
# Edit 2: Add three hint attributes to __init__
# ─────────────────────────────────────────────────────────────────────
#
# ANCHOR (existing __init__):
#     def __init__(self, db_connector=None, warmup=True):
#         # Feature computation should not depend on DB
#         self.db = db_connector
#         if warmup:
#             self._warmup_numba()
#
# REPLACE WITH:
#
#     def __init__(self, db_connector=None, warmup=True):
#         # Feature computation should not depend on DB
#         self.db = db_connector
#
#         # HMSRE-Lite hints (Day 4 integration). Callers should set these
#         # BEFORE calling generate_features() if they want HMSRE features.
#         # When unset, HMSRE columns will be 0.0 (the fallback contract).
#         self._symbol_hint: Optional[str] = None
#         self._primary_tf_hint: str = "60"
#         self._data_version_hint: str = "v2"
#
#         if warmup:
#             self._warmup_numba()
#
# ─────────────────────────────────────────────────────────────────────
# Edit 3: Add _compute_hmsre_columns_safe helper method
# ─────────────────────────────────────────────────────────────────────
#
# Insert this new method AFTER calculate_indicators and BEFORE
# _update_incremental:
#
#     def _compute_hmsre_columns_safe(
#         self,
#         df: pd.DataFrame,
#     ) -> Dict[str, np.ndarray]:
#         """Compute HMSRE-Lite market_state + trend_strength columns.
#
#         Safe wrapper: never raises. On any failure (missing data,
#         module unavailable, runtime error) returns 0.0-filled columns
#         of length len(df). The L4 dtype filter accepts float32 columns
#         and the model treats 0.0 as the WAITING/RANGE state.
#         """
#         n = len(df)
#         if not _HMSRE_AVAILABLE or compute_hmsre_features is None:
#             return {
#                 "market_state":   np.zeros(n, dtype=np.float32),
#                 "trend_strength": np.zeros(n, dtype=np.float32),
#             }
#
#         try:
#             return compute_hmsre_features(
#                 df,
#                 symbol=self._symbol_hint,
#                 primary_tf=self._primary_tf_hint,
#                 data_version=self._data_version_hint,
#             )
#         except Exception as e:
#             logger.warning(
#                 "HMSRE-Lite feature computation failed: %s. "
#                 "Returning 0.0 columns.", e
#             )
#             return {
#                 "market_state":   np.zeros(n, dtype=np.float32),
#                 "trend_strength": np.zeros(n, dtype=np.float32),
#             }
#
# ─────────────────────────────────────────────────────────────────────
# Edit 4: Inject HMSRE columns in generate_features (POST-batching)
# ─────────────────────────────────────────────────────────────────────
#
# ANCHOR (existing generate_features end):
#         if len(df) > self.BATCH_SIZE and batch_processing:
#             logger.info(f"Large dataset ({len(df):,} rows). Using batch processing...")
#             return self._process_in_batches(df)
#         else:
#             return self._sanitize_column_names(self.calculate_indicators(df))
#
# REPLACE WITH:
#
#         if len(df) > self.BATCH_SIZE and batch_processing:
#             logger.info(f"Large dataset ({len(df):,} rows). Using batch processing...")
#             result = self._process_in_batches(df)
#         else:
#             result = self._sanitize_column_names(self.calculate_indicators(df))
#
#         # HMSRE-Lite integration (Day 4) — runs ONCE on the assembled
#         # feature dataframe so swing detection sees a consistent timeline
#         # rather than batch-by-batch chunks with seam artifacts.
#         #
#         # The features are added in-place. If HMSRE is unavailable or
#         # fails, the helper returns 0.0-filled float32 columns, which
#         # the L4 dtype filter accepts and the model interprets as the
#         # WAITING/RANGE state.
#         hmsre_cols = self._compute_hmsre_columns_safe(result)
#         result["market_state"]   = hmsre_cols["market_state"]
#         result["trend_strength"] = hmsre_cols["trend_strength"]
#
#         return result
#
# ─────────────────────────────────────────────────────────────────────
# Edit 5: Handle _update_incremental (live path) — last-value propagation
# ─────────────────────────────────────────────────────────────────────
#
# In the incremental path (live trading), HMSRE features for the new bar
# should be taken from the prior bar (last-value propagation). This is
# acceptable staleness for Sub-Phase 1A (design v3 §4.4):
#   - On a 60m primary TF, HMSRE is recomputed by the next full
#     generate_features() pass (typically once per pair_tf refresh)
#   - Between refreshes the live engine just uses the prior committed
#     state, which is correct because state machine output is
#     piecewise-constant in time
#
# Find the area near the end of _update_incremental where new_row is
# being assembled (before return), and add:
#
#     # HMSRE features (Day 4): propagate from prior bar (staleness
#     # acceptable per design v3 §4.4; refreshed on next full recompute).
#     for hmsre_col in ("market_state", "trend_strength"):
#         if hmsre_col in old_feat_window.columns:
#             new_row[hmsre_col] = float(old_feat_window[hmsre_col].iloc[-1])
#         else:
#             new_row[hmsre_col] = 0.0
#
# ─────────────────────────────────────────────────────────────────────
# Edit 6: Caller updates
# ─────────────────────────────────────────────────────────────────────
#
# In offline_trainer.py around line 430 (fe = FeatureEngineerOptimized()):
#
# REPLACE:
#     fe          = FeatureEngineerOptimized()
#     features_df = fe.generate_features(df.copy(), batch_processing=False)
#
# WITH:
#     fe          = FeatureEngineerOptimized()
#     fe._symbol_hint       = symbol          # or whatever symbol var is in scope
#     fe._primary_tf_hint   = "60"
#     fe._data_version_hint = data_version    # or "v2" hardcoded if no var
#     features_df = fe.generate_features(df.copy(), batch_processing=False)
#
# Similar updates needed in any other caller that constructs a
# FeatureEngineerOptimized and runs generate_features. Live factory paths
# (alpha_factory.py, nobitex_trader.py) should also set these hints.
# When the hint is None (default), HMSRE columns become 0.0.
#
# ─────────────────────────────────────────────────────────────────────
# Verification after applying these edits
# ─────────────────────────────────────────────────────────────────────
#
# Run:
#   python -m pytest src/features/hmsre/tests/ -v
#   (all 80 tests should still pass)
#
# Then a smoke test with a real CSV:
#   python -c "
#   import pandas as pd
#   from src.features.features_engineering import FeatureEngineerOptimized
#   df = pd.read_csv('data/raw/v2/ohlcv_btcusdt_60.csv').head(2000)
#   fe = FeatureEngineerOptimized()
#   fe._symbol_hint = 'BTCUSDT'
#   feat = fe.generate_features(df)
#   print('Columns include market_state:', 'market_state' in feat.columns)
#   print('Columns include trend_strength:', 'trend_strength' in feat.columns)
#   print('market_state dtype:', feat['market_state'].dtype)
#   print('Non-zero fraction:', (feat['market_state'] != 0.0).sum() / len(feat))
#   "
#
# ─────────────────────────────────────────────────────────────────────
# END Day 4 patch description
# ─────────────────────────────────────────────────────────────────────
