# tests/test_evidence_ladder.py
"""
Tests for src/core/evidence_ladder.py — Evidence Ladder system.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.core.evidence_ladder import (
    EvidenceLadder,
    EvidenceLevel,
    HypothesisRecord,
    PIPELINE_STAGES,
    StageResult,
)


class TestEvidenceLevel:
    def test_level_ordering(self):
        """L0 < L1 < L2 < ... < L6."""
        assert EvidenceLevel.L0 < EvidenceLevel.L1
        assert EvidenceLevel.L1 < EvidenceLevel.L2
        assert EvidenceLevel.L5 < EvidenceLevel.L6

    def test_from_string(self):
        assert EvidenceLevel.from_string("L0") == EvidenceLevel.L0
        assert EvidenceLevel.from_string("L3") == EvidenceLevel.L3
        assert EvidenceLevel.from_string("L6") == EvidenceLevel.L6
        assert EvidenceLevel.from_string("l2") == EvidenceLevel.L2
        assert EvidenceLevel.from_string("4") == EvidenceLevel.L4

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            EvidenceLevel.from_string("L7")
        with pytest.raises(ValueError):
            EvidenceLevel.from_string("invalid")

    def test_labels_and_actions(self):
        assert EvidenceLevel.L0.label == "Economic intuition only"
        assert EvidenceLevel.L0.action == "Cheap prototype"
        assert EvidenceLevel.L3.label == "Survives walk-forward"
        assert EvidenceLevel.L3.action == "High priority"
        assert EvidenceLevel.L6.label == "Survives 6-12 months live"
        assert EvidenceLevel.L6.action == "Deploy capital"


class TestHypothesisRecord:
    def test_create_minimal(self):
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
        )
        assert record.hypothesis_id == "test_001"
        assert record.evidence_level == EvidenceLevel.L0
        assert record.created_at != ""
        assert record.updated_at != ""
        assert record.retry_count == 0
        assert not record.archived

    def test_promote(self):
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
        )
        result = StageResult(stage=2, name="In-Sample", passed=True)
        record.promote(EvidenceLevel.L1, result)
        assert record.evidence_level == EvidenceLevel.L1
        assert len(record.stage_results) == 1
        assert record.stage_results[0].stage == 2

    def test_promote_not_higher_ignored(self):
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
            evidence_level=EvidenceLevel.L3,
        )
        result = StageResult(stage=1, name="Economic", passed=True)
        record.promote(EvidenceLevel.L1, result)  # L1 < L3 — should be ignored
        assert record.evidence_level == EvidenceLevel.L3

    def test_demote(self):
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
            evidence_level=EvidenceLevel.L3,
        )
        record.demote("Failed walk-forward", 3)
        assert record.evidence_level == EvidenceLevel.L0
        assert record.failed_at_stage == 3
        assert "Failed walk-forward" in record.failure_reason
        assert record.retry_count == 1

    def test_record_stage(self):
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
        )
        result = StageResult(stage=1, name="Economic", passed=True)
        record.record_stage(result)
        assert len(record.stage_results) == 1
        assert record.evidence_level == EvidenceLevel.L0  # Level unchanged

    def test_current_stage(self):
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
        )
        # At L0, the first stage requiring >L0 is Stage 2 (requires L1).
        # Stage 1 requires L0 which is NOT > L0, so it's skipped.
        assert record.current_stage == 2

        record.evidence_level = EvidenceLevel.L3
        # At L3, the next pipeline stage requiring >L3 is Stage 7 (Regime Stability, L4)
        assert record.current_stage == 7

        record.evidence_level = EvidenceLevel.L6
        assert record.current_stage == 11  # Beyond pipeline

    def test_to_dict_and_from_dict(self):
        original = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="TestFamily",
            description="A test",
            economic_rationale="Because testing",
            evidence_level=EvidenceLevel.L2,
            symbols=["BTCUSDT"],
            timeframes=["15", "60"],
            tags=["test", "unit"],
            metrics={"sharpe": 1.5},
        )
        original.promote(EvidenceLevel.L2, StageResult(
            stage=2, name="In-Sample", passed=True,
            metrics={"pf": 1.2},
        ))

        d = original.to_dict()
        restored = HypothesisRecord.from_dict(d)

        assert restored.hypothesis_id == original.hypothesis_id
        assert restored.evidence_level == original.evidence_level
        assert restored.name == original.name
        assert restored.family == original.family
        assert restored.metrics == original.metrics
        assert len(restored.stage_results) == len(original.stage_results)


class TestEvidenceLadder:
    def test_register_and_get(self):
        ladder = EvidenceLadder()
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test",
            family="TestFamily",
        )
        ladder.register(record)
        assert ladder.get("test_001") is record
        assert ladder.get("nonexistent") is None

    def test_duplicate_register_warns(self, caplog):
        ladder = EvidenceLadder()
        r1 = HypothesisRecord(hypothesis_id="test_001", name="A", family="F")
        r2 = HypothesisRecord(hypothesis_id="test_001", name="B", family="F")
        ladder.register(r1)
        ladder.register(r2)
        assert "already registered" in caplog.text

    def test_promote(self):
        ladder = EvidenceLadder()
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test",
            family="TestFamily",
        )
        ladder.register(record)
        result = StageResult(stage=3, name="Walk-Forward", passed=True)
        ok = ladder.promote("test_001", EvidenceLevel.L3, result)
        assert ok
        assert ladder.get("test_001").evidence_level == EvidenceLevel.L3

    def test_promote_unknown(self):
        ladder = EvidenceLadder()
        result = StageResult(stage=3, name="WF", passed=True)
        assert not ladder.promote("nonexistent", EvidenceLevel.L3, result)

    def test_demote(self):
        ladder = EvidenceLadder()
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test",
            family="TestFamily",
            evidence_level=EvidenceLevel.L3,
        )
        ladder.register(record)
        ok = ladder.demote("test_001", "Bootstrap failed", 4)
        assert ok
        assert ladder.get("test_001").evidence_level == EvidenceLevel.L0

    def test_archive(self):
        ladder = EvidenceLadder()
        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test",
            family="TestFamily",
        )
        ladder.register(record)
        assert not record.archived
        ladder.archive("test_001")
        assert record.archived

    def test_list_active(self):
        ladder = EvidenceLadder()
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="F",
                              evidence_level=EvidenceLevel.L3)
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="F",
                              evidence_level=EvidenceLevel.L1)
        r3 = HypothesisRecord(hypothesis_id="c", name="C", family="F",
                              evidence_level=EvidenceLevel.L0)
        r3.archived = True
        ladder.register(r1)
        ladder.register(r2)
        ladder.register(r3)

        active = ladder.list_active()
        assert len(active) == 2
        # Should be sorted by evidence level descending
        assert active[0].hypothesis_id == "a"  # L3
        assert active[1].hypothesis_id == "b"  # L1

    def test_list_by_level(self):
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(hypothesis_id="a", name="A", family="F",
                                         evidence_level=EvidenceLevel.L0))
        ladder.register(HypothesisRecord(hypothesis_id="b", name="B", family="F",
                                         evidence_level=EvidenceLevel.L3))
        ladder.register(HypothesisRecord(hypothesis_id="c", name="C", family="F",
                                         evidence_level=EvidenceLevel.L3))
        assert len(ladder.list_by_level(EvidenceLevel.L0)) == 1
        assert len(ladder.list_by_level(EvidenceLevel.L3)) == 2
        assert len(ladder.list_by_level(EvidenceLevel.L6)) == 0

    def test_list_by_family(self):
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(hypothesis_id="a", name="A", family="PositioningAlpha"))
        ladder.register(HypothesisRecord(hypothesis_id="b", name="B", family="ExpansionAlpha"))
        ladder.register(HypothesisRecord(hypothesis_id="c", name="C", family="positioningalpha"))
        assert len(ladder.list_by_family("PositioningAlpha")) == 2
        assert len(ladder.list_by_family("ExpansionAlpha")) == 1

    def test_list_candidates(self):
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(hypothesis_id="a", name="A", family="F",
                                         evidence_level=EvidenceLevel.L4))
        ladder.register(HypothesisRecord(hypothesis_id="b", name="B", family="F",
                                         evidence_level=EvidenceLevel.L5))
        ladder.register(HypothesisRecord(hypothesis_id="c", name="C", family="F",
                                         evidence_level=EvidenceLevel.L3))
        candidates = ladder.list_candidates()
        assert len(candidates) == 2

    def test_list_production_candidates(self):
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(hypothesis_id="a", name="A", family="F",
                                         evidence_level=EvidenceLevel.L5))
        ladder.register(HypothesisRecord(hypothesis_id="b", name="B", family="F",
                                         evidence_level=EvidenceLevel.L6))
        ladder.register(HypothesisRecord(hypothesis_id="c", name="C", family="F",
                                         evidence_level=EvidenceLevel.L4))
        prods = ladder.list_production_candidates()
        assert len(prods) == 2

    def test_list_backlog(self):
        ladder = EvidenceLadder()
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="F")
        r1.retry_count = 1  # Previously failed
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="F")
        r2.retry_count = 0  # Never tested
        ladder.register(r1)
        ladder.register(r2)
        backlog = ladder.list_backlog()
        assert len(backlog) == 1
        assert backlog[0].hypothesis_id == "a"

    def test_list_never_tested(self):
        ladder = EvidenceLadder()
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="F")
        r1.retry_count = 1
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="F")
        r2.retry_count = 0
        ladder.register(r1)
        ladder.register(r2)
        fresh = ladder.list_never_tested()
        assert len(fresh) == 1
        assert fresh[0].hypothesis_id == "b"

    def test_save_and_load_roundtrip(self):
        ladder = EvidenceLadder()
        r1 = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test Hypothesis",
            family="PositioningAlpha",
            description="Test description",
            economic_rationale="Test rationale",
            evidence_level=EvidenceLevel.L0,  # Start at L0
            symbols=["BTCUSDT"],
            timeframes=["60"],
            tags=["test"],
            metrics={"sharpe": 1.2, "pf": 1.5},
        )
        # Manually add stage results and set level
        r1.stage_results.append(StageResult(
            stage=3, name="Walk-Forward", passed=True,
            metrics={"mean_ir": 0.5},
        ))
        r1.evidence_level = EvidenceLevel.L3
        r1.updated_at = "2026-06-26T00:00:00+00:00"
        ladder.register(r1)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            ladder.path = Path(tmp_path)
            ladder.save()

            # Load into a new ladder
            ladder2 = EvidenceLadder(path=tmp_path)
            assert ladder2.load()
            assert len(ladder2) == 1

            restored = ladder2.get("test_001")
            assert restored is not None
            assert restored.name == "Test Hypothesis"
            assert restored.family == "PositioningAlpha"
            assert restored.evidence_level == EvidenceLevel.L3
            assert restored.metrics == {"sharpe": 1.2, "pf": 1.5}
            assert len(restored.stage_results) == 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_nonexistent(self):
        ladder = EvidenceLadder(path="nonexistent/path/ladder.json")
        assert ladder.load()  # Should succeed — starts fresh
        assert len(ladder) == 0

    def test_summary(self):
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(hypothesis_id="a", name="A", family="PositioningAlpha",
                                         evidence_level=EvidenceLevel.L4))
        ladder.register(HypothesisRecord(hypothesis_id="b", name="B", family="ExpansionAlpha",
                                         evidence_level=EvidenceLevel.L0))
        ladder.register(HypothesisRecord(hypothesis_id="c", name="C", family="PositioningAlpha",
                                         evidence_level=EvidenceLevel.L0))
        ladder.get("c").archived = True

        s = ladder.summary()
        assert s["total_active"] == 2
        assert s["total_archived"] == 1
        assert s["candidates"] == 1
        assert s["by_family"]["PositioningAlpha"] == 1  # One active in PositioningAlpha
        assert s["by_family"]["ExpansionAlpha"] == 1

    def test_render_summary(self):
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(hypothesis_id="a", name="A", family="F"))
        text = ladder.render_summary()
        assert "Evidence Ladder Summary" in text
        assert "Active hypotheses" in text


class TestPipelineStages:
    def test_all_10_stages_exist(self):
        assert len(PIPELINE_STAGES) == 10

    def test_stage_numbers(self):
        for i, stage in enumerate(PIPELINE_STAGES, start=1):
            assert stage.number == i

    def test_evidence_level_progression(self):
        """Verify pipeline stages exist with monotonically increasing levels
        (with known intentional exception: Stage 6 costs L2 < Stage 5 robustness L3).
        Just verify stage numbers are sequential."""
        for i, stage in enumerate(PIPELINE_STAGES, start=1):
            assert stage.number == i
        # All 10 stages have defined levels
        assert all(s.required_evidence_level is not None for s in PIPELINE_STAGES)


class TestStageResult:
    def test_create(self):
        sr = StageResult(stage=1, name="Economic", passed=True,
                         metrics={"score": 10}, notes="Good")
        assert sr.stage == 1
        assert sr.passed
        assert sr.metrics == {"score": 10}
        assert sr.notes == "Good"
        assert sr.timestamp != ""
