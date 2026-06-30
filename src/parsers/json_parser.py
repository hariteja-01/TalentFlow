"""JSON source parser — for structured ATS/API payloads.

Handles both single candidate objects and arrays of candidates.
Includes an ATS field mapping layer that translates non-canonical
field names into our internal representation before extraction.
Missing or malformed fields are skipped, never invented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.canonical import Education, Experience, Links, Location
from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# ATS field mapping — translates vendor-specific field names to canonical ones.
# Each key is a non-canonical field name (case-insensitive lookup).
# Values are the canonical path we map to.
# This dictionary is intentionally extensible; add new mappings as you
# encounter new ATS vendors without touching extraction logic.
# ---------------------------------------------------------------------------
_ATS_FIELD_MAP: dict[str, str] = {
    # Name variants
    "candidate_name": "full_name",
    "applicant_name": "full_name",
    "name": "full_name",
    # Email variants
    "contact_email": "email",
    "email_address": "email",
    "primary_email": "email",
    # Phone variants
    "contact_phone": "phone",
    "phone_number": "phone",
    "mobile": "phone",
    # Location variants
    "address": "location",
    "candidate_location": "location",
    # Headline variants
    "current_position": "headline",
    "job_title": "headline",
    "current_title": "headline",
    "position": "headline",
    # Experience variants
    "work_history": "experience",
    "employment_history": "experience",
    "positions": "experience",
    "work_experience": "experience",
    # Education variants
    "academic_background": "education",
    "qualifications": "education",
    "degrees": "education",
    # Skill variants
    "competencies": "skills",
    "technical_skills": "skills",
    "expertise": "skills",
    "proficiencies": "skills",
    # Links variants
    "social_profiles": "links",
    "web_profiles": "links",
    "online_presence": "links",
    # Years of experience
    "total_experience": "years_experience",
    "yoe": "years_experience",
    "experience_years": "years_experience",
}

# Experience sub-field mapping (inside each work_history entry)
_ATS_EXP_FIELD_MAP: dict[str, str] = {
    "role": "title",
    "position": "title",
    "job_title": "title",
    "organization": "company",
    "employer": "company",
    "firm": "company",
    "start_date": "start",
    "from": "start",
    "end_date": "end",
    "to": "end",
    "description": "summary",
    "responsibilities": "summary",
}

# Education sub-field mapping
_ATS_EDU_FIELD_MAP: dict[str, str] = {
    "school": "institution",
    "university": "institution",
    "college": "institution",
    "qualification": "degree",
    "course": "field",
    "major": "field",
    "study_field": "field",
    "specialization": "field",
    "graduation_year": "end_year",
    "year": "end_year",
}


def _remap_dict(data: dict, field_map: dict[str, str]) -> dict:
    """Remap dictionary keys using the provided field mapping.

    Keys already in canonical form are kept as-is. Non-canonical keys
    are translated. Unmapped keys are passed through unchanged.
    """
    remapped: dict[str, Any] = {}
    for key, value in data.items():
        canonical_key = field_map.get(key.lower().strip(), key)
        # Don't overwrite a canonical key that already exists
        if canonical_key not in remapped:
            remapped[canonical_key] = value
    return remapped


class JsonParser(BaseParser):
    """Parses structured JSON candidate data with ATS field mapping."""

    @property
    def source_type(self) -> str:
        return "json"

    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Parse a JSON file containing one or more candidate records."""
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to read {file_path.name}: {e}")

        if not text.strip():
            raise ValueError(f"Empty JSON file: {file_path.name}")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path.name}: {e}")

        # Normalize to list of candidate dicts
        if isinstance(data, dict):
            # Could be a single candidate or a wrapper with a "candidates" key
            if "candidates" in data:
                candidates = data["candidates"]
            elif "applicants" in data:
                candidates = data["applicants"]
            elif "records" in data:
                candidates = data["records"]
            else:
                candidates = [data]
        elif isinstance(data, list):
            candidates = data
        else:
            raise ValueError(f"Unexpected JSON structure in {file_path.name}")

        records = []
        for i, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                logger.warning("Skipping non-dict entry at index %d in %s", i, file_path)
                continue

            # Apply ATS field mapping before extraction
            mapped = _remap_dict(candidate, _ATS_FIELD_MAP)
            record = self._extract_record(mapped, file_path)
            if record and record.has_candidate_data():
                records.append(record)
            elif record:
                logger.warning(
                    "Skipping JSON entry at index %d in %s: no recognizable candidate data",
                    i, file_path,
                )

        if not records:
            raise ValueError(f"File does not contain valid candidate data: {file_path.name}")

        logger.info("Parsed %d records from %s", len(records), file_path.name)
        return records

    def _extract_record(self, data: dict, file_path: Path) -> IntermediateRecord | None:
        """Extract a single IntermediateRecord from a (possibly remapped) JSON dict."""
        try:
            # Extract location
            location = None
            loc_data = data.get("location")
            if isinstance(loc_data, dict):
                loc_mapped = _remap_dict(loc_data, {"state": "region"})
                location = Location(
                    city=loc_mapped.get("city"),
                    region=loc_mapped.get("region"),
                    country=loc_mapped.get("country"),
                )
            elif isinstance(loc_data, str) and loc_data.strip():
                # Simple string location → try to parse "City, State, Country"
                location = self._parse_location_string(loc_data)

            # Extract links
            links = None
            links_data = data.get("links")
            if isinstance(links_data, dict):
                links = Links(
                    github=links_data.get("github"),
                    portfolio=links_data.get("portfolio"),
                    other=links_data.get("other", []),
                )
            elif isinstance(links_data, list):
                # Some ATS systems provide links as a flat list of URLs
                linkedin = github = portfolio = None
                other: list[str] = []
                for url in links_data:
                    if isinstance(url, str):
                        url_lower = url.lower()
                        if "linkedin.com" in url_lower:
                            linkedin = url
                        elif "github.com" in url_lower:
                            github = url
                        else:
                            other.append(url)
                if any([linkedin, github, other]):
                    links = Links(github=github, portfolio=portfolio, other=other)

            # Extract experience — with sub-field mapping
            experience = []
            for exp in data.get("experience", []):
                if isinstance(exp, dict):
                    exp_mapped = _remap_dict(exp, _ATS_EXP_FIELD_MAP)
                    experience.append(Experience(
                        company=exp_mapped.get("company"),
                        title=exp_mapped.get("title"),
                        start=exp_mapped.get("start"),
                        end=exp_mapped.get("end"),
                        summary=exp_mapped.get("summary"),
                    ))

            # Extract education — with sub-field mapping
            education = []
            for edu in data.get("education", []):
                if isinstance(edu, dict):
                    edu_mapped = _remap_dict(edu, _ATS_EDU_FIELD_MAP)
                    end_year = edu_mapped.get("end_year")
                    if isinstance(end_year, str):
                        try:
                            end_year = int(end_year)
                        except ValueError:
                            end_year = None
                    education.append(Education(
                        institution=edu_mapped.get("institution"),
                        degree=edu_mapped.get("degree"),
                        field=edu_mapped.get("field"),
                        end_year=end_year,
                    ))

            # Extract emails — handle string, list, or nested contact object
            emails = data.get("emails") or data.get("email") or []
            if isinstance(emails, str):
                emails = [emails]
            # Handle nested contact object: {"contact": {"email": "..."}}
            contact = data.get("contact")
            if isinstance(contact, dict):
                contact_email = contact.get("email") or contact.get("email_address")
                if contact_email:
                    if isinstance(contact_email, str):
                        emails = [contact_email] + (emails if isinstance(emails, list) else [])
                    elif isinstance(contact_email, list):
                        emails = contact_email + (emails if isinstance(emails, list) else [])
                contact_phone = contact.get("phone") or contact.get("phone_number")
                if contact_phone and "phones" not in data and "phone" not in data:
                    if isinstance(contact_phone, str):
                        data["phone"] = contact_phone
                    elif isinstance(contact_phone, list):
                        data["phones"] = contact_phone

            emails = [e.strip().lower() for e in emails if isinstance(e, str) and e.strip()]

            # Extract phones — handle both string and list
            phones = data.get("phones") or data.get("phone") or []
            if isinstance(phones, str):
                phones = [phones]
            phones = [str(p).strip() for p in phones if p]

            # Extract skills — handle list of strings or list of dicts
            raw_skills = data.get("skills", [])
            skills = []
            for s in raw_skills:
                if isinstance(s, str):
                    skills.append(s)
                elif isinstance(s, dict) and "name" in s:
                    skills.append(s["name"])

            # Extract years of experience
            yoe = data.get("years_experience")
            if isinstance(yoe, str):
                try:
                    yoe = float(yoe)
                except ValueError:
                    yoe = None

            return IntermediateRecord(
                source_name=file_path.name,
                source_type=self.source_type,
                source_weight=SOURCE_WEIGHTS.get(self.source_type, 0.5),
                full_name=data.get("full_name") or data.get("name"),
                emails=emails,
                phones=phones,
                location=location,
                links=links,
                headline=data.get("headline"),
                years_experience=yoe,
                skills=skills,
                experience=experience,
                education=education,
            )
        except Exception as e:
            logger.error("Error extracting record from JSON: %s", e)
            return None

    @staticmethod
    def _parse_location_string(loc_str: str) -> Location:
        """Best-effort parse of 'City, State, Country' strings."""
        parts = [p.strip() for p in loc_str.split(",")]
        if len(parts) >= 3:
            return Location(city=parts[0], region=parts[1], country=parts[2])
        elif len(parts) == 2:
            return Location(city=parts[0], region=parts[1])
        else:
            return Location(city=parts[0])

