"""Tests for source parsers."""

from pathlib import Path

import pytest

from src.parsers.json_parser import JsonParser
from src.parsers.csv_parser import CsvParser
from src.parsers.resume_parser import ResumeParser


class TestJsonParser:
    """Tests for the JSON source parser."""

    def test_parse_sample_file(self, sample_json_path):
        parser = JsonParser()
        records = parser.parse(sample_json_path)
        assert len(records) == 2
        # First candidate
        assert records[0].full_name == "Jane M. Doe"
        assert "jane.doe@email.com" in records[0].emails
        assert records[0].source_type == "json"

    def test_parse_single_candidate(self, valid_json_single):
        parser = JsonParser()
        records = parser.parse(valid_json_single)
        assert len(records) == 1
        assert records[0].full_name == "Test User"
        assert records[0].emails == ["test@example.com"]

    def test_parse_empty_file(self, empty_file):
        parser = JsonParser()
        records = parser.parse(empty_file)
        assert records == []

    def test_parse_malformed_json(self, malformed_json):
        parser = JsonParser()
        records = parser.parse(malformed_json)
        assert records == []

    def test_parse_nonexistent_file(self):
        parser = JsonParser()
        records = parser.parse(Path("/does/not/exist.json"))
        assert records == []

    def test_source_type(self):
        assert JsonParser().source_type == "json"

    def test_source_weight(self, valid_json_single):
        parser = JsonParser()
        records = parser.parse(valid_json_single)
        assert records[0].source_weight == 0.9  # JSON is highest weight


class TestCsvParser:
    """Tests for the CSV source parser."""

    def test_parse_sample_file(self, sample_csv_path):
        parser = CsvParser()
        records = parser.parse(sample_csv_path)
        assert len(records) == 3
        assert records[0].full_name == "Jane Doe"
        assert "jane.doe@email.com" in records[0].emails

    def test_parse_empty_file(self, empty_file):
        parser = CsvParser()
        # Rename to .csv for detection
        csv_empty = empty_file.parent / "empty.csv"
        csv_empty.write_text("")
        records = parser.parse(csv_empty)
        assert records == []

    def test_parse_garbage_csv(self, garbage_csv):
        parser = CsvParser()
        records = parser.parse(garbage_csv)
        # Should not crash, may return empty records
        assert isinstance(records, list)

    def test_source_type(self):
        assert CsvParser().source_type == "csv"

    def test_skills_comma_separated(self, sample_csv_path):
        parser = CsvParser()
        records = parser.parse(sample_csv_path)
        # Jane's CSV row has "Python, ML, TF, Docker, Kubernetes, AWS"
        assert "Python" in records[0].skills
        assert "ML" in records[0].skills


class TestResumeParser:
    """Tests for the plain-text resume parser."""

    def test_parse_sample_resume(self, sample_resume_path):
        parser = ResumeParser()
        records = parser.parse(sample_resume_path)
        assert len(records) == 1

        record = records[0]
        assert record.full_name == "Jane Doe"
        assert "jane.doe@email.com" in record.emails
        assert "janedoe@personal.com" in record.emails
        assert record.source_type == "resume"

    def test_parse_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        parser = ResumeParser()
        records = parser.parse(f)
        assert records == []

    def test_extract_links(self, sample_resume_path):
        parser = ResumeParser()
        records = parser.parse(sample_resume_path)
        assert records[0].links is not None
        assert "linkedin" in records[0].links.linkedin.lower()
        assert "github" in records[0].links.github.lower()

    def test_extract_skills(self, sample_resume_path):
        parser = ResumeParser()
        records = parser.parse(sample_resume_path)
        # Should find skills from the SKILLS section
        assert len(records[0].skills) > 0
        # At least Python should be found
        skill_names_lower = [s.lower() for s in records[0].skills]
        assert "python" in skill_names_lower

    def test_source_type(self):
        assert ResumeParser().source_type == "resume"
