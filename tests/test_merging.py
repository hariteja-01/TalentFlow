"""Tests for the merge stage — identity matching and conflict resolution."""

import pytest

from src.models.canonical import Education, Experience, Links, Location
from src.models.intermediate import IntermediateRecord
from src.pipeline.stages.merging import merge_records


def _make_record(**kwargs) -> IntermediateRecord:
    """Helper to create an IntermediateRecord with defaults."""
    defaults = {
        "source_name": "test.json",
        "source_type": "json",
        "source_weight": 0.9,
    }
    defaults.update(kwargs)
    return IntermediateRecord(**defaults)


class TestIdentityMatching:
    """Tests for grouping records by candidate identity."""

    def test_same_email_merged(self):
        """Records with overlapping emails should merge into one profile."""
        records = [
            _make_record(
                source_name="a.json",
                full_name="Jane Doe",
                emails=["jane@example.com"],
            ),
            _make_record(
                source_name="b.csv",
                source_type="csv",
                source_weight=0.7,
                full_name="Jane M. Doe",
                emails=["jane@example.com", "jane2@example.com"],
            ),
        ]
        profiles = merge_records(records)
        assert len(profiles) == 1

    def test_different_emails_separate(self):
        """Records with no email overlap should become separate profiles."""
        records = [
            _make_record(full_name="Alice", emails=["alice@example.com"]),
            _make_record(full_name="Bob", emails=["bob@example.com"]),
        ]
        profiles = merge_records(records)
        assert len(profiles) == 2

    def test_name_fallback_matching(self):
        """Records with same name but no emails should merge."""
        records = [
            _make_record(
                source_name="a.json",
                full_name="Jane Doe",
                emails=[],
                phones=["+14155551234"],
            ),
            _make_record(
                source_name="b.csv",
                source_type="csv",
                full_name="Jane Doe",
                emails=[],
                phones=["+14155555678"],
            ),
        ]
        profiles = merge_records(records)
        assert len(profiles) == 1


class TestConflictResolution:
    """Tests for how conflicts are resolved during merge."""

    def test_highest_weight_wins_for_name(self):
        """Scalar fields should pick from the highest-weight source."""
        records = [
            _make_record(
                source_name="api.json",
                source_weight=0.9,
                full_name="Jane M. Doe",
                emails=["jane@example.com"],
            ),
            _make_record(
                source_name="hr.csv",
                source_type="csv",
                source_weight=0.7,
                full_name="Jane Doe",
                emails=["jane@example.com"],
            ),
        ]
        profiles = merge_records(records)
        assert profiles[0].full_name == "Jane M. Doe"

    def test_emails_union(self):
        """Emails from all sources should be unioned and deduped."""
        records = [
            _make_record(
                emails=["jane@a.com", "jane@b.com"],
            ),
            _make_record(
                emails=["jane@b.com", "jane@c.com"],
            ),
        ]
        profiles = merge_records(records)
        assert set(profiles[0].emails) == {"jane@a.com", "jane@b.com", "jane@c.com"}

    def test_skills_union_dedup(self):
        """Skills should be unioned and deduplicated by canonical name."""
        records = [
            _make_record(
                source_name="a.json",
                emails=["test@test.com"],
                skills=["Python", "JavaScript"],
            ),
            _make_record(
                source_name="b.csv",
                emails=["test@test.com"],
                skills=["Python", "Docker"],
            ),
        ]
        profiles = merge_records(records)
        skill_names = [s.name for s in profiles[0].skills]
        assert "Python" in skill_names
        assert "JavaScript" in skill_names
        assert "Docker" in skill_names
        # Python should appear only once
        assert skill_names.count("Python") == 1

    def test_experience_dedup_by_company_title(self):
        """Duplicate experience entries should be deduped."""
        exp = Experience(company="TechCorp", title="Engineer", start="2020-01")
        records = [
            _make_record(source_name="a.json", emails=["t@t.com"], experience=[exp]),
            _make_record(source_name="b.csv", emails=["t@t.com"], experience=[exp]),
        ]
        profiles = merge_records(records)
        assert len(profiles[0].experience) == 1

    def test_deterministic_candidate_id(self):
        """Same inputs should always produce the same candidate_id."""
        records = [
            _make_record(full_name="Jane", emails=["jane@test.com"]),
        ]
        id1 = merge_records(records)[0].candidate_id
        id2 = merge_records(records)[0].candidate_id
        assert id1 == id2


