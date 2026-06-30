"""Plain-text resume parser — extracts candidate data via regex heuristics.

This parser uses deterministic regex patterns rather than ML models, ensuring
consistent outputs without requiring API keys or heavy dependencies. It works
by identifying sections (EXPERIENCE, EDUCATION, SKILLS) and applying targeted
extraction patterns within each logical block.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from src.models.canonical import Education, Experience, Links, Location
from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

# --- Regex patterns for field extraction ---

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", re.IGNORECASE)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+/?", re.IGNORECASE)
_PORTFOLIO_RE = re.compile(
    r"(?<![\w@.-])(?:https?://)?(?:www\.)?(?:[\w-]+\.)+(?:com|io|dev|me|org|net|app|co)/?\S*", re.IGNORECASE
)

# Shared skill subheaders
_SUBHEADERS = frozenset({
    "languages", "frameworks", "libraries", "tools", "platforms", 
    "databases", "core concepts", "operating systems", "technologies", 
    "methodologies", "frameworks & libraries", "tools & platforms", 
    "big data & databases", "technical skills", "skills", "soft skills"
})

_EXT_DEGREE_RE = re.compile(
    r"\b(?P<degree>B\.?Tech|M\.?Tech|B\.?E\.?|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|"
    r"Bachelor(?:'?s)?|Master(?:'?s)?|Doctorate|Intermediate|Matriculation|Diploma|High\s*School)\b"
    r"(?:\s*(?:\(.*?\)))?"
    r"(?:\s+(?:of|in)\s+(?P<field>[\w\s&,]+))?",
    re.IGNORECASE
)

# Section headers — used to split the resume into logical blocks
_SECTION_RE = re.compile(
    r"^(?:[-—=*\s]*)("
    r"experience|work\s*experience|professional\s*experience|employment|"
    r"education|academic|qualifications|"
    r"skills|technical\s*skills|core\s*competencies|technologies|"
    r"summary|profile|objective|about|"
    r"projects|certifications|honors|awards|achievements|publications"
    r")(?:[-—=*:\s]*)$",
    re.IGNORECASE | re.MULTILINE,
)

# Experience entry: "Title at Company" or "Company — Title" followed by dates
_EXP_ENTRY_RE = re.compile(
    r"(?P<title>[A-Z][A-Za-z\s/]+?)\s+(?:at|@|-|–|—)\s+(?P<company>[A-Z][\w\s&.,]+?)$",
    re.MULTILINE,
)
_EXP_ENTRY_REV_RE = re.compile(
    r"(?P<company>[A-Z][\w\s&.,]+?)\s+(?:-|–|—)\s+(?P<title>[A-Z][A-Za-z\s/]+?)$",
    re.MULTILINE,
)

# Date range: "Jan 2020 - Present", "2018-06 to 2020-01", "June 2017 – Dec 2019"
_DATE_RANGE_RE = re.compile(
    r"(?P<start>"
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+)?\d{4}(?:-\d{2})?)"
    r"\s*(?:to|-|–|—)\s*"
    r"(?P<end>(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+)?\d{4}(?:-\d{2})?|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.IGNORECASE,
)

# Education: degree, field, institution patterns
_DEGREE_RE = re.compile(
    r"(?P<degree>(?:B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|"
    r"Bachelor(?:'?s)?|Master(?:'?s)?|Doctorate|Associate(?:'?s)?)"
    r"(?:\s+(?:of|in)\s+(?P<field>[\w\s]+?))?)"
    r"(?:\s*(?:,|from|-|–|—|at)\s*(?P<institution>[\w\s]+?))?$",
    re.IGNORECASE | re.MULTILINE,
)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Location: "City, State", "City, State, Country", or "City, State, Country, Zipcode"
_LOCATION_LINE_RE = re.compile(
    r"^(?P<city>[a-zA-Z \t]+?),\s*"
    r"(?P<region>[a-zA-Z \t]+?)(?:,\s*(?P<country>[a-zA-Z \t]+?))?(?:,\s*(?P<zip>\d{4,}))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class ResumeParser(BaseParser):
    """Extracts candidate data from plain-text resumes using regex heuristics."""

    @property
    def source_type(self) -> str:
        return "resume"

    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Parse a resume file (.txt, .pdf, .docx)."""
        ext = file_path.suffix.lower()
        text = ""
        
        try:
            if ext == ".pdf":
                import fitz
                with fitz.open(file_path) as doc:
                    text = "\n".join(page.get_text() for page in doc)
            elif ext == ".docx":
                import docx
                doc = docx.Document(file_path)
                text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
            else:
                try:
                    text = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = file_path.read_text(encoding="latin-1")
                    logger.warning("Used latin-1 fallback for %s", file_path)
        except Exception as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                raise ValueError(f"Encrypted PDF not supported: {file_path.name}")
            raise ValueError(f"Failed to read {file_path.name}: {e}")

        if not text.strip():
            if ext == ".pdf":
                raise ValueError(f"Image-only PDF detected (no machine-readable text found): {file_path.name}")
            raise ValueError(f"Empty document: {file_path.name}")

        record = self._extract_from_text(text, file_path)
        
        if not record.has_candidate_data():
            raise ValueError(f"File does not contain valid candidate data: {file_path.name}")
            
        logger.info("Parsed resume from %s", file_path.name)
        return [record]

    def _extract_from_text(self, text: str, file_path: Path) -> IntermediateRecord:
        """Extract all fields from resume text."""
        sections = self._split_sections(text)

        emails = list(dict.fromkeys(e.lower() for e in _EMAIL_RE.findall(text)))
        
        # Phone regex often over-matches numeric sequences (e.g. zip codes, IDs)
        # We filter out matches with fewer than 7 digits to reduce noise.
        phones = list(dict.fromkeys(_PHONE_RE.findall(text)))
        phones = [p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 7]

        name = self._extract_name(text)
        links = self._extract_links(text)
        location = self._extract_location(text)
        skills = self._extract_skills(sections.get("skills", ""), text)
        experience = self._extract_experience(sections.get("experience", ""))
        education = self._extract_education(sections.get("education", ""))
        headline = self._extract_headline(sections.get("summary", ""))
        yoe = self._estimate_yoe(experience)

        return IntermediateRecord(
            source_name=file_path.name,
            source_type=self.source_type,
            source_weight=SOURCE_WEIGHTS.get(self.source_type, 0.5),
            full_name=name,
            emails=emails,
            phones=phones,
            location=location,
            links=links,
            headline=headline,
            years_experience=yoe,
            skills=skills,
            experience=experience,
            education=education,
        )

    @staticmethod
    def _split_sections(text: str) -> dict[str, str]:
        """Split resume into named sections based on headers."""
        sections: dict[str, str] = {}
        matches = list(_SECTION_RE.finditer(text))

        for i, match in enumerate(matches):
            section_name = match.group(1).strip().lower()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            # Normalize section names
            if any(kw in section_name for kw in ("experience", "work", "employment")):
                sections["experience"] = content
            elif any(kw in section_name for kw in ("education", "academic", "qualification")):
                sections["education"] = content
            elif any(kw in section_name for kw in ("skill", "competenc", "technolog")):
                sections["skills"] = content
            elif any(kw in section_name for kw in ("summary", "profile", "objective", "about")):
                sections["summary"] = content

        return sections

    @staticmethod
    def _extract_name(text: str) -> str | None:
        """Extract candidate name from the first meaningful line."""
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Skip lines that look like headers, emails, phones, or URLs
            if "@" in line or "http" in line.lower() or "linkedin" in line.lower() or "github" in line.lower():
                continue
            if re.match(r"^[\d(+]", line):  # Starts with digit or phone prefix
                continue
            if "resume" in line.lower() or "cv" in line.lower() or "curriculum vitae" in line.lower():
                continue
            
            # Additional check: skip date lines or typical header lines
            if _DATE_RANGE_RE.search(line):
                continue
            
            # A name line is typically 1-5 words, mostly letters
            words = line.split()
            if 1 <= len(words) <= 5 and all(re.match(r"^[A-Za-zÀ-ÿ]+[-']?[A-Za-zÀ-ÿ]*$", w) for w in words):
                # Return proper cased name even if input was lowercase
                return " ".join(w.capitalize() for w in words)
        return None

    @staticmethod
    def _extract_links(text: str) -> Links | None:
        """Extract LinkedIn, GitHub, and portfolio links."""
        linkedin = _LINKEDIN_RE.search(text)
        github = _GITHUB_RE.search(text)

        # Find portfolio URLs (not LinkedIn or GitHub)
        portfolio = None
        for match in _PORTFOLIO_RE.finditer(text):
            url = match.group(0)
            # Exclude matches that are part of an email address
            # (check if preceded by @ in the original text)
            start_idx = match.start()
            if start_idx > 0 and text[start_idx - 1] == "@":
                continue
            if "linkedin.com" not in url.lower() and "github.com" not in url.lower():
                portfolio = url
                break

        if not any([linkedin, github, portfolio]):
            return None

        return Links(
            linkedin=linkedin.group(0) if linkedin else None,
            github=github.group(0) if github else None,
            portfolio=portfolio,
        )

    @staticmethod
    def _extract_location(text: str) -> Location | None:
        """Extract location from resume header area (first ~10 lines)."""
        header = "\n".join(text.strip().split("\n")[:10])
        match = _LOCATION_LINE_RE.search(header)
        if match:
            return Location(
                city=match.group("city").strip() if match.group("city") else None,
                region=match.group("region").strip() if match.group("region") else None,
                country=match.group("country").strip() if match.group("country") else None,
            )
        return None

    @staticmethod
    def _extract_skills(skills_section: str, full_text: str) -> list[str]:
        """Extract skills from the skills section or fall back to full text."""
        text = skills_section or full_text
        if not text.strip():
            return []

        # Skills are typically comma, pipe, or bullet-separated
        # First try to find a clear list
        skills = []
        for line in text.split("\n"):
            clean_line = line.strip().lower().rstrip(":")
            if clean_line in _SUBHEADERS:
                continue

            line = line.strip().lstrip("•·▪►-*|:")
            if not line:
                continue

            # Split by common delimiters
            for sep in [",", "|", "•", "·", ";"]:
                if sep in line:
                    parts = [s.strip() for s in line.split(sep) if s.strip()]
                    # Only treat as skill list if parts look like skill names (short)
                    if all(len(p.split()) <= 4 for p in parts):
                        skills.extend(parts)
                    break
            else:
                # Single skill per line (if short enough to be a skill name)
                if len(line.split()) <= 4 and len(line) < 50:
                    skills.append(line)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique = []
        for s in skills:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique

    @staticmethod
    def _extract_experience(exp_section: str) -> list[Experience]:
        """Extract work experience entries from the experience section."""
        if not exp_section.strip():
            return []

        entries: list[Experience] = []
        lines = exp_section.strip().split("\n")

        current_company = None
        current_title = None
        current_start = None
        current_end = None
        current_summary_lines: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for dates on the same line
            date_match = _DATE_RANGE_RE.search(line)
            # If the entire line is just a date range, it shouldn't be parsed as an experience entry
            is_only_date = bool(date_match and len(line) <= len(date_match.group(0)) + 5)
            
            exp_match = None
            if not is_only_date:
                exp_match = _EXP_ENTRY_RE.search(line) or _EXP_ENTRY_REV_RE.search(line)

            if exp_match:
                # Save previous entry if exists
                if current_company or current_title:
                    entries.append(Experience(
                        company=current_company,
                        title=current_title,
                        start=current_start,
                        end=current_end,
                        summary="\n".join(current_summary_lines) if current_summary_lines else None,
                    ))

                current_company = exp_match.group("company").strip().rstrip(",.")
                current_title = exp_match.group("title").strip().rstrip(",.")
                current_summary_lines = []

                # Check for dates on the same line
                if date_match:
                    current_start = date_match.group("start")
                    current_end = date_match.group("end")
                else:
                    current_start = None
                    current_end = None

            elif date_match and not exp_match:
                # Date line without title — applies to current entry
                current_start = date_match.group("start")
                current_end = date_match.group("end")

            elif line.startswith(("-", "•", "·", "▪", "►", "*")):
                # Bullet point — part of summary
                current_summary_lines.append(line.lstrip("-•·▪►* "))

        # Don't forget the last entry
        if current_company or current_title:
            entries.append(Experience(
                company=current_company,
                title=current_title,
                start=current_start,
                end=current_end,
                summary="\n".join(current_summary_lines) if current_summary_lines else None,
            ))

        return entries

    @staticmethod
    def _extract_education(edu_section: str) -> list[Education]:
        """Extract education entries."""
        if not edu_section.strip():
            return []

        entries: list[Education] = []
        lines = [line.strip() for line in edu_section.split("\n") if line.strip()]

        for i, line in enumerate(lines):
            match = _EXT_DEGREE_RE.search(line)
            if match:
                degree = match.group("degree").strip()
                field = match.group("field").strip() if match.group("field") else None

                # Check for year in this line or nearby
                end_year = None
                year_match = _YEAR_RE.search(line)
                if year_match:
                    end_year = int(year_match.group(0))
                elif i > 0:
                    year_match = _YEAR_RE.search(lines[i - 1])
                    if year_match:
                        end_year = int(year_match.group(0))

                # Look backwards for institution
                institution = None
                
                # Check current line first for comma separated like "Degree in Field, Institution, Year"
                if "," in line:
                    parts = [p.strip() for p in line.split(",")]
                    for part in parts:
                        if not _EXT_DEGREE_RE.search(part) and not _YEAR_RE.search(part):
                            institution = part
                            break

                if not institution:
                    for j in range(i - 1, -1, -1):
                        prev = lines[j]
                        if not prev or 'education' in prev.lower() or _YEAR_RE.search(prev) or ',' in prev:
                            continue
                        institution = prev
                        break

                # Avoid duplicate creation if we already parsed this institution in a simpler fallback
                entries.append(Education(
                    institution=institution,
                    degree=degree,
                    field=field,
                    end_year=end_year,
                ))

        # If regex didn't match anything, or missed some lines, try simpler line-by-line parsing
        # But ensure we don't duplicate existing entries.
        existing_institutions = {e.institution.lower() for e in entries if e.institution}
        
        for line in lines:
            if _EXT_DEGREE_RE.search(line):
                continue  # Already handled by regex approach
                
            year_match = _YEAR_RE.search(line)
            end_year = int(year_match.group(0)) if year_match else None
            if end_year or any(kw in line.lower() for kw in ("university", "college", "institute", "school")):
                inst = line.split(",")[0].strip() if "," in line else line
                # Only add if it doesn't overlap with what we found
                if inst.lower() not in existing_institutions:
                    entries.append(Education(
                        institution=inst,
                        end_year=end_year,
                    ))
                    existing_institutions.add(inst.lower())

        return entries

    @staticmethod
    def _extract_headline(summary_section: str) -> str | None:
        """Extract a headline from the summary section — first sentence or line."""
        if not summary_section.strip():
            return None
        first_line = summary_section.strip().split("\n")[0].strip()
        # Limit to reasonable headline length
        if len(first_line) > 200:
            first_line = first_line[:197] + "..."
        return first_line if first_line else None

    @staticmethod
    def _estimate_yoe(experience: list[Experience]) -> float | None:
        """Rough years-of-experience estimate from work history dates."""
        if not experience:
            return None

        total_months = 0
        for exp in experience:
            if not exp.start:
                continue

            try:
                start_parts = exp.start.split("-")
                start_year = int(start_parts[0]) if len(start_parts) >= 1 else None
                start_month = int(start_parts[1]) if len(start_parts) >= 2 else 1

                if exp.end and not re.match(r"(?i)present|current|now", exp.end):
                    end_parts = exp.end.split("-")
                    end_year = int(end_parts[0]) if len(end_parts) >= 1 else None
                    end_month = int(end_parts[1]) if len(end_parts) >= 2 else 1
                else:
                    now = datetime.date.today()
                    end_year = now.year
                    end_month = now.month

                if start_year and end_year:
                    months = (end_year - start_year) * 12 + (end_month - start_month)
                    total_months += max(0, months)
            except (ValueError, IndexError):
                continue

        return round(total_months / 12, 1) if total_months > 0 else None
