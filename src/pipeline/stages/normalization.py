"""Stage 3: Normalization — standardizes formats across all records.

Applied to IntermediateRecords BEFORE merging, so the merge stage
works with consistently formatted data.
"""

from __future__ import annotations

from src.models.intermediate import IntermediateRecord
from src.normalizers.date import normalize_date, normalize_year
from src.normalizers.location import normalize_location
from src.normalizers.phone import normalize_phones
from src.normalizers.skills import canonicalize_skills
from src.utils.logger import get_logger

logger = get_logger(__name__)


def normalize_record(record: IntermediateRecord) -> IntermediateRecord:
    """Apply all normalizations to a single IntermediateRecord.

    Returns a new record — does not mutate the input.
    """
    normalized_phones = normalize_phones(record.phones)
    normalized_location = normalize_location(record.location)
    normalized_skills = canonicalize_skills(record.skills)

    normalized_emails = list(dict.fromkeys(
        e.strip().lower() for e in record.emails if e.strip()
    ))

    normalized_experience = []
    for exp in record.experience:
        normalized_experience.append(exp.model_copy(update={
            "start": normalize_date(exp.start),
            "end": normalize_date(exp.end),
        }))

    normalized_education = []
    for edu in record.education:
        normalized_education.append(edu.model_copy(update={
            "end_year": normalize_year(edu.end_year) if edu.end_year else edu.end_year,
        }))

    normalized_name = record.full_name
    if normalized_name:
        normalized_name = normalized_name.strip()
        if normalized_name.isupper() or normalized_name.islower():
            normalized_name = normalized_name.title()

    return record.model_copy(update={
        "full_name": normalized_name,
        "emails": normalized_emails,
        "phones": normalized_phones,
        "location": normalized_location,
        "skills": normalized_skills,
        "experience": normalized_experience,
        "education": normalized_education,
    })


def normalize_all(records: list[IntermediateRecord]) -> list[IntermediateRecord]:
    """Normalize all intermediate records.

    Records that fail normalization are kept as-is with a warning.
    """
    results = []
    for record in records:
        try:
            results.append(normalize_record(record))
        except Exception as e:
            logger.warning(
                "Normalization failed for record from %s: %s — keeping raw",
                record.source_name, e,
            )
            results.append(record)

    logger.info("Normalized %d records", len(results))
    return results
