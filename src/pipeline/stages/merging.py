"""Stage 4: Merging — groups records by candidate identity and resolves conflicts.

Identity matching:
  1. Primary: email overlap (any shared email → same person)
  2. Fallback: exact full name match (case-insensitive)

Conflict resolution:
  - Union + dedup for list fields (emails, phones, skills)
  - Highest source-weight wins for scalar fields (name, headline, location)
  - All entries kept for experience and education (sorted by date)
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from src.models.canonical import (
    CanonicalProfile,
    Education,
    Experience,
    Links,
    Location,
    Provenance,
    Skill,
)
from src.models.intermediate import IntermediateRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)


def merge_records(records: list[IntermediateRecord]) -> list[CanonicalProfile]:
    """Group records by candidate identity and merge each group.

    Returns one CanonicalProfile per unique candidate.
    """
    groups = _group_by_identity(records)
    profiles = []

    for group_key, group_records in groups.items():
        profile = _merge_group(group_records)
        profiles.append(profile)

    logger.info("Merged %d records into %d profiles", len(records), len(profiles))
    return profiles


def _group_by_identity(records: list[IntermediateRecord]) -> dict[str, list[IntermediateRecord]]:
    """Group records that belong to the same candidate.

    Uses Union-Find logic: if record A and B share an email,
    they're the same person. Transitively merged.
    """
    # Map each email to a canonical group key
    email_to_group: dict[str, str] = {}
    # Map each group key to its records
    groups: dict[str, list[IntermediateRecord]] = defaultdict(list)
    # Track name-based groups as fallback
    name_to_group: dict[str, str] = {}

    for record in records:
        # Try to find an existing group via email overlap
        matching_group = None
        for email in record.emails:
            email_lower = email.lower()
            if email_lower in email_to_group:
                matching_group = email_to_group[email_lower]
                break

        # Fallback: try exact name match
        if matching_group is None and record.full_name:
            name_key = record.full_name.strip().lower()
            if name_key in name_to_group:
                matching_group = name_to_group[name_key]

        # Create new group if no match found
        if matching_group is None:
            matching_group = _generate_group_key(record)

        # Register all emails to this group
        for email in record.emails:
            email_to_group[email.lower()] = matching_group

        # Register name to this group
        if record.full_name:
            name_to_group[record.full_name.strip().lower()] = matching_group

        groups[matching_group].append(record)

    return dict(groups)


def _generate_group_key(record: IntermediateRecord) -> str:
    """Generate a stable group key for a new candidate group."""
    # Use first email if available, otherwise name, otherwise source + hash
    if record.emails:
        seed = record.emails[0].lower()
    elif record.full_name:
        seed = record.full_name.strip().lower()
    else:
        seed = f"{record.source_name}:{id(record)}"

    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _merge_group(records: list[IntermediateRecord]) -> CanonicalProfile:
    """Merge multiple records into a single CanonicalProfile.

    Conflict resolution strategy:
    - Scalars: highest source_weight wins
    - Lists: union with dedup
    - Experience/Education: collect all, deduplicate, sort
    """
    # Sort records by source_weight descending so highest-weight is first
    sorted_records = sorted(records, key=lambda r: r.source_weight, reverse=True)
    provenance: list[Provenance] = []

    # --- Scalar fields: pick from highest-weight source ---
    full_name = _pick_scalar(sorted_records, "full_name", provenance)
    headline = _pick_scalar(sorted_records, "headline", provenance)
    years_experience = _pick_scalar(sorted_records, "years_experience", provenance)

    # --- Location: pick from highest-weight source that has one ---
    location = _pick_location(sorted_records, provenance)

    # --- Links: merge across sources ---
    links = _merge_links(sorted_records, provenance)

    # --- List fields: union + dedup ---
    emails = _merge_list_field(sorted_records, "emails", provenance)
    phones = _merge_list_field(sorted_records, "phones", provenance)

    # --- Skills: union, deduplicate by canonical name ---
    skills = _merge_skills(sorted_records, provenance)

    # --- Experience: collect all, deduplicate ---
    experience = _merge_experience(sorted_records, provenance)

    # --- Education: collect all, deduplicate ---
    education = _merge_education(sorted_records, provenance)

    # --- Generate deterministic candidate ID ---
    candidate_id = _generate_candidate_id(emails, full_name)

    return CanonicalProfile(
        candidate_id=candidate_id,
        full_name=full_name or "",
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        provenance=provenance,
        overall_confidence=0.0,  # Computed in the confidence stage
    )


def _pick_scalar(
    records: list[IntermediateRecord],
    field: str,
    provenance: list[Provenance],
) -> str | float | None:
    """Pick a scalar field value from the highest-weight source that has it."""
    for record in records:
        value = getattr(record, field, None)
        if value is not None and value != "":
            provenance.append(Provenance(
                field=field,
                source=record.source_name,
                method="merged-highest-weight",
            ))
            return value
    return None


def _pick_location(
    records: list[IntermediateRecord],
    provenance: list[Provenance],
) -> Location | None:
    """Pick location from highest-weight source that has one."""
    for record in records:
        if record.location and (record.location.city or record.location.country):
            provenance.append(Provenance(
                field="location",
                source=record.source_name,
                method="merged-highest-weight",
            ))
            return record.location
    return None


def _merge_links(
    records: list[IntermediateRecord],
    provenance: list[Provenance],
) -> Links | None:
    """Merge links across all sources, preferring first non-None value."""
    linkedin = github = portfolio = None
    other: list[str] = []

    for record in records:
        if not record.links:
            continue
        if not linkedin and record.links.linkedin:
            linkedin = record.links.linkedin
            provenance.append(Provenance(
                field="links.linkedin", source=record.source_name, method="merged-first-seen",
            ))
        if not github and record.links.github:
            github = record.links.github
            provenance.append(Provenance(
                field="links.github", source=record.source_name, method="merged-first-seen",
            ))
        if not portfolio and record.links.portfolio:
            portfolio = record.links.portfolio
            provenance.append(Provenance(
                field="links.portfolio", source=record.source_name, method="merged-first-seen",
            ))
        for url in record.links.other:
            if url not in other:
                other.append(url)

    if not any([linkedin, github, portfolio, other]):
        return None

    return Links(linkedin=linkedin, github=github, portfolio=portfolio, other=other)


def _merge_list_field(
    records: list[IntermediateRecord],
    field: str,
    provenance: list[Provenance],
) -> list[str]:
    """Union-merge a list field across all records, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    sources_logged = False

    for record in records:
        values = getattr(record, field, [])
        for value in values:
            key = value.lower() if isinstance(value, str) else str(value)
            if key not in seen:
                seen.add(key)
                result.append(value)
                if not sources_logged:
                    provenance.append(Provenance(
                        field=field, source=record.source_name, method="merged-union",
                    ))
                    sources_logged = True

    return result


