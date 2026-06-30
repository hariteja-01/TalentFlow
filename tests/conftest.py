"""Test fixtures and shared configuration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Project root for resolving sample data paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INPUTS = PROJECT_ROOT / "sample_inputs"
CONFIGS = PROJECT_ROOT / "configs"


@pytest.fixture
def sample_json_path() -> Path:
    return SAMPLE_INPUTS / "structured" / "candidate_api.json"


@pytest.fixture
def sample_csv_path() -> Path:
    return SAMPLE_INPUTS / "structured" / "candidates.csv"


@pytest.fixture
def sample_resume_path() -> Path:
    return SAMPLE_INPUTS / "unstructured" / "resume_jane_doe.txt"


@pytest.fixture
def custom_config_path() -> Path:
    return CONFIGS / "custom_config.json"


@pytest.fixture
def empty_file(tmp_path: Path) -> Path:
    """Create an empty JSON file for edge case testing."""
    f = tmp_path / "empty.json"
    f.write_text("")
    return f


@pytest.fixture
def malformed_json(tmp_path: Path) -> Path:
    """Create a malformed JSON file."""
    f = tmp_path / "bad.json"
    f.write_text("{this is not: valid json!!!")
    return f


@pytest.fixture
def garbage_csv(tmp_path: Path) -> Path:
    """Create a CSV with garbage data."""
    f = tmp_path / "garbage.csv"
    f.write_text("col1,col2,col3\n!@#,$%^,&*(\n")
    return f


@pytest.fixture
def valid_json_single(tmp_path: Path) -> Path:
    """Create a minimal valid JSON candidate file."""
    data = {
        "full_name": "Test User",
        "email": "test@example.com",
        "phones": ["+14155551234"],
        "skills": ["Python", "SQL"],
    }
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data))
    return f
