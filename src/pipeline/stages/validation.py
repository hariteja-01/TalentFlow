"""Stage 7: Validation — verifies the final output matches the requested schema.

This is the last safety net before output. It catches:
  - Missing required fields
  - Type mismatches
  - Invalid values that slipped through normalization
"""

from __future__ import annotations

from typing import Any

from src.models.canonical import CanonicalProfile
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when the output fails schema validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


def validate_canonical(profile: CanonicalProfile) -> list[str]:
    """Validate a canonical profile for completeness and correctness.

    Returns a list of warning messages (empty = valid).
    Does NOT raise — the pipeline should still output partial profiles.
    """
    warnings: list[str] = []

    # candidate_id is required
    if not profile.candidate_id:
        warnings.append("Missing candidate_id")

    # full_name should be non-empty
    if not profile.full_name:
        warnings.append("Missing full_name")

    # Phones should be E.164
    for phone in profile.phones:
        if not phone.startswith("+"):
            warnings.append(f"Phone '{phone}' is not in E.164 format")

    # Location country should be ISO-3166 alpha-2
    if profile.location and profile.location.country:
        if len(profile.location.country) != 2 or not profile.location.country.isalpha():
            warnings.append(f"Country '{profile.location.country}' is not ISO-3166 alpha-2")

    # Experience dates should be YYYY-MM
    import re
    date_re = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
    for exp in profile.experience:
        if exp.start and not date_re.match(exp.start):
            warnings.append(f"Experience start date '{exp.start}' is not YYYY-MM format")
        if exp.end and not date_re.match(exp.end):
            warnings.append(f"Experience end date '{exp.end}' is not YYYY-MM format")

    # Overall confidence should be in [0, 1]
    if not 0.0 <= profile.overall_confidence <= 1.0:
        warnings.append(f"overall_confidence {profile.overall_confidence} outside [0, 1]")

    # Skill confidence should be in [0, 1]
    for skill in profile.skills:
        if not 0.0 <= skill.confidence <= 1.0:
            warnings.append(f"Skill '{skill.name}' confidence {skill.confidence} outside [0, 1]")

    if warnings:
        logger.warning("Profile %s has %d validation warnings", profile.candidate_id, len(warnings))
        for w in warnings:
            logger.warning("  - %s", w)

    return warnings


def validate_projected(output: dict[str, Any], config_fields: list[dict]) -> list[str]:
    """Validate a projected output dict against the config's type expectations.

    Returns a list of warning messages (empty = valid).
    """
    warnings: list[str] = []

    for field_cfg in config_fields:
        path = field_cfg.get("path", "")
        expected_type = field_cfg.get("type", "string")
        required = field_cfg.get("required", False)

        if path not in output:
            if required:
                warnings.append(f"Required field '{path}' missing from output")
            continue

        value = output[path]
        if value is None:
            continue  # None is acceptable for optional fields

        # Type check
        if expected_type == "string" and not isinstance(value, str):
            warnings.append(f"Field '{path}' expected string, got {type(value).__name__}")
        elif expected_type == "string[]" and not isinstance(value, list):
            warnings.append(f"Field '{path}' expected string[], got {type(value).__name__}")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            warnings.append(f"Field '{path}' expected number, got {type(value).__name__}")

    return warnings
