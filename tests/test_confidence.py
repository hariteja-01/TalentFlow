"""Tests for confidence scoring."""

from src.models.canonical import CanonicalProfile, Location, Provenance, Skill
from src.pipeline.stages.confidence import score_confidence


def _make_profile(**kwargs) -> CanonicalProfile:
    defaults = {
        "candidate_id": "test123",
        "full_name": "Jane Doe",
        "emails": ["jane@example.com"],
        "phones": ["+14155552671"],
        "location": Location(city="SF", region="CA", country="US"),
        "headline": "Engineer",
        "years_experience": 5.0,
        "skills": [Skill(name="Python", confidence=0.0, sources=["a.json"])],
        "experience": [],
        "education": [],
        "provenance": [
            Provenance(field="full_name", source="api.json", method="parsed"),
            Provenance(field="emails", source="api.json", method="parsed"),
            Provenance(field="phones", source="api.json", method="parsed"),
            Provenance(field="location", source="api.json", method="parsed"),
            Provenance(field="headline", source="api.json", method="parsed"),
            Provenance(field="years_experience", source="api.json", method="parsed"),
            Provenance(field="skills", source="api.json", method="parsed"),
        ],
        "overall_confidence": 0.0,
    }
    defaults.update(kwargs)
    return CanonicalProfile(**defaults)


class TestConfidenceScoring:
    """Tests for per-field and overall confidence computation."""

    def test_overall_confidence_positive(self):
        """A populated profile should have positive confidence."""
        profile = _make_profile()
        scored = score_confidence(profile)
        assert scored.overall_confidence > 0.0

    def test_overall_confidence_bounded(self):
        """Confidence should never exceed 1.0."""
        profile = _make_profile()
        scored = score_confidence(profile)
        assert scored.overall_confidence <= 1.0

    def test_empty_profile_low_confidence(self):
        """A profile with mostly empty fields should have low confidence."""
        profile = _make_profile(
            full_name="",
            emails=[],
            phones=[],
            location=None,
            headline=None,
            years_experience=None,
            skills=[],
            provenance=[],
        )
        scored = score_confidence(profile)
        assert scored.overall_confidence < 0.1

    def test_skill_confidence_increases_with_sources(self):
        """Skills seen in more sources should have higher confidence."""
        profile = _make_profile(
            skills=[
                Skill(name="Python", confidence=0.0, sources=["a.json", "b.csv", "c.txt"]),
                Skill(name="Docker", confidence=0.0, sources=["a.json"]),
            ],
        )
        scored = score_confidence(profile)
        python_conf = next(s for s in scored.skills if s.name == "Python").confidence
        docker_conf = next(s for s in scored.skills if s.name == "Docker").confidence
        assert python_conf > docker_conf

    def test_multi_source_agreement_bonus(self):
        """Fields confirmed by multiple sources should get higher confidence."""
        profile = _make_profile(
            provenance=[
                Provenance(field="full_name", source="a.json", method="parsed"),
                Provenance(field="full_name", source="b.csv", method="parsed"),
                Provenance(field="emails", source="a.json", method="parsed"),
            ],
        )
        scored = score_confidence(profile)
        # With agreement bonus, confidence should be healthy
        assert scored.overall_confidence > 0.0

    def test_deterministic(self):
        """Same input should always produce same confidence."""
        profile = _make_profile()
        scored1 = score_confidence(profile)
        scored2 = score_confidence(profile)
        assert scored1.overall_confidence == scored2.overall_confidence
