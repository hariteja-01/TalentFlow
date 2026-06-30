"""Runtime output configuration — controls what the pipeline emits.

The projection layer uses this config to reshape the canonical profile
into whatever the caller needs. Same engine, no code changes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class FieldConfig(BaseModel):
    """Configuration for a single output field.

    Attributes:
        path: The name this field appears as in the output.
        from_path: Canonical path to read from (e.g. "emails[0]", "skills[].name").
                   Defaults to ``path`` if not set.
        type: Expected output type ("string", "string[]", "number", "object").
        required: If True and value is missing, ``on_missing`` policy applies.
        normalize: Optional normalization to apply ("E164", "canonical", etc.).
    """

    path: str
    from_path: str | None = Field(None, alias="from")
    type: str = "string"
    required: bool = False
    normalize: str | None = None

    # Allow both "from" (JSON alias) and "from_path" (Python attribute)
    model_config = {"populate_by_name": True}


class OutputConfig(BaseModel):
    """Configuration schema for runtime output projection and field selection.

    Attributes:
        fields: List of field specifications for the output.
        include_confidence: Whether to include overall_confidence in output.
        on_missing: Policy for missing required values: "null", "omit", or "error".
    """

    fields: list[FieldConfig] = Field(default_factory=list)
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: str = "null"

    @field_validator("on_missing")
    @classmethod
    def validate_on_missing(cls, v: str) -> str:
        allowed = {"null", "omit", "error"}
        if v not in allowed:
            raise ValueError(f"on_missing must be one of {allowed}, got '{v}'")
        return v
