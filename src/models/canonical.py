"""Canonical profile schema — the single source of truth for a candidate.

Every field has a fixed type and normalization format. The pipeline's job
is to fill this schema from messy inputs, never inventing data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Geographic location with ISO-3166 alpha-2 country code."""

    city: str | None = None
    region: str | None = None
    country: str | None = None  # ISO-3166 alpha-2 (e.g. "US", "IN")


class Links(BaseModel):
    """Web presence links for a candidate."""

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    """A canonicalized skill with confidence and source tracking."""

    name: str
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    """A single work experience entry with normalized dates."""

    company: str | None = None
    title: str | None = None
    start: str | None = None  # YYYY-MM format
    end: str | None = None  # YYYY-MM format, None means "present"
    summary: str | None = None


class Education(BaseModel):
    """A single education entry."""

    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    end_year: int | None = None


class Provenance(BaseModel):
    """Tracks where a field value came from and how it was derived.

    This is how we keep the pipeline explainable — every value
    is traceable to a source and extraction method.
    """

    field: str
    source: str
    method: str  # e.g. "parsed", "normalized", "merged-highest-weight"


class CanonicalProfile(BaseModel):
    """The final, merged, normalized candidate profile.

    This is the pipeline's output. Every field follows a fixed format.
    Unknown values are None, never invented.
    """

    candidate_id: str
    full_name: str = ""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location | None = None
    links: Links | None = None
    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    overall_confidence: float = 0.0
