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
    if key in SKILL_ALIASES:
        return SKILL_ALIASES[key]
        
    clean = raw.strip()
    # Only title-case if the skill is entirely lowercase or uppercase (e.g. "python" -> "Python")
    # If it has mixed casing (e.g. "REST APIs", "gRPC", "OpenAI"), preserve the original intentional casing.
    if clean.islower() or clean.isupper():
        return clean.title()
    return clean


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
