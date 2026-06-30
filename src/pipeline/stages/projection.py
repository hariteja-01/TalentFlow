"""Stage 6: Projection — reshapes the canonical profile based on runtime config.

This is the key to "configurable output, no code changes":
  1. Select only the fields requested in the config
  2. Remap paths (e.g. "emails[0]" → first email)
  3. Rename fields (canonical path exposed under a custom name)
  4. Apply per-field normalization toggles
  5. Handle missing values per on_missing policy
  6. Optionally include/exclude confidence
"""

from __future__ import annotations

import re
from typing import Any

from src.models.canonical import CanonicalProfile
from src.models.config import FieldConfig, OutputConfig
from src.normalizers.phone import normalize_phone
from src.normalizers.skills import canonicalize_skill
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProjectionError(Exception):
    """Raised when a required field is missing and on_missing is 'error'."""


def project_profile(
    profile: CanonicalProfile,
    config: OutputConfig,
) -> dict[str, Any]:
    """Project a canonical profile into the shape defined by the config.

    Args:
        profile: The full canonical profile.
        config: Runtime output configuration.

    Returns:
        Dict matching the requested output shape.

    Raises:
        ProjectionError: If a required field is missing and on_missing="error".
    """
    # Convert profile to a nested dict for path resolution
    profile_dict = profile.model_dump()
    output: dict[str, Any] = {}

    for field_cfg in config.fields:
        # Resolve the source path (use "from" if specified, else "path")
        source_path = field_cfg.from_path or field_cfg.path
        output_key = field_cfg.path

        # Extract value from the profile dict
        value = _resolve_path(profile_dict, source_path)

        # Apply per-field normalization if specified
        if value is not None and field_cfg.normalize:
            value = _apply_normalization(value, field_cfg.normalize)

        # Handle missing values
        if value is None or (isinstance(value, list) and len(value) == 0):
            if field_cfg.required:
                if config.on_missing == "error":
                    raise ProjectionError(
                        f"Required field '{output_key}' (from '{source_path}') is missing"
                    )
                elif config.on_missing == "omit":
                    continue
                else:  # "null"
                    output[output_key] = None
            else:
                if config.on_missing == "omit":
                    continue
                else:
                    output[output_key] = None
        else:
            # Type coercion
            output[output_key] = _coerce_type(value, field_cfg.type)

    # Optionally include confidence
    if config.include_confidence:
        output["overall_confidence"] = profile.overall_confidence

    return output


def _resolve_path(data: dict[str, Any], path: str) -> Any:
    """Resolve a dot/bracket path against a nested dict.

    Supported path syntax:
        - "field"           → data["field"]
        - "field[0]"        → data["field"][0]
        - "field[].subfield" → [item["subfield"] for item in data["field"]]
        - "field.subfield"  → data["field"]["subfield"]

    Returns None if any part of the path is missing.
    """
    if not path:
        return None

    try:
        return _resolve_path_recursive(data, path)
    except (KeyError, IndexError, TypeError):
        return None


def _resolve_path_recursive(data: Any, path: str) -> Any:
    """Recursive path resolution with support for [] array access."""
    if not path:
        return data

    # Handle array spread: "field[].subfield"
    spread_match = re.match(r"^(\w+)\[\]\.(.+)$", path)
    if spread_match:
        field_name = spread_match.group(1)
        rest = spread_match.group(2)
        arr = data.get(field_name, []) if isinstance(data, dict) else []
        if not isinstance(arr, list):
            return None
        return [_resolve_path_recursive(item, rest) for item in arr]

    # Handle array index: "field[0]"
    index_match = re.match(r"^(\w+)\[(\d+)\](?:\.(.+))?$", path)
    if index_match:
        field_name = index_match.group(1)
        index = int(index_match.group(2))
        rest = index_match.group(3)
        arr = data.get(field_name, []) if isinstance(data, dict) else []
        if not isinstance(arr, list) or index >= len(arr):
            return None
        item = arr[index]
        if rest:
            return _resolve_path_recursive(item, rest)
        return item

    # Handle dot notation: "field.subfield"
    dot_match = re.match(r"^(\w+)\.(.+)$", path)
    if dot_match:
        field_name = dot_match.group(1)
        rest = dot_match.group(2)
        child = data.get(field_name) if isinstance(data, dict) else None
        if child is None:
            return None
        return _resolve_path_recursive(child, rest)

    # Simple field access
    if isinstance(data, dict):
        return data.get(path)
    return None


def _apply_normalization(value: Any, normalize: str) -> Any:
    """Apply a named normalization to a value."""
    normalize_upper = normalize.upper()

    if normalize_upper == "E164":
        if isinstance(value, str):
            return normalize_phone(value) or value
        elif isinstance(value, list):
            return [normalize_phone(str(v)) or v for v in value]

    elif normalize_upper == "CANONICAL":
        if isinstance(value, str):
            return canonicalize_skill(value)
        elif isinstance(value, list):
            return [canonicalize_skill(str(v)) for v in value]

    # Unknown normalization — pass through with warning
    logger.warning("Unknown normalization '%s', passing value through", normalize)
    return value


def _coerce_type(value: Any, target_type: str) -> Any:
    """Coerce a value to the target type specified in the config."""
    if target_type == "string":
        if isinstance(value, list):
            return str(value[0]) if value else None
        return str(value) if value is not None else None

    elif target_type == "string[]":
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)] if value is not None else []

    elif target_type == "number":
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    elif target_type == "object":
        return value  # Already a dict or complex type

    # Unknown type — pass through
    return value
