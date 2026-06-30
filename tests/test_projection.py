"""Tests for the projection stage — runtime config-driven output shaping."""

import pytest

from src.models.canonical import CanonicalProfile, Links, Location, Skill
from src.models.config import FieldConfig, OutputConfig
from src.pipeline.stages.projection import ProjectionError, project_profile


def _make_profile(**kwargs) -> CanonicalProfile:
    """Helper to create a CanonicalProfile with defaults."""
    defaults = {
        "candidate_id": "test123",
        "full_name": "Jane Doe",
        "emails": ["jane@example.com", "jane2@example.com"],
        "phones": ["+14155552671"],
        "location": Location(city="San Francisco", region="California", country="US"),
        "links": Links(linkedin="https://linkedin.com/in/janedoe", github="https://github.com/janedoe"),
        "headline": "ML Engineer",
        "years_experience": 7.0,
        "skills": [
            Skill(name="Python", confidence=0.9, sources=["a.json"]),
            Skill(name="Docker", confidence=0.8, sources=["b.csv"]),
        ],
        "overall_confidence": 0.85,
    }
    defaults.update(kwargs)
    return CanonicalProfile(**defaults)


class TestFieldSelection:
    """Tests for selecting a subset of fields."""

    def test_select_only_name(self):
        config = OutputConfig(
            fields=[FieldConfig(path="full_name", type="string")],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert "full_name" in result
        assert "emails" not in result

    def test_select_multiple_fields(self):
        config = OutputConfig(
            fields=[
                FieldConfig(path="full_name", type="string"),
                FieldConfig(path="headline", type="string"),
            ],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert set(result.keys()) == {"full_name", "headline"}


class TestPathRemapping:
    """Tests for the 'from' path remapping feature."""

    def test_remap_first_email(self):
        config = OutputConfig(
            fields=[FieldConfig(path="primary_email", from_path="emails[0]", type="string")],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert result["primary_email"] == "jane@example.com"

    def test_remap_nested_field(self):
        config = OutputConfig(
            fields=[FieldConfig(path="city", from_path="location.city", type="string")],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert result["city"] == "San Francisco"

    def test_remap_array_spread(self):
        config = OutputConfig(
            fields=[FieldConfig(path="skill_names", from_path="skills[].name", type="string[]")],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert result["skill_names"] == ["Python", "Docker"]

    def test_remap_linkedin(self):
        config = OutputConfig(
            fields=[FieldConfig(path="linkedin", from_path="links.linkedin", type="string")],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert "linkedin.com" in result["linkedin"]


class TestMissingValuePolicies:
    """Tests for on_missing behavior."""

    def test_on_missing_null(self):
        profile = _make_profile(headline=None)
        config = OutputConfig(
            fields=[FieldConfig(path="headline", type="string", required=True)],
            on_missing="null",
            include_confidence=False,
        )
        result = project_profile(profile, config)
        assert result["headline"] is None

    def test_on_missing_omit(self):
        profile = _make_profile(headline=None)
        config = OutputConfig(
            fields=[FieldConfig(path="headline", type="string", required=True)],
            on_missing="omit",
            include_confidence=False,
        )
        result = project_profile(profile, config)
        assert "headline" not in result

    def test_on_missing_error(self):
        profile = _make_profile(headline=None)
        config = OutputConfig(
            fields=[FieldConfig(path="headline", type="string", required=True)],
            on_missing="error",
            include_confidence=False,
        )
        with pytest.raises(ProjectionError):
            project_profile(profile, config)


class TestConfidenceToggle:
    """Tests for include_confidence toggle."""

    def test_confidence_included(self):
        config = OutputConfig(
            fields=[FieldConfig(path="full_name", type="string")],
            include_confidence=True,
        )
        result = project_profile(_make_profile(), config)
        assert "overall_confidence" in result

    def test_confidence_excluded(self):
        config = OutputConfig(
            fields=[FieldConfig(path="full_name", type="string")],
            include_confidence=False,
        )
        result = project_profile(_make_profile(), config)
        assert "overall_confidence" not in result
