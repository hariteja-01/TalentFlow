"""Stage 1: Ingestion — reads source files and detects their format.

This is the pipeline's entry point. It discovers files, detects their format,
and hands them to the correct parser.
"""

from __future__ import annotations

from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Supported file extensions mapped to source type
_EXTENSION_MAP: dict[str, str] = {
    ".json": "json",
    ".csv": "csv",
    ".txt": "resume",
    ".pdf": "resume",
    ".docx": "resume",
}


def detect_source_type(file_path: Path) -> str | None:
    """Detect the source type from a file's extension.

    Returns:
        Source type string ("json", "csv", "resume", "github"), or None if unsupported.
    """
    ext = file_path.suffix.lower()
    source_type = _EXTENSION_MAP.get(ext)

    # Special handling for text files: might be a resume or github urls
    if source_type == "resume" and ext == ".txt":
        try:
            content = file_path.read_text(encoding="utf-8").lower()
            if "github.com/" in content:
                source_type = "github"
        except Exception:
            pass  # Fall back to resume if unreadable

    if source_type is None:
        logger.warning("Unsupported file extension '%s' for %s", ext, file_path)

    return source_type


def discover_files(input_paths: list[Path]) -> list[tuple[Path, str]]:
    """Resolve input paths to (file, source_type) pairs.

    Handles both individual files and directories (scanned recursively).

    Args:
        input_paths: List of file or directory paths.

    Returns:
        List of (file_path, source_type) tuples for supported files.
    """
    results: list[tuple[Path, str]] = []

    for path in input_paths:
        if not path.exists():
            logger.warning("Input path does not exist: %s", path)
            continue

        if path.is_file():
            source_type = detect_source_type(path)
            if source_type:
                results.append((path, source_type))
        elif path.is_dir():
            # Recursively scan directory for supported files
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    source_type = detect_source_type(child)
                    if source_type:
                        results.append((child, source_type))

    logger.info("Discovered %d source files", len(results))
    return results
