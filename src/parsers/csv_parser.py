"""CSV source parser — for HR spreadsheet exports.

Handles common CSV layouts with flexible column name mapping.
Each row becomes one IntermediateRecord.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from src.models.canonical import Education, Experience, Links, Location
from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Map common CSV column names to our intermediate fields (case-insensitive)
_COLUMN_ALIASES: dict[str, str] = {
    "name": "full_name",
    "full_name": "full_name",
    "full name": "full_name",
    "candidate_name": "full_name",
    "email": "emails",
    "emails": "emails",
    "email_address": "emails",
    "phone": "phones",
    "phones": "phones",
    "phone_number": "phones",
    "city": "city",
    "state": "region",
    "region": "region",
    "country": "country",
    "location": "location_str",
    "linkedin": "linkedin",
    "linkedin_url": "linkedin",
    "github": "github",
    "github_url": "github",
    "portfolio": "portfolio",
    "website": "portfolio",
    "headline": "headline",
    "title": "headline",
    "current_title": "headline",
    "years_experience": "years_experience",
    "yoe": "years_experience",
    "experience_years": "years_experience",
    "skills": "skills",
    "company": "company",
    "current_company": "company",
    "degree": "degree",
    "institution": "institution",
    "school": "institution",
    "university": "institution",
    "field_of_study": "field",
    "major": "field",
    "graduation_year": "end_year",
    "grad_year": "end_year",
}


class CsvParser(BaseParser):
    """Parses CSV files with flexible column name mapping."""

    @property
    def source_type(self) -> str:
        return "csv"

    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Parse a CSV file into intermediate records."""
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback encoding for non-UTF-8 files
            try:
                text = file_path.read_text(encoding="latin-1")
                logger.warning("Used latin-1 fallback encoding for %s", file_path)
        except OSError as e:
            raise ValueError(f"Failed to read {file_path.name}: {e}")

        if not text.strip():
            raise ValueError(f"Empty CSV file: {file_path.name}")

        try:
            reader = csv.DictReader(StringIO(text))
            if reader.fieldnames is None:
                logger.warning("No headers found in CSV: %s", file_path)
                return []
        except csv.Error as e:
            raise ValueError(f"CSV parsing error in {file_path.name}: {e}")

        # Map actual column names to our canonical field names
        column_map = self._build_column_map(reader.fieldnames)

        records = []
        for row_num, row in enumerate(reader, start=2):  # Row 1 is header
            record = self._extract_record(row, column_map, file_path, row_num)
            if record:
                records.append(record)

        logger.info("Parsed %d records from %s", len(records), file_path.name)
        return records

    @staticmethod
    def _build_column_map(fieldnames: list[str]) -> dict[str, str]:
        """Map actual CSV column names to our intermediate field names."""
        mapping = {}
        for col in fieldnames:
            normalized = col.strip().lower()
            if normalized in _COLUMN_ALIASES:
                mapping[col] = _COLUMN_ALIASES[normalized]
        return mapping

    def _extract_record(
        self,
        row: dict[str, str],
        column_map: dict[str, str],
        file_path: Path,
        row_num: int,
    ) -> IntermediateRecord | None:
        """Extract one IntermediateRecord from a CSV row."""
        try:
            # Build a field-value dict from the mapped columns
            fields: dict[str, str] = {}
            for col_name, field_name in column_map.items():
                value = row.get(col_name, "").strip()
                if value:
                    fields[field_name] = value

            # Skip completely empty rows
            if not fields:
                return None

            # Parse emails (may be semicolon or comma separated in a single cell)
            emails = []
            if "emails" in fields:
                raw = fields["emails"]
                for sep in [";", ","]:
                    if sep in raw:
                        emails = [e.strip().lower() for e in raw.split(sep) if e.strip()]
                        break
                else:
                    emails = [raw.strip().lower()]

            # Parse phones
            phones = []
            if "phones" in fields:
                raw = fields["phones"]
                for sep in [";", ","]:
                    if sep in raw:
                        phones = [p.strip() for p in raw.split(sep) if p.strip()]
                        break
                else:
                    phones = [raw.strip()]

            # Build location
            location = None
            if any(k in fields for k in ("city", "region", "country", "location_str")):
                if "location_str" in fields:
                    location = self._parse_location_string(fields["location_str"])
                else:
                    location = Location(
                        city=fields.get("city"),
                        region=fields.get("region"),
                        country=fields.get("country"),
                    )

            # Build links
            links = None
            if any(k in fields for k in ("linkedin", "github", "portfolio")):
                links = Links(
                    linkedin=fields.get("linkedin"),
                    github=fields.get("github"),
                    portfolio=fields.get("portfolio"),
                )

            # Parse skills (comma-separated)
            skills = []
            if "skills" in fields:
                skills = [s.strip() for s in fields["skills"].split(",") if s.strip()]

            # Parse years of experience
            yoe = None
            if "years_experience" in fields:
                try:
                    yoe = float(fields["years_experience"])
                except ValueError:
                    pass

            # Build experience from current company/title if present
            experience = []
            if "company" in fields or "headline" in fields:
                experience.append(Experience(
                    company=fields.get("company"),
                    title=fields.get("headline"),
                ))

            # Build education if present
            education = []
            if any(k in fields for k in ("institution", "degree", "field", "end_year")):
                end_year = None
                if "end_year" in fields:
                    try:
                        end_year = int(fields["end_year"])
                    except ValueError:
                        pass
                education.append(Education(
                    institution=fields.get("institution"),
                    degree=fields.get("degree"),
                    field=fields.get("field"),
                    end_year=end_year,
                ))

            return IntermediateRecord(
                source_name=file_path.name,
                source_type=self.source_type,
                source_weight=SOURCE_WEIGHTS.get(self.source_type, 0.5),
                full_name=fields.get("full_name"),
                emails=emails,
                phones=phones,
                location=location,
                links=links,
                headline=fields.get("headline"),
                years_experience=yoe,
                skills=skills,
                experience=experience,
                education=education,
            )
        except Exception as e:
            logger.error("Error extracting CSV row %d from %s: %s", row_num, file_path, e)
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
