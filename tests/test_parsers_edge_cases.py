"""Edge case tests for all parsers."""

import pytest
from pathlib import Path

from src.parsers.resume_parser import ResumeParser, _is_date_range
from src.parsers.csv_parser import CsvParser
from src.parsers.json_parser import JsonParser
from src.parsers.github_parser import GithubParser

def test_resume_parser_date_range_helper():
    """Test the _is_date_range helper function."""
    assert _is_date_range("August 2023 - Present") is True
    assert _is_date_range(" June 2021 - May 2023 ") is True
    assert _is_date_range("2020 - 2023") is True
    assert _is_date_range("06/2020 - 04/2021") is True
    assert _is_date_range("Present") is True
    assert _is_date_range("Current") is True
    
    # Should be False
    assert _is_date_range("Lovely Professional University") is False
    assert _is_date_range("B.Tech in Computer Science") is False


def test_resume_parser_education_date_separation(tmp_path: Path):
    """Test that dates are not extracted as institutions."""
    text = """
EDUCATION
August 2023 - Present
B.Tech in Computer Science & Engineering
Lovely Professional University, Punjab
    """
    p = tmp_path / "resume.txt"
    p.write_text(text, encoding="utf-8")
    
    parser = ResumeParser()
    records = parser.parse(p)
    assert len(records) == 1
    
    edu = records[0].education
    assert len(edu) == 1
    assert "Lovely Professional University" in edu[0].institution
    assert edu[0].degree == "B.Tech"
    assert edu[0].end_year == 2023


def test_csv_parser_missing_fields_and_nulls(tmp_path: Path):
    """Test CSV with missing columns and empty rows."""
    text = """name,email,unknown_column
Hari,hari@test.com,ignore_this

,,
"""
    p = tmp_path / "test.csv"
    p.write_text(text, encoding="utf-8")
    
    parser = CsvParser()
    records = parser.parse(p)
    
    assert len(records) == 1
    assert records[0].full_name == "Hari"
    assert records[0].emails == ["hari@test.com"]


def test_json_parser_deep_nesting(tmp_path: Path):
    """Test JSON parser handles deeply nested arrays and missing contacts safely."""
    text = """
    {
        "candidates": [
            {
                "name": "Jane",
                "contact": {
                    "email": "jane@test.com"
                },
                "links": [
                    "https://github.com/jane",
                    "https://myportfolio.com"
                ]
            },
            {
                "name": "No Contact Info"
            }
        ]
    }
    """
    p = tmp_path / "test.json"
    p.write_text(text, encoding="utf-8")
    
    parser = JsonParser()
    records = parser.parse(p)
    
    assert len(records) == 2
    assert records[0].full_name == "Jane"
    assert records[0].emails == ["jane@test.com"]
    assert records[0].links is not None
    assert records[0].links.github == "https://github.com/jane"
    
    assert records[1].full_name == "No Contact Info"
    assert not records[1].emails


def test_github_parser_rate_limit_fallback(tmp_path: Path):
    """Test Github parser returns partial record instead of throwing when API fails."""
    # We test a known non-existent username that will return 404
    text = "https://github.com/this-user-definitely-does-not-exist-123456789\n"
    p = tmp_path / "github.txt"
    p.write_text(text, encoding="utf-8")
    
    parser = GithubParser()
    records = parser.parse(p)
    
    assert len(records) == 1
    assert records[0].full_name == "this-user-definitely-does-not-exist-123456789"
    assert records[0].links is not None
    assert records[0].links.github == "https://github.com/this-user-definitely-does-not-exist-123456789"
