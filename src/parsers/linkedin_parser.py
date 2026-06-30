"""LinkedIn profile URL parser — extracts links from text files."""

from pathlib import Path

from src.models.canonical import Links
from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

class LinkedinParser(BaseParser):
    """Parses text files containing LinkedIn profile URLs."""

    @property
    def source_type(self) -> str:
        return "linkedin"

    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Extract profile URLs."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to read {file_path.name}: {e}")

        urls = [line.strip() for line in content.splitlines() if "linkedin.com/in/" in line.lower()]
        
        if not urls:
            raise ValueError(f"No LinkedIn URLs found in {file_path.name}")

        records = []
        for url in set(urls):
            # Extract basic name from URL slug (e.g., /in/janedoe -> Jane Doe)
            username = url.rstrip("/").split("/")[-1]
            # Heuristic: split by dashes, title case
            name_guess = " ".join(part.title() for part in username.split("-") if not part.isdigit())

            links = Links(
                linkedin=url,
                github=None,
                portfolio=None,
                other=[],
            )

            records.append(IntermediateRecord(
                source_name=file_path.name,
                source_type=self.source_type,
                source_weight=SOURCE_WEIGHTS.get(self.source_type, 0.4),
                full_name=name_guess if name_guess else None,
                emails=[],
                phones=[],
                location=None,
                links=links,
                headline=None,
                years_experience=None,
                skills=[],
                experience=[],
                education=[],
            ))

        return records
