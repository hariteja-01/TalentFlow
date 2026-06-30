"""Pipeline orchestrator — wires all stages together.

This is the single entry point for running the full pipeline.
Each stage is called in sequence, with error boundaries between them.

Pipeline flow:
    Input files → Ingest → Parse → Normalize → Merge → Score → [Project] → Validate → Output
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.canonical import CanonicalProfile
from src.models.config import FieldConfig, OutputConfig
from src.pipeline.stages.confidence import score_confidence
from src.pipeline.stages.extraction import extract_records
from src.pipeline.stages.ingestion import discover_files
from src.pipeline.stages.merging import merge_records
from src.pipeline.stages.normalization import normalize_all
from src.pipeline.stages.projection import ProjectionError, project_profile
from src.pipeline.stages.validation import validate_canonical, validate_projected
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineResult:
    """Container for pipeline output — holds both canonical and projected forms."""

    def __init__(
        self,
        profiles: list[CanonicalProfile],
        projected: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
        config_used: OutputConfig | None = None,
    ):
        self.profiles = profiles
        self.projected = projected
        self.warnings = warnings or []
        self.config_used = config_used

    def to_json(self, indent: int = 2) -> str:
        """Serialize the output to JSON.

        Uses projected output if a config was applied, otherwise canonical.
        """
        if self.projected is not None:
            data = self.projected
        else:
            data = [p.model_dump(mode="json") for p in self.profiles]

        return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def run_pipeline(
    input_paths: list[Path],
    config: OutputConfig | None = None,
) -> PipelineResult:
    """Run the full transformation pipeline.

    Args:
        input_paths: Paths to source files or directories.
        config: Optional runtime output configuration. If None, emits
                the full canonical schema.

    Returns:
        PipelineResult containing the transformed profiles.
    """
    all_warnings: list[str] = []

    # --- Stage 1: Ingest ---
    logger.info("=== Stage 1: Ingestion ===")
    files = discover_files(input_paths)
    if not files:
        logger.warning("No valid source files found")
        return PipelineResult(profiles=[], warnings=["No valid source files found"])

    # --- Stage 2: Extract ---
    logger.info("=== Stage 2: Extraction ===")
    records, ext_warnings = extract_records(files)
    all_warnings.extend(ext_warnings)
    if not records:
        logger.warning("No records extracted from any source")
        return PipelineResult(profiles=[], warnings=all_warnings)

    # --- Stage 3: Normalize ---
    logger.info("=== Stage 3: Normalization ===")
    normalized = normalize_all(records)

    # --- Stage 4: Merge ---
    logger.info("=== Stage 4: Merging ===")
    profiles = merge_records(normalized)

    # --- Stage 5: Score confidence ---
    logger.info("=== Stage 5: Confidence scoring ===")
    scored_profiles = [score_confidence(p) for p in profiles]

    # --- Stage 6: Validate canonical ---
    logger.info("=== Stage 6: Validation (canonical) ===")
    for profile in scored_profiles:
        warnings = validate_canonical(profile)
        all_warnings.extend(warnings)

    # --- Stage 7: Project (if config provided) ---
    projected = None
    if config and config.fields:
        logger.info("=== Stage 7: Projection ===")
        projected = []
        for profile in scored_profiles:
            try:
                proj = project_profile(profile, config)
                # Validate projected output
                proj_warnings = validate_projected(
                    proj,
                    [f.model_dump(by_alias=True) for f in config.fields],
                )
                all_warnings.extend(proj_warnings)
                projected.append(proj)
            except ProjectionError as e:
                logger.error("Projection failed for %s: %s", profile.candidate_id, e)
                all_warnings.append(str(e))

    logger.info(
        "Pipeline complete: %d profiles, %d warnings",
        len(scored_profiles), len(all_warnings),
    )

    return PipelineResult(
        profiles=scored_profiles,
        projected=projected,
        warnings=all_warnings,
        config_used=config,
    )


def load_config(config_path: Path) -> OutputConfig | None:
    """Load an output configuration from a JSON file.

    Returns None if the file doesn't exist or is invalid.
    """
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return None

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load config from %s: %s", config_path, e)
        return None

    # Parse the config — handle the mixed-type "fields" array
    fields = []
    for item in raw.get("fields", []):
        if isinstance(item, dict):
            fields.append(FieldConfig(**item))
        # Skip non-dict entries (like the bare "1" in the example config)

    return OutputConfig(
        fields=fields,
        include_confidence=raw.get("include_confidence", raw.get("include confidence", True)),
        on_missing=raw.get("on_missing", "null"),
    )
