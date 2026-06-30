"""Stage 5: Confidence scoring — assigns per-field and overall confidence.

Confidence formula per field:
    confidence(f) = source_weight × completeness × agreement_bonus

Where:
    - source_weight: reliability of the source (0.0–1.0)
    - completeness:  1.0 if field is populated, 0.0 if empty
    - agreement_bonus: 1.2× if ≥2 sources agree on the value (capped at 1.0)

Overall confidence: mean of all per-field confidences.
"""

from __future__ import annotations

from src.models.canonical import CanonicalProfile, Provenance
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Fields to score — each maps to a check for "is this field populated?"
_SCORABLE_FIELDS = [
    "full_name",
    "emails",
    "phones",
    "location",
    "headline",
    "years_experience",
    "skills",
    "experience",
    "education",
    "links",
]


def score_confidence(profile: CanonicalProfile) -> CanonicalProfile:
    """Compute per-field and overall confidence for a canonical profile.

    Also updates skill-level confidence scores.
    Returns a new profile with confidence values populated.
    """
    field_scores: list[float] = []
    provenance_by_field = _index_provenance(profile.provenance)

    for field_name in _SCORABLE_FIELDS:
        score = _score_field(profile, field_name, provenance_by_field)
        field_scores.append(score)

    # Overall confidence = mean of field scores
    overall = sum(field_scores) / len(field_scores) if field_scores else 0.0
    overall = round(min(overall, 1.0), 3)

    # Score individual skills
    scored_skills = []
    for skill in profile.skills:
        # Skill confidence: base 0.5 + 0.15 per source, capped at 1.0
        skill_conf = min(0.5 + 0.15 * len(skill.sources), 1.0)
        scored_skills.append(skill.model_copy(update={"confidence": round(skill_conf, 3)}))

    return profile.model_copy(update={
        "overall_confidence": overall,
        "skills": scored_skills,
    })


def _score_field(
    profile: CanonicalProfile,
    field_name: str,
    provenance_by_field: dict[str, list[Provenance]],
) -> float:
    """Score a single field's confidence."""
    value = getattr(profile, field_name, None)

    # Completeness: is the field populated?
    completeness = _check_completeness(value)
    if completeness == 0.0:
        return 0.0

    # Source weight: highest weight among sources that contributed
    source_weight = _get_source_weight(field_name, provenance_by_field)

    # Agreement bonus: 1.2× if multiple sources contributed
    source_count = len(provenance_by_field.get(field_name, []))
    agreement_bonus = 1.2 if source_count >= 2 else 1.0

    score = source_weight * completeness * agreement_bonus
    return round(min(score, 1.0), 3)


def _check_completeness(value: object) -> float:
    """Check if a field value is meaningfully populated."""
    if value is None:
        return 0.0
    if isinstance(value, str) and not value.strip():
        return 0.0
    if isinstance(value, list) and len(value) == 0:
        return 0.0
    return 1.0


def _get_source_weight(
    field_name: str,
    provenance_by_field: dict[str, list[Provenance]],
) -> float:
    """Get the highest source weight among contributors to this field."""
    prov_entries = provenance_by_field.get(field_name, [])
    if not prov_entries:
        return 0.5  # Default weight if no provenance

    max_weight = 0.0
    for prov in prov_entries:
        # Infer source type from source name extension
        source_name = prov.source.lower()
        for ext, source_type in [(".json", "json"), (".csv", "csv"), (".txt", "resume")]:
            if source_name.endswith(ext):
                max_weight = max(max_weight, SOURCE_WEIGHTS.get(source_type, 0.5))
                break
        else:
            max_weight = max(max_weight, 0.5)

    return max_weight


def _index_provenance(provenance: list[Provenance]) -> dict[str, list[Provenance]]:
    """Index provenance entries by field name for quick lookup."""
    index: dict[str, list[Provenance]] = {}
    for prov in provenance:
        # Normalize field names (e.g. "links.linkedin" → "links")
        base_field = prov.field.split(".")[0]
        index.setdefault(base_field, []).append(prov)
    return index
