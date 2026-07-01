"""Phone number normalization to E.164 format.

Uses Google's libphonenumber for robust international phone parsing.
Numbers that can't be parsed are dropped with a warning — we never invent data.
"""

from __future__ import annotations

import os

import phonenumbers

from src.utils.logger import get_logger

logger = get_logger(__name__)


def normalize_phone(raw: str, default_region: str | None = None) -> str | None:
    """Normalize a phone number string to E.164 format.

    Args:
        raw: Raw phone string (e.g. "(415) 555-2671", "+1-415-555-2671").
        default_region: ISO country code to assume if no country code is present.
                       Falls back to DEFAULT_PHONE_REGION env var, then "US".

    Returns:
        E.164 formatted string (e.g. "+14155552671"), or None if unparseable.
    """
    if not raw or not raw.strip():
        return None

    region = default_region

    try:
        parsed = phonenumbers.parse(raw.strip(), region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

        # Try without region as a fallback (number might include country code)
        parsed = phonenumbers.parse(raw.strip(), None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    except phonenumbers.NumberParseException:
        pass

    logger.warning("Could not parse phone number: '%s'", raw)
    return None


def normalize_phones(raw_phones: list[str], default_region: str | None = None) -> list[str]:
    """Normalize a list of phone numbers, dropping unparseable ones.

    Returns deduplicated E.164 numbers in the order they were first seen.
    """
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_phones:
        normalized = normalize_phone(raw, default_region)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result
