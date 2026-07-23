# Scientific Evaluation Report: M003
**Date:** 2026-07-21

## Mechanism
- **ID:** M003
- **Description:** Position Unwind (Open Interest vs Price divergence) on high-quality regimes.

## Experimental Results
- **Pipeline Stages Run:** 3
- **Stages Passed:** 2
- **Final Level:** Economic intuition only

## Boundary Models & Falsification
- **Boundary Models:** ['M003_BTC_4h_Lookback5_B01', 'M003_BTC_4h_Lookback10_B02']
- **Falsification Criteria:** ['OI increases with price during reversal']

## Evidence Gap
- **Next High Info Gain Experiment:** {}

---
## Detailed Results
```json
{
  "hypothesis_id": "M003_BTCUSDT_4h",
  "started_at_level": "L3",
  "final_level": "L0",
  "stages_run": 3,
  "stages_passed": 2,
  "stages_failed": 1,
  "final_level_label": "Economic intuition only",
  "results": [
    {
      "stage": 1,
      "name": "Economic Explanation",
      "passed": true,
      "timestamp": "2026-07-23T12:29:06.430172+00:00",
      "metrics": {
        "checks_passed": 6,
        "checks_total": 6,
        "check_has_rationale": true,
        "check_has_description": true,
        "check_has_symbols": true,
        "check_has_timeframes": true,
        "check_no_placeholders": true,
        "check_thesis_document_ok": true
      },
      "notes": "Economic explanation validated (6/6 checks passed).; Thesis document path not configured \u2014 skipped."
    },
    {
      "stage": 2,
      "name": "In-Sample Discovery",
      "passed": true,
      "timestamp": "2026-07-23T12:29:06.430172+00:00",
      "metrics": {
        "profit_factor": 1.1525705032328044,
        "sharpe": 0.6551842696502319,
        "win_rate": 0.375
      },
      "notes": "In-sample edge confirmed: PF=1.15, Sharpe=0.66"
    },
    {
      "stage": 3,
      "name": "Walk-Forward Validation",
      "passed": false,
      "timestamp": "2026-07-23T12:29:06.430172+00:00",
      "metrics": {
        "n_windows": 8,
        "mean_ir": -3.6766,
        "ir_positive_prob": 0.25,
        "dsr": -5.3171
      },
      "notes": "Walk-forward: 8/12 windows, mean_IR=-3.677, P(IR>0)=0.250, DSR=-5.317"
    }
  ]
}
```
