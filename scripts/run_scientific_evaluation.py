import json
from pathlib import Path
from src.core.evidence_ladder import EvidenceLadder, HypothesisRecord, EvidenceLevel
from src.core.research_pipeline import ResearchPipeline
from src.core.records import get_record

def evaluate_mechanism(mechanism_id: str):
    ladder = EvidenceLadder()
    ladder.load()
    pipeline = ResearchPipeline(ladder=ladder)
    record = get_record(mechanism_id)
    
    if not record:
        print(f"Mechanism {mechanism_id} not found.")
        return

    # 1. Register hypothesis with required fields
    hypo_id = f"{mechanism_id}_BTCUSDT_4h"
    if not ladder.get(hypo_id):
        new_record = HypothesisRecord(
            hypothesis_id=hypo_id,
            name=record.description,
            family="ScientificValidation",
            description=f"Automated evaluation for {mechanism_id}",
            economic_rationale=record.scientific_rationale if hasattr(record, 'scientific_rationale') else "Standard market microstructure rationale.",
            symbols=["BTCUSDT"],
            timeframes=["4h"],
            evidence_level=EvidenceLevel.L0
        )
        ladder.register(new_record)
        ladder.save()

    # 2. Run Pipeline (Stages 1-6)
    print(f"Running pipeline for {hypo_id}...")
    result = pipeline.run_hypothesis(hypo_id, requested_stages=[1, 2, 3, 4, 5, 6])
    
    # 3. Generate Report
    report_content = f"""# Scientific Evaluation Report: {mechanism_id}
**Date:** 2026-07-21

## Mechanism
- **ID:** {mechanism_id}
- **Description:** {record.description}

## Experimental Results
- **Pipeline Stages Run:** {result.get('stages_run')}
- **Stages Passed:** {result.get('stages_passed')}
- **Final Level:** {result.get('final_level_label')}

## Boundary Models & Falsification
- **Boundary Models:** {list(record.boundary_models.keys())}
- **Falsification Criteria:** {record.falsification_criteria}

## Evidence Gap
- **Next High Info Gain Experiment:** {record.next_experiment()}

---
## Detailed Results
```json
{json.dumps(result, indent=2)}
```
"""
    report_path = Path(f"docs/reports/scientific_evaluation_{mechanism_id}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_content)
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        evaluate_mechanism(sys.argv[1])
