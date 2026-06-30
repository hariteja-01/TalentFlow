"""Skill name canonicalization.

Maps raw skill strings (from resumes, CSVs, APIs) to a consistent canonical
form using an alias lookup table. Unknown skills are title-cased as a fallback.
"""

from __future__ import annotations

from src.utils.constants import SKILL_ALIASES


def canonicalize_skill(raw: str) -> str:
    """Map a raw skill name to its canonical form.

    Lookup is case-insensitive. Unknown skills are returned title-cased
    so output is at least visually consistent.

    Args:
        raw: Raw skill string (e.g. "js", "machine learning", "TF").

    Returns:
        Canonical skill name (e.g. "JavaScript", "Machine Learning", "TensorFlow").
    """
    if not raw or not raw.strip():
        return raw

    key = raw.strip().lower()
    return SKILL_ALIASES.get(key, raw.strip().title())


def canonicalize_skills(raw_skills: list[str]) -> list[str]:
    """Canonicalize and deduplicate a list of skill names.

    Preserves first-seen order after deduplication.
    """
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_skills:
        canonical = canonicalize_skill(raw)
        # Deduplicate by canonical name (case-insensitive)
        canon_key = canonical.lower()
        if canon_key not in seen:
            seen.add(canon_key)
            result.append(canonical)

    return result
