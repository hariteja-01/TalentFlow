"""Intermediate record — the uniform shape every parser outputs before merging.

Parsers extract raw data into this format. It deliberately uses simple types
(plain strings for skills, un-normalized phones) because normalization
happens in a later pipeline stage.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.canonical import Education, Experience, Links, Location


class IntermediateRecord(BaseModel):
    """One candidate record extracted from a single source.

    Multiple IntermediateRecords may refer to the same person.
    The merge stage groups them by identity and resolves conflicts.
    """

    # Source metadata — used for provenance and confidence weighting
    source_name: str  # filename or identifier (e.g. "candidate_api.json")
    source_type: str  # "json", "csv", or "resume"
    source_weight: float = 0.5  # reliability weight, set by parser

    # Candidate fields — all optional because any source may be partial
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)  # raw, not yet E.164
    location: Location | None = None
    links: Links | None = None
    headline: str | None = None
    years_experience: float | None = None
    skills: list[str] = Field(default_factory=list)  # raw names, not canonical
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
