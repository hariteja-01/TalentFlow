"""End-to-end pipeline tests — runs the full pipeline on sample data."""

import json
from pathlib import Path

import pytest

from src.pipeline.orchestrator import load_config, run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INPUTS = PROJECT_ROOT / "sample_inputs"
CONFIGS = PROJECT_ROOT / "configs"


class TestDefaultPipeline:
    """E2E tests with default (full canonical) output."""

    def test_full_pipeline_produces_profiles(self):
        """Pipeline should produce at least one profile from sample inputs."""
        result = run_pipeline([SAMPLE_INPUTS])
        assert len(result.profiles) > 0

    def test_jane_doe_merged(self):
        """Jane Doe appears in all 3 sources — should merge into one profile."""
        result = run_pipeline([SAMPLE_INPUTS])
        # Find Jane's profile by email
        jane_profiles = [
            p for p in result.profiles
            if "jane.doe@email.com" in p.emails
        ]
        assert len(jane_profiles) == 1, "Jane should be merged into exactly one profile"

    def test_jane_has_provenance(self):
        """Jane's profile should have provenance from multiple sources."""
        result = run_pipeline([SAMPLE_INPUTS])
        jane = next(p for p in result.profiles if "jane.doe@email.com" in p.emails)
        assert len(jane.provenance) > 0
        sources = {prov.source for prov in jane.provenance}
        # Should have provenance from at least 2 different source files
        assert len(sources) >= 2

    def test_phones_normalized_e164(self):
        """All phone numbers should be in E.164 format."""
        result = run_pipeline([SAMPLE_INPUTS])
        for profile in result.profiles:
            for phone in profile.phones:
                assert phone.startswith("+"), f"Phone '{phone}' not in E.164"

    def test_skills_canonicalized(self):
        """Skills should use canonical names, not raw aliases."""
        result = run_pipeline([SAMPLE_INPUTS])
        jane = next(p for p in result.profiles if "jane.doe@email.com" in p.emails)
        skill_names = [s.name for s in jane.skills]
        # "ML" from CSV should become "Machine Learning"
        assert "Machine Learning" in skill_names
        # "TF" should become "TensorFlow"
        assert "TensorFlow" in skill_names

    def test_output_is_valid_json(self):
        """Pipeline output should serialize to valid JSON."""
        result = run_pipeline([SAMPLE_INPUTS])
        output_str = result.to_json()
        parsed = json.loads(output_str)
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    def test_overall_confidence_present(self):
        """Every profile should have an overall_confidence score."""
        result = run_pipeline([SAMPLE_INPUTS])
        for profile in result.profiles:
            assert 0.0 <= profile.overall_confidence <= 1.0

    def test_deterministic_output(self):
        """Same inputs should always produce the same output."""
        result1 = run_pipeline([SAMPLE_INPUTS])
        result2 = run_pipeline([SAMPLE_INPUTS])
        assert result1.to_json() == result2.to_json()


class TestCustomConfigPipeline:
    """E2E tests with custom output configuration."""

    def test_custom_config_runs(self):
        """Pipeline should work with the example custom config."""
        config = load_config(CONFIGS / "custom_config.json")
        assert config is not None
        result = run_pipeline([SAMPLE_INPUTS], config)
        assert result.projected is not None
        assert len(result.projected) > 0

    def test_custom_config_field_selection(self):
        """Custom config should only include requested fields."""
        config = load_config(CONFIGS / "custom_config.json")
        result = run_pipeline([SAMPLE_INPUTS], config)
        for proj in result.projected:
            # Should have "full_name" (from config)
            assert "full_name" in proj
            # Should NOT have "candidate_id" (not in config)
            assert "candidate_id" not in proj

    def test_custom_config_renames(self):
        """Custom config should remap 'emails[0]' to 'primary_email'."""
        config = load_config(CONFIGS / "custom_config.json")
        result = run_pipeline([SAMPLE_INPUTS], config)
        for proj in result.projected:
            if proj.get("primary_email") is not None:
                assert "@" in proj["primary_email"]

    def test_custom_config_includes_confidence(self):
        """Custom config has include_confidence=true."""
        config = load_config(CONFIGS / "custom_config.json")
        result = run_pipeline([SAMPLE_INPUTS], config)
        for proj in result.projected:
            assert "overall_confidence" in proj
