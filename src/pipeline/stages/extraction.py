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
    import concurrent.futures

    all_records: list[IntermediateRecord] = []
    warnings: list[str] = []

    def _parse_single(file_path: Path, source_type: str) -> tuple[list[IntermediateRecord] | None, str | None]:
        parser = _PARSERS.get(source_type)
        if parser is None:
            return None, f"No parser registered for source type '{source_type}'"

        try:
            records = parser.parse(file_path)
            logger.debug("Extracted %d records from %s (%s)", len(records), file_path.name, source_type)
            return records, None
        except ValueError as e:
            return None, f"Failed to parse {file_path.name}: {e}"
        except Exception as e:
            return None, f"Unexpected error parsing {file_path.name}: {e}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_file = {
            executor.submit(_parse_single, file_path, source_type): file_path
            for file_path, source_type in files
        }

        for future in concurrent.futures.as_completed(future_to_file):
            records, warning = future.result()
            if records:
                all_records.extend(records)
            if warning:
                logger.error(warning)
                warnings.append(warning)

    logger.info("Extracted %d total records from %d files", len(all_records), len(files))
    return all_records, warnings
