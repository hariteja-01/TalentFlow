"""Stage 2: Extraction — dispatches files to the correct parser.

Each parser returns IntermediateRecords. Errors in one source
never crash the pipeline — we log and continue.
"""

from __future__ import annotations

from pathlib import Path

from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.parsers.csv_parser import CsvParser
from src.parsers.json_parser import JsonParser
from src.parsers.resume_parser import ResumeParser
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Parser registry — maps source type to parser instance
_PARSERS: dict[str, BaseParser] = {
    "json": JsonParser(),
    "csv": CsvParser(),
    "resume": ResumeParser(),
}


def extract_records(
    files: list[tuple[Path, str]],
) -> tuple[list[IntermediateRecord], list[str]]:
    """Parse all source files into IntermediateRecords.

    Args:
        files: List of (file_path, source_type) from the ingestion stage.

    Returns:
        Tuple of (records, warnings).
        Failed files are skipped, never crash the pipeline, but produce a warning.
    """
    all_records: list[IntermediateRecord] = []
    warnings: list[str] = []

    for file_path, source_type in files:
        parser = _PARSERS.get(source_type)
        if parser is None:
            logger.error("No parser registered for source type '%s'", source_type)
            continue

        try:
            records = parser.parse(file_path)
            all_records.extend(records)
            logger.debug(
                "Extracted %d records from %s (%s)", len(records), file_path.name, source_type
            )
        except ValueError as e:
            msg = f"Failed to parse {file_path.name}: {e}"
            logger.error(msg)
            warnings.append(msg)
            continue
        except Exception as e:
            msg = f"Unexpected error parsing {file_path.name}: {e}"
            logger.error(msg)
            warnings.append(msg)
            continue

    logger.info("Extracted %d total records from %d files", len(all_records), len(files))
    return all_records, warnings