def _merge_skills(
    records: list[IntermediateRecord],
    provenance: list[Provenance],
) -> list[Skill]:
    """Merge skills across sources into Skill objects with source tracking."""
    skill_map: dict[str, Skill] = {}  # canonical lowercase name → Skill

    for record in records:
        for skill_name in record.skills:
            key = skill_name.lower()
            if key in skill_map:
                # Skill already seen — add source
                existing = skill_map[key]
                if record.source_name not in existing.sources:
                    existing.sources.append(record.source_name)
            else:
                skill_map[key] = Skill(
                    name=skill_name,
                    confidence=0.0,  # Set by confidence stage
                    sources=[record.source_name],
                )

    if skill_map:
        provenance.append(Provenance(
            field="skills", source="multiple", method="merged-union-dedup",
        ))

    return list(skill_map.values())


def _merge_experience(
    records: list[IntermediateRecord],
    provenance: list[Provenance],
) -> list[Experience]:
    """Collect all experience entries, deduplicate by fuzzy company/title/date match."""
    result: list[Experience] = []

    for record in records:
        for exp in record.experience:
            c_comp = (exp.company or "").lower().strip()
            c_title = (exp.title or "").lower().strip()
            
            is_duplicate = False
            for existing in result:
                e_comp = (existing.company or "").lower().strip()
                e_title = (existing.title or "").lower().strip()
                
                if not c_comp or not e_comp:
                    continue
                
                # Check company match (substring)
                if c_comp in e_comp or e_comp in c_comp:
                    # Check title match (shared words)
                    c_words = set(c_title.split())
                    e_words = set(e_title.split())
                    title_match = bool(c_words & e_words)
                    
                    # Check date match
                    date_match = (exp.start and existing.start and exp.start == existing.start)
                    
                    if title_match or date_match:
                        is_duplicate = True
                        
                        # Merge missing fields
                        if not existing.start and exp.start:
                            existing.start = exp.start
                        if not existing.end and exp.end:
                            existing.end = exp.end
                        if not existing.summary and exp.summary:
                            existing.summary = exp.summary
                            
                        # Upgrade to longer title/company names
                        if len(exp.title or "") > len(existing.title or ""):
                            existing.title = exp.title
                        if len(exp.company or "") > len(existing.company or ""):
                            existing.company = exp.company
                            
                        break

            if not is_duplicate:
                result.append(exp)
                provenance.append(Provenance(
                    field="experience",
                    source=record.source_name,
                    method="merged-collected",
                ))

    # Sort by start date descending (most recent first)
    result.sort(key=lambda e: e.start or "0000-00", reverse=True)
    return result


def _merge_education(
    records: list[IntermediateRecord],
    provenance: list[Provenance],
) -> list[Education]:
    """Collect all education entries, deduplicate by (institution, degree)."""
    seen: set[tuple[str | None, str | None]] = set()
    result: list[Education] = []

    for record in records:
        for edu in record.education:
            key = (
                (edu.institution or "").lower().strip(),
                (edu.degree or "").lower().strip(),
            )
            if key not in seen:
                seen.add(key)
                result.append(edu)
                provenance.append(Provenance(
                    field="education",
                    source=record.source_name,
                    method="merged-collected",
                ))

    # Sort by end_year descending (most recent first)
    result.sort(key=lambda e: e.end_year or 0, reverse=True)
    return result


def _generate_candidate_id(emails: list[str], full_name: str | None) -> str:
    """Generate a deterministic candidate ID from identity signals.

    Same emails + name always produce the same ID.
    """
    seed = "|".join(sorted(e.lower() for e in emails))
    if not seed and full_name:
        seed = full_name.strip().lower()
    if not seed:
        seed = "unknown"

    return hashlib.sha256(seed.encode()).hexdigest()[:12]
