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
) -> list[IntermediateRecord]:
    """Parse all source files into IntermediateRecords.

    Args:
        files: List of (file_path, source_type) from the ingestion stage.

    Returns:
        Flat list of all extracted IntermediateRecords.
        Failed files are skipped (logged), never crash the pipeline.
    """
    all_records: list[IntermediateRecord] = []

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
        except Exception as e:
            # Safety net — parsers should handle their own errors,
            # but we never let one bad file crash the whole pipeline
            logger.error("Unexpected error parsing %s: %s", file_path, e)
            continue

    logger.info("Extracted %d total records from %d files", len(all_records), len(files))
    return all_records
