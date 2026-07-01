"""Edge case tests — graceful degradation on bad/missing/weird input."""

import json
from pathlib import Path

import pytest

from src.pipeline.orchestrator import run_pipeline, load_config
from src.models.config import OutputConfig, FieldConfig
from src.parsers.json_parser import JsonParser
from src.parsers.csv_parser import CsvParser
from src.parsers.resume_parser import ResumeParser


class TestEmptyInputs:
    """Pipeline should handle empty/missing inputs gracefully."""

    def test_empty_directory(self, tmp_path):
        result = run_pipeline([tmp_path])
        assert len(result.profiles) == 0
        assert len(result.warnings) > 0

    def test_nonexistent_path(self):
        result = run_pipeline([Path("/does/not/exist")])
        assert len(result.profiles) == 0

    def test_empty_json_file(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        result = run_pipeline([f])
        assert len(result.profiles) == 1

    def test_empty_csv_file(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("")
        result = run_pipeline([f])
        assert len(result.profiles) == 1

    def test_empty_resume_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = run_pipeline([f])
        assert len(result.profiles) == 1


class TestMalformedInputs:
    """Pipeline should not crash on garbage data."""

    def test_malformed_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{{not json at all!!!")
        result = run_pipeline([f])
        assert len(result.profiles) == 1  # No crash

    def test_json_with_wrong_structure(self, tmp_path):
        f = tmp_path / "wrong.json"
        f.write_text(json.dumps([1, 2, 3]))  # Array of numbers, not candidates
        result = run_pipeline([f])
        assert isinstance(result.profiles, list)  # No crash

    def test_csv_with_no_known_columns(self, tmp_path):
        f = tmp_path / "unknown.csv"
        f.write_text("x,y,z\n1,2,3\n")
        result = run_pipeline([f])
        assert isinstance(result.profiles, list)

    def test_resume_with_only_gibberish(self, tmp_path):
        f = tmp_path / "gibberish.txt"
        f.write_text("asdfghjkl 12345 !@#$%\n" * 10)
        result = run_pipeline([f])
        # Should produce a record (resume parser always returns 1) but with sparse data
        assert isinstance(result.profiles, list)

    def test_binary_file_ignored(self, tmp_path):
        f = tmp_path / "binary.dat"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        result = run_pipeline([f])
        # .dat extension not supported — should be skipped
        assert len(result.profiles) == 0


class TestMissingFields:
    """Profiles with missing fields should have None, never invented data."""

    def test_candidate_without_phone(self, tmp_path):
        f = tmp_path / "no_phone.json"
        f.write_text(json.dumps({
            "full_name": "No Phone Person",
            "email": "nophone@test.com",
        }))
        result = run_pipeline([f])
        assert len(result.profiles) == 1
        assert result.profiles[0].phones == []

    def test_candidate_without_skills(self, tmp_path):
        f = tmp_path / "no_skills.json"
        f.write_text(json.dumps({
            "full_name": "No Skills Person",
            "email": "noskills@test.com",
        }))
        result = run_pipeline([f])
        assert result.profiles[0].skills == []

    def test_candidate_without_name(self, tmp_path):
        f = tmp_path / "no_name.json"
        f.write_text(json.dumps({
            "email": "noname@test.com",
            "skills": ["Python"],
        }))
        result = run_pipeline([f])
        assert len(result.profiles) == 1
        # Name should be empty, not invented
        assert result.profiles[0].full_name == ""


class TestConfigEdgeCases:
    """Tests for unusual config scenarios."""

    def test_config_requesting_nonexistent_path(self, tmp_path):
        """Config requesting a path that doesn't exist in the profile."""
        f = tmp_path / "test.json"
        f.write_text(json.dumps({"full_name": "Test", "email": "t@t.com"}))

        config = OutputConfig(
            fields=[
                FieldConfig(path="full_name", type="string"),
                FieldConfig(path="foo", from_path="nonexistent.field", type="string"),
            ],
            on_missing="null",
            include_confidence=False,
        )
        result = run_pipeline([f], config)
        assert result.projected is not None
        # The nonexistent field should be null
        assert result.projected[0].get("foo") is None

    def test_load_config_nonexistent_file(self):
        config = load_config(Path("/does/not/exist.json"))
        assert config is None

    def test_on_missing_omit_removes_field(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(json.dumps({"full_name": "Test", "email": "t@t.com"}))

        config = OutputConfig(
            fields=[
                FieldConfig(path="full_name", type="string"),
                FieldConfig(path="headline", type="string"),
            ],
            on_missing="omit",
            include_confidence=False,
        )
        result = run_pipeline([f], config)
        assert result.projected is not None
        # headline is None → should be omitted
        assert "headline" not in result.projected[0]
