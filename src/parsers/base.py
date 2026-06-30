"""Abstract base class for source parsers.

Every parser must produce a list of IntermediateRecord objects from raw
file content. This contract lets the pipeline treat all sources uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.models.intermediate import IntermediateRecord


class BaseParser(ABC):
    """Interface that all source parsers implement."""

    @abstractmethod
    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Parse a source file into intermediate records.

        Args:
            file_path: Path to the source file.

        Returns:
            List of IntermediateRecord objects extracted from the file.
            Returns an empty list if the file is empty or unparseable.

        Raises:
            Never — parsers must handle errors gracefully and return
            partial results or an empty list.
        """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Identifier for this source type (e.g. 'json', 'csv', 'resume')."""