class TestProvenance:
    """Tests for provenance tracking during merge."""

    def test_provenance_populated(self):
        """Merged profiles should have provenance entries."""
        records = [
            _make_record(
                full_name="Test User",
                emails=["test@example.com"],
                skills=["Python"],
            ),
        ]
        profiles = merge_records(records)
        assert len(profiles[0].provenance) > 0

    def test_provenance_tracks_source(self):
        """Provenance should record which source a value came from."""
        records = [
            _make_record(
                source_name="api_data.json",
                full_name="Test User",
                emails=["test@example.com"],
            ),
        ]
        profiles = merge_records(records)
        sources = [p.source for p in profiles[0].provenance]
        assert "api_data.json" in sources


class TestMultiSourceIdentityMerge:
    """Explicit tests for complex multi-source identity resolution."""
    
    def test_multi_source_single_candidate_merge(self):
        """Test that 5 sources are correctly merged into a single CanonicalProfile."""
        records = [
            # 1. JSON (Highest weight, email1)
            _make_record(
                source_name="candidate.json",
                source_weight=0.9,
                full_name="Hari Teja Patnala",
                emails=["hari@example.com"],
                skills=["Python", "React"],
                experience=[Experience(company="Eightfold", title="SWE Intern")]
            ),
            # 2. CSV (Email1 + Email2 overlap)
            _make_record(
                source_name="candidate.csv",
                source_weight=0.7,
                full_name="Hari T.",
                emails=["hari@example.com", "hari.teja@gmail.com"],
                skills=["SQL"]
            ),
            # 3. PDF (Email2 overlap)
            _make_record(
                source_name="resume.pdf",
                source_weight=0.6,
                full_name="Hari Teja",
                emails=["hari.teja@gmail.com"],
                skills=["Python", "C++"],
                education=[Education(institution="LPU", end_year=2024)]
            ),
            # 4. GitHub (Name overlap fallback since no email)
            _make_record(
                source_name="github.com",
                source_weight=0.4,
                full_name="Hari Teja Patnala", # exact match with JSON
                emails=[],
                links=Links(github="https://github.com/hariteja-01")
            )
        ]
        
        profiles = merge_records(records)
        
        # Should be exactly 1 profile due to transitive email and name matches
        assert len(profiles) == 1, "Failed to merge 5 sources into 1 profile"
        
        profile = profiles[0]
        
        # Scalar picks highest weight (JSON)
        assert profile.full_name == "Hari Teja Patnala"
        
        # Emails unioned
        assert set(profile.emails) == {"hari@example.com", "hari.teja@gmail.com"}
        
        # Links merged from GitHub
        assert profile.links is not None
        assert profile.links.github == "https://github.com/hariteja-01"
        
        # Skills unioned
        skill_names = {s.name for s in profile.skills}
        assert skill_names == {"Python", "React", "SQL", "C++"}
        
        # Experience and Education collected
        assert len(profile.experience) == 1
        assert profile.experience[0].company == "Eightfold"
        assert len(profile.education) == 1
        assert profile.education[0].institution == "LPU"

    def test_url_overlap_identity_merge(self):
        """Test that records are merged if they share a GitHub URL, even without emails."""
        github_url = "https://github.com/hariteja-01"

        # Record 1: Resume with slightly different name, no email, but has GitHub
        r1 = _make_record(
            source_name="resume.pdf",
            source_weight=0.6,
            full_name="Hari Teja P.",
            emails=[],
            links=Links(github=github_url, portfolio=None, other=[])
        )

        # Record 2: JSON scrape with same GitHub URL
        r2 = _make_record(
            source_name="github_scrape",
            source_weight=0.9,
            full_name="Hari Teja Patnala",
            emails=[],
            links=Links(github=github_url, portfolio=None, other=[])
        )

        records = [r1, r2]
        merged_profiles = merge_records(records)

        # Both should be merged into exactly 1 profile
        assert len(merged_profiles) == 1
        profile = merged_profiles[0]
        
        # Name should come from highest weight source (r2)
        assert profile.full_name == "Hari Teja Patnala"
        # Links should be unioned
        assert profile.links.github == github_url
