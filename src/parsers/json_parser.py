"""JSON source parser — for structured ATS/API payloads.

Handles both single candidate objects and arrays of candidates.
Missing or malformed fields are skipped, never invented.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models.canonical import Education, Experience, Links, Location
from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)


class JsonParser(BaseParser):
    """Parses structured JSON candidate data."""

    @property
    def source_type(self) -> str:
        return "json"

    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Parse a JSON file containing one or more candidate records."""
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.error("Failed to read %s: %s", file_path, e)
            return []

        if not text.strip():
            logger.warning("Empty JSON file: %s", file_path)
            return []

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", file_path, e)
            return []

        # Normalize to list of candidate dicts
        if isinstance(data, dict):
            # Could be a single candidate or a wrapper with a "candidates" key
            if "candidates" in data:
                candidates = data["candidates"]
            else:
                candidates = [data]
        elif isinstance(data, list):
            candidates = data
        else:
            logger.error("Unexpected JSON structure in %s", file_path)
            return []

        records = []
        for i, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                logger.warning("Skipping non-dict entry at index %d in %s", i, file_path)
                continue
            record = self._extract_record(candidate, file_path)
            if record:
                records.append(record)

        logger.info("Parsed %d records from %s", len(records), file_path.name)
        return records

    def _extract_record(self, data: dict, file_path: Path) -> IntermediateRecord | None:
        """Extract a single IntermediateRecord from a JSON dict."""
        try:
            # Extract location
            location = None
            loc_data = data.get("location")
            if isinstance(loc_data, dict):
                location = Location(
                    city=loc_data.get("city"),
                    region=loc_data.get("region") or loc_data.get("state"),
                    country=loc_data.get("country"),
                )
            elif isinstance(loc_data, str) and loc_data.strip():
                # Simple string location → try to parse "City, State, Country"
                location = self._parse_location_string(loc_data)

            # Extract links
            links = None
            links_data = data.get("links")
            if isinstance(links_data, dict):
                links = Links(
                    linkedin=links_data.get("linkedin"),
                    github=links_data.get("github"),
                    portfolio=links_data.get("portfolio"),
                    other=links_data.get("other", []),
                )

            # Extract experience
            experience = []
            for exp in data.get("experience", []):
                if isinstance(exp, dict):
                    experience.append(Experience(
                        company=exp.get("company"),
                        title=exp.get("title"),
                        start=exp.get("start"),
                        end=exp.get("end"),
                        summary=exp.get("summary"),
                    ))

            # Extract education
            education = []
            for edu in data.get("education", []):
                if isinstance(edu, dict):
                    education.append(Education(
                        institution=edu.get("institution"),
                        degree=edu.get("degree"),
                        field=edu.get("field"),
                        end_year=edu.get("end_year"),
                    ))

            # Extract emails — handle both string and list
            emails = data.get("emails") or data.get("email") or []
            if isinstance(emails, str):
                emails = [emails]
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
                years_experience=data.get("years_experience"),
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
