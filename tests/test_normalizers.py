"""Tests for normalizer modules."""

import pytest

from src.normalizers.phone import normalize_phone, normalize_phones
from src.normalizers.date import normalize_date, normalize_year
from src.normalizers.location import normalize_country, normalize_region, normalize_location
from src.normalizers.skills import canonicalize_skill, canonicalize_skills
from src.models.canonical import Location


class TestPhoneNormalizer:
    """Tests for E.164 phone normalization."""

    def test_us_phone_with_parens(self):
        assert normalize_phone("(415) 555-2671", "US") == "+14155552671"

    def test_us_phone_with_dashes(self):
        assert normalize_phone("415-555-2671", "US") == "+14155552671"

    def test_us_phone_already_e164(self):
        assert normalize_phone("+14155552671") == "+14155552671"

    def test_us_phone_with_country_code(self):
        assert normalize_phone("+1 (415) 555-2671") == "+14155552671"

    def test_uk_phone(self):
        result = normalize_phone("+44 20 7946 0958")
        assert result == "+442079460958"

    def test_empty_string(self):
        assert normalize_phone("") is None

    def test_none_input(self):
        assert normalize_phone(None) is None

    def test_garbage_input(self):
        assert normalize_phone("not-a-phone") is None

    def test_normalize_phones_deduplication(self):
        result = normalize_phones(["(415) 555-2671", "415-555-2671", "+14155552671"], "US")
        assert result == ["+14155552671"]

    def test_normalize_phones_drops_invalid(self):
        result = normalize_phones(["(415) 555-2671", "garbage", ""], "US")
        assert result == ["+14155552671"]


class TestDateNormalizer:
    """Tests for YYYY-MM date normalization."""

    def test_already_normalized(self):
        assert normalize_date("2020-01") == "2020-01"

    def test_month_year_string(self):
        assert normalize_date("January 2020") == "2020-01"

    def test_abbreviated_month(self):
        assert normalize_date("Jan 2020") == "2020-01"

    def test_year_only(self):
        assert normalize_date("2020") == "2020-01"

    def test_present(self):
        assert normalize_date("Present") is None

    def test_current(self):
        assert normalize_date("Current") is None

    def test_empty(self):
        assert normalize_date("") is None

    def test_none(self):
        assert normalize_date(None) is None

    def test_normalize_year_int(self):
        assert normalize_year(2020) == 2020

    def test_normalize_year_string(self):
        assert normalize_year("2020") == 2020

    def test_normalize_year_none(self):
        assert normalize_year(None) is None


class TestLocationNormalizer:
    """Tests for ISO-3166 country normalization."""

    def test_country_full_name(self):
        assert normalize_country("United States") == "US"

    def test_country_abbreviation(self):
        assert normalize_country("USA") == "US"

    def test_country_alpha2(self):
        assert normalize_country("US") == "US"

    def test_country_uk(self):
        assert normalize_country("UK") == "GB"

    def test_country_india(self):
        assert normalize_country("India") == "IN"

    def test_country_empty(self):
        assert normalize_country("") is None

    def test_country_none(self):
        assert normalize_country(None) is None

    def test_region_state_abbrev(self):
        assert normalize_region("CA") == "California"

    def test_region_state_full(self):
        assert normalize_region("California") == "California"

    def test_region_non_us(self):
        assert normalize_region("Bavaria") == "Bavaria"

    def test_normalize_location_full(self):
        loc = Location(city="san francisco", region="CA", country="United States")
        result = normalize_location(loc)
        assert result.city == "San Francisco"
        assert result.region == "California"
        assert result.country == "US"

    def test_normalize_location_none(self):
        assert normalize_location(None) is None


class TestSkillNormalizer:
    """Tests for skill name canonicalization."""

    def test_known_alias_lowercase(self):
        assert canonicalize_skill("js") == "JavaScript"

    def test_known_alias_mixed_case(self):
        assert canonicalize_skill("TensorFlow") == "TensorFlow"

    def test_known_alias_abbreviation(self):
        assert canonicalize_skill("k8s") == "Kubernetes"

    def test_known_alias_ml(self):
        assert canonicalize_skill("ML") == "Machine Learning"

    def test_unknown_skill_title_cased(self):
        assert canonicalize_skill("my custom skill") == "My Custom Skill"

    def test_canonicalize_skills_dedup(self):
        result = canonicalize_skills(["Python", "python", "PYTHON"])
        assert result == ["Python"]

    def test_canonicalize_skills_aliases(self):
        result = canonicalize_skills(["js", "tf", "k8s"])
        assert result == ["JavaScript", "TensorFlow", "Kubernetes"]

    def test_canonicalize_skills_preserves_order(self):
        result = canonicalize_skills(["Docker", "Python", "AWS"])
        assert result == ["Docker", "Python", "AWS"]
