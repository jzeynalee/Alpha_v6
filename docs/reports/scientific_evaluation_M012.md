# Scientific Evaluation Report: M012
**Date:** 2026-07-21

## Mechanism
- **ID:** M012
- **Description:** M012 auto-generated.

## Experimental Results
- **Pipeline Stages Run:** 2
- **Stages Passed:** 1
- **Final Level:** Economic intuition only

## Boundary Models & Falsification
- **Boundary Models:** []
- **Falsification Criteria:** ['Performance fails baseline']

## Evidence Gap
- **Next High Info Gain Experiment:** {}

---
## Detailed Results
```json
{
  "hypothesis_id": "M012_BTCUSDT_4h",
  "started_at_level": "L0",
  "final_level": "L0",
  "stages_run": 2,
  "stages_passed": 1,
  "stages_failed": 1,
  "final_level_label": "Economic intuition only",
  "results": [
    {
      "stage": 1,
      "name": "Economic Explanation",
      "passed": true,
      "timestamp": "2026-07-22T18:35:47.723502+00:00",
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
      "passed": false,
      "timestamp": "2026-07-22T18:35:47.723502+00:00",
      "metrics": {},
      "notes": "In-sample edge insufficient: PF=0.00 (need > 1.0). Run signal_factory_simulation.py to populate in-sample metrics."
    }
  ]
}
```
