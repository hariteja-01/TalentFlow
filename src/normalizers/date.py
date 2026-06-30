"""Date normalization to YYYY-MM format.

Handles various date formats seen in resumes and HR data:
- "January 2020", "Jan 2020"
- "2020-01", "2020/01"
- "01/2020"
- "2020" (year only → YYYY-01)
- "Present", "Current" → None (signals ongoing)
"""

from __future__ import annotations

import re

from dateutil import parser as dateutil_parser

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Patterns that mean "still in this role"
_PRESENT_PATTERNS = re.compile(
    r"^(present|current|now|ongoing|today)$", re.IGNORECASE
)

# Quick check for a standalone 4-digit year
_YEAR_ONLY = re.compile(r"^\d{4}$")

# YYYY-MM already normalized
_YYYY_MM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def normalize_date(raw: str | None) -> str | None:
    """Normalize a date string to YYYY-MM format.

    Args:
        raw: Raw date string from any source.

    Returns:
        "YYYY-MM" string, or None if the value represents "present" or is unparseable.
    """
    if not raw or not raw.strip():
        return None

    cleaned = raw.strip()

    # "Present" / "Current" → ongoing, no end date
    if _PRESENT_PATTERNS.match(cleaned):
        return None

    # Already in target format
    if _YYYY_MM.match(cleaned):
        return cleaned

    # Bare year → assume January
    if _YEAR_ONLY.match(cleaned):
        return f"{cleaned}-01"

    # Try dateutil for everything else (handles "Jan 2020", "01/2020", etc.)
    try:
        parsed = dateutil_parser.parse(cleaned, dayfirst=False)
        return parsed.strftime("%Y-%m")
    except (ValueError, OverflowError):
        pass

    logger.warning("Could not parse date: '%s'", raw)
    return None


def normalize_year(raw: str | int | None) -> int | None:
    """Extract a 4-digit year from a string or int.

    Used for education end_year fields.
    """
    if raw is None:
        return None

    raw_str = str(raw).strip()
    match = re.search(r"\b(19|20)\d{2}\b", raw_str)
    if match:
        return int(match.group(0))

    return None
