"""Location normalization — country codes to ISO-3166 alpha-2.

Handles:
- Full country names ("United States" → "US")
- Common abbreviations ("USA" → "US")
- Already-valid alpha-2 codes (passthrough)
- US state names/abbreviations → region normalization
"""

from __future__ import annotations

import pycountry

from src.models.canonical import Location
from src.utils.constants import US_STATES
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Common country name overrides that pycountry doesn't handle well
_COUNTRY_OVERRIDES: dict[str, str] = {
    "usa": "US",
    "u.s.a.": "US",
    "u.s.": "US",
    "united states of america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "india": "IN",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "japan": "JP",
    "china": "CN",
    "brazil": "BR",
    "south korea": "KR",
    "korea": "KR",
    "singapore": "SG",
    "israel": "IL",
    "netherlands": "NL",
    "sweden": "SE",
    "switzerland": "CH",
    "ireland": "IE",
    "new zealand": "NZ",
    "spain": "ES",
    "italy": "IT",
    "mexico": "MX",
    "russia": "RU",
    "uae": "AE",
    "united arab emirates": "AE",
}


def normalize_country(raw: str | None) -> str | None:
    """Normalize a country string to ISO-3166 alpha-2 code.

    Args:
        raw: Country name, abbreviation, or code.

    Returns:
        Two-letter ISO-3166 alpha-2 code, or None if unresolvable.
    """
    if not raw or not raw.strip():
        return None

    cleaned = raw.strip()

    # Check our overrides first (handles UK→GB, USA→US, etc.)
    lower = cleaned.lower()
    if lower in _COUNTRY_OVERRIDES:
        return _COUNTRY_OVERRIDES[lower]

    # Already a valid alpha-2 code?
    if len(cleaned) == 2 and cleaned.upper().isalpha():
        try:
            pycountry.countries.get(alpha_2=cleaned.upper())
            return cleaned.upper()
        except (KeyError, LookupError):
            pass

    # Try pycountry fuzzy search
    try:
        results = pycountry.countries.search_fuzzy(cleaned)
        if results:
            return results[0].alpha_2
    except LookupError:
        pass

    logger.warning("Could not normalize country: '%s'", raw)
    return None


def normalize_region(raw: str | None) -> str | None:
    """Normalize a US state name or abbreviation to full name.

    For non-US regions, returns the value as-is (title-cased).
    """
    if not raw or not raw.strip():
        return None

    cleaned = raw.strip()

    # Check if it's a US state abbreviation
    upper = cleaned.upper()
    if upper in US_STATES:
        return US_STATES[upper]

    # Check if it's already a full state name
    for abbr, full_name in US_STATES.items():
        if cleaned.lower() == full_name.lower():
            return full_name

    # Non-US region — return title-cased
    return cleaned.title()


def normalize_location(location: Location | None) -> Location | None:
    """Normalize all parts of a location object."""
    if location is None:
        return None

    return Location(
        city=location.city.strip().title() if location.city else None,
        region=normalize_region(location.region),
        country=normalize_country(location.country),
    )
