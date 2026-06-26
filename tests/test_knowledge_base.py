# tests/test_knowledge_base.py
"""Tests for Research Knowledge Base."""

import tempfile

import pytest

from src.core.knowledge_base import (
    ResearchKnowledgeBase,
    Observation,
    KnowledgeBaseSummary,
    create_seeded_knowledge_base,
)


class TestObservation:
    def test_create(self):
        obs = Observation(
            observation_id="obs_001",
            statement="BTC behaves differently from ETH.",
            domain="cross_asset",
            confidence=4,
        )
        assert obs.observation_id == "obs_001"
        assert obs.confidence_label == "Strong"
        assert "obs_001" in obs.citation()

    def test_confidence_labels(self):
        labels = {1: "Weak", 2: "Suggestive", 3: "Moderate", 4: "Strong", 5: "Confirmed"}
        for level, label in labels.items():
            obs = Observation(
                observation_id=f"obs_{level}",
                statement=f"Test {level}",
                domain="test",
                confidence=level,
            )
            assert obs.confidence_label == label

    def test_to_dict(self):
        obs = Observation(
            observation_id="obs_001",
            statement="Test",
            domain="test",
            confidence=3,
            supporting_experiments=["exp1"],
        )
        d = obs.to_dict()
        assert d["observation_id"] == "obs_001"
        assert d["confidence"] == 3
        assert "exp1" in d["supporting_experiments"]

    def test_citation(self):
        obs = Observation(
            observation_id="obs_007",
            statement="Multi-timeframe context matters.",
            domain="multi_timeframe",
            confidence=4,
            supporting_experiments=["exp1", "exp2"],
        )
        cite = obs.citation()
        assert "obs_007" in cite
        assert "Multi-timeframe" in cite
        assert "Strong" in cite


class TestResearchKnowledgeBase:
    @pytest.fixture
    def kb(self, tmp_path):
        kb = ResearchKnowledgeBase(path=str(tmp_path / "test_kb.json"))
        return kb

    def test_add_and_get(self, kb):
        obs = Observation(
            observation_id="obs_001",
            statement="Test finding",
            domain="test",
            confidence=3,
        )
        kb.add(obs)
        retrieved = kb.get("obs_001")
        assert retrieved is not None
        assert retrieved.statement == "Test finding"

    def test_duplicate_add(self, kb):
        obs1 = Observation("obs_001", "First", "test", 1)
        obs2 = Observation("obs_001", "Second", "test", 1)
        kb.add(obs1)
        kb.add(obs2)  # Should warn but not overwrite
        assert kb.get("obs_001").statement == "First"

    def test_update(self, kb):
        obs = Observation("obs_001", "Original", "test", 1)
        kb.add(obs)
        kb.update("obs_001", confidence=5, notes="Updated")
        updated = kb.get("obs_001")
        assert updated.confidence == 5
        assert updated.notes == "Updated"

    def test_cite(self, kb):
        obs = Observation("obs_001", "Important finding", "test", 4)
        kb.add(obs)
        cite = kb.cite("obs_001")
        assert "obs_001" in cite
        assert "Important" in cite

    def test_cite_missing(self, kb):
        assert kb.cite("nonexistent") == ""

    def test_get_by_domain(self, kb):
        kb.add(Observation("obs_001", "A", "microstructure", 4))
        kb.add(Observation("obs_002", "B", "momentum", 3))
        kb.add(Observation("obs_003", "C", "microstructure", 2))

        ms = kb.get_by_domain("microstructure")
        assert len(ms) == 2
        assert all(o.domain == "microstructure" for o in ms)

    def test_get_by_confidence(self, kb):
        kb.add(Observation("obs_001", "A", "test", 5))
        kb.add(Observation("obs_002", "B", "test", 3))
        kb.add(Observation("obs_003", "C", "test", 1))

        high = kb.get_by_confidence(4)
        assert len(high) == 1
        assert high[0].confidence == 5

    def test_get_by_hypothesis(self, kb):
        obs = Observation(
            observation_id="obs_001",
            statement="Test",
            domain="test",
            confidence=3,
            related_hypotheses=["pos_001", "pos_002"],
        )
        kb.add(obs)
        related = kb.get_by_hypothesis("pos_001")
        assert len(related) == 1

    def test_get_high_confidence(self, kb):
        kb.add(Observation("obs_001", "A", "test", 5))
        kb.add(Observation("obs_002", "B", "test", 4))
        kb.add(Observation("obs_003", "C", "test", 3))
        high = kb.get_high_confidence()
        assert len(high) == 2

    def test_list_domains(self, kb):
        kb.add(Observation("obs_001", "A", "microstructure", 1))
        kb.add(Observation("obs_002", "B", "momentum", 1))
        domains = kb.list_domains()
        assert "microstructure" in domains
        assert "momentum" in domains

    def test_summary(self, kb):
        kb.add(Observation("obs_001", "A", "microstructure", 5))
        kb.add(Observation("obs_002", "B", "momentum", 2))
        s = kb.summary()
        assert s.total_observations == 2
        assert s.high_confidence == 1
        assert "microstructure" in s.by_domain
        assert "momentum" in s.by_domain

    def test_render_summary(self, kb):
        kb.add(Observation("obs_001", "A", "test", 3))
        text = kb.render_summary()
        assert "Knowledge Base" in text
        assert "1" in text

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "kb.json")
        kb1 = ResearchKnowledgeBase(path=path)
        kb1.add(Observation("obs_001", "Persist test", "test", 5))
        kb1.save()

        kb2 = ResearchKnowledgeBase(path=path)
        kb2.load()
        assert len(kb2) == 1
        assert kb2.get("obs_001").statement == "Persist test"

    def test_len(self, kb):
        assert len(kb) == 0
        kb.add(Observation("obs_001", "A", "test", 1))
        assert len(kb) == 1
        kb.add(Observation("obs_002", "B", "test", 1))
        assert len(kb) == 2


class TestSeededKnowledgeBase:
    def test_create_seeded(self):
        kb = create_seeded_knowledge_base()
        assert len(kb) == 8
        # Should have known discoveries
        domains = kb.list_domains()
        assert "cross_asset" in domains
        assert "funding" in domains
        assert "validation" in domains

        # Should have high-confidence observations
        high = kb.get_high_confidence()
        assert len(high) >= 3  # At least obs_001, obs_004, obs_005, obs_006

        # All IDs should be present
        for oid in [f"obs_{i:03d}" for i in range(1, 9)]:
            assert kb.get(oid) is not None, f"Missing {oid}"
