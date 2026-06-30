"""GitHub profile URL parser — extracts candidate data via GitHub REST API."""

import json
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse

from src.models.canonical import Links, Location
from src.models.intermediate import IntermediateRecord
from src.parsers.base import BaseParser
from src.parsers.resume_parser import _EMAIL_RE, _PHONE_RE
from src.utils.constants import SOURCE_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

class GithubParser(BaseParser):
    """Parses text files containing GitHub profile URLs."""

    @property
    def source_type(self) -> str:
        return "github"

    def parse(self, file_path: Path) -> list[IntermediateRecord]:
        """Extract profile URLs and fetch data from GitHub API."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to read {file_path.name}: {e}")

        import re
        github_url_re = re.compile(r'https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+')
        
        urls = []
        for line in content.splitlines():
            matches = github_url_re.findall(line)
            urls.extend(matches)
        
        if not urls:
            raise ValueError(f"No GitHub URLs found in {file_path.name}")

        records = []
        for url in set(urls):
            username = self._extract_username(url)
            if not username:
                logger.warning("Could not extract GitHub username from URL: %s", url)
                continue

            record = self._fetch_profile(username, url, file_path.name)
            if record:
                records.append(record)

        if not records:
            raise ValueError(f"Could not extract any profiles from URLs in {file_path.name}")

        return records

    def _extract_username(self, url: str) -> str | None:
        """Extract the username from a github.com URL."""
        if not url.startswith("http"):
            url = "https://" + url
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            if not path:
                return None
            return path.split("/")[0]
        except Exception:
            return None

    def _fetch_profile(self, username: str, original_url: str, source_name: str) -> IntermediateRecord | None:
        """Fetch user data from GitHub REST API."""
        api_url = f"https://api.github.com/users/{username}"
        headers = {"User-Agent": "TalentFlow-Transformer"}

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Attempt to fetch top languages and topics as skills
            skills = self._fetch_skills(username, headers)

            # Parse location
            location = None
            loc_str = data.get("location")
            if loc_str:
                parts = [p.strip() for p in loc_str.split(",")]
                if len(parts) >= 3:
                    location = Location(city=parts[0], region=parts[1], country=parts[2])
                elif len(parts) == 2:
                    location = Location(city=parts[0], region=parts[1])
                else:
                    location = Location(city=parts[0])

            # Parse emails
            emails = []
            if data.get("email"):
                emails.append(data["email"])

            phones = []
            
            # Scrape README.md for contact info
            readme_text = self._fetch_readme(username, headers)
            if readme_text:
                found_emails = _EMAIL_RE.findall(readme_text)
                for em in found_emails:
                    if em not in emails:
                        emails.append(em)
                        
                found_phones = _PHONE_RE.findall(readme_text)
                for ph in found_phones:
                    # Basic cleanup
                    clean_ph = "".join(c for c in ph if c.isdigit() or c == "+")
                    if len(clean_ph) >= 10 and clean_ph not in phones:
                        phones.append(clean_ph)

            # Fetch social accounts to find linkedin
            linkedin_url = None
            try:
                social_req = urllib.request.Request(f"https://api.github.com/users/{username}/social_accounts", headers=headers)
                with urllib.request.urlopen(social_req, timeout=3) as social_resp:
                    social_data = json.loads(social_resp.read().decode())
                    for acc in social_data:
                        provider = acc.get("provider", "").lower()
                        url = acc.get("url", "")
                        if provider == "linkedin" or "linkedin.com" in url.lower():
                            linkedin_url = url
                            break
            except Exception:
                pass

            # Fallback to scrape the HTML profile page directly if API social_accounts fails or doesn't have it
            if not linkedin_url:
                try:
                    html_req = urllib.request.Request(f"https://github.com/{username}", headers=headers)
                    with urllib.request.urlopen(html_req, timeout=3) as html_resp:
                        html_text = html_resp.read().decode('utf-8', errors='ignore')
                        # Look for linkedin.com links
                        import re
                        li_match = re.search(r'href="([^"]*linkedin\.com/[^"]+)"', html_text)
                        if li_match:
                            linkedin_url = li_match.group(1)
                except Exception:
                    pass
            
            # Final fallback: Check if company field contains a LinkedIn path like "company/xyz"
            if not linkedin_url:
                company = (data.get("company") or "").strip()
                if company.startswith("company/") or company.startswith("in/"):
                    linkedin_url = f"https://www.linkedin.com/{company}"

            links = Links(
                linkedin=linkedin_url,
                github=original_url,
                portfolio=data.get("blog") if data.get("blog") else None,
                other=[],
            )
            
            # Parse account age as years_experience
            years_experience = None
            created_at = data.get("created_at")
            if created_at:
                try:
                    import datetime
                    # Extract year
                    created_year = int(created_at[:4])
                    current_year = datetime.datetime.now().year
                    years_experience = max(0.0, float(current_year - created_year))
                except Exception:
                    pass

            return IntermediateRecord(
                source_name=source_name,
                source_type=self.source_type,
                source_weight=SOURCE_WEIGHTS.get(self.source_type, 0.4),
                full_name=data.get("name") or data.get("login"),
                emails=emails,
                phones=phones,
                location=location,
                links=links,
                headline=data.get("bio"),
                years_experience=years_experience,
                skills=skills,
                experience=[],
                education=[],
            )

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.warning("GitHub user not found: %s", username)
            elif e.code == 403:
                logger.warning("GitHub API rate limit exceeded for user: %s", username)
            else:
                logger.warning("GitHub API HTTP error %s for user: %s", e.code, username)
        except urllib.error.URLError as e:
            logger.warning("GitHub API network error for user %s: %s", username, e.reason)
        except Exception as e:
            logger.error("Unexpected error fetching GitHub profile for %s: %s", username, e)
            
        # Return a partial profile with just the URL on failure
        return IntermediateRecord(
            source_name=source_name,
            source_type=self.source_type,
            source_weight=SOURCE_WEIGHTS.get(self.source_type, 0.4),
            full_name=username,
            emails=[],
            phones=[],
            location=None,
            links=Links(github=original_url, portfolio=None, other=[]),
            headline=None,
            years_experience=None,
            skills=[],
            experience=[],
            education=[],
        )

    def _fetch_readme(self, username: str, headers: dict) -> str | None:
        """Attempt to fetch the user's profile README.md."""
        urls = [
            f"https://raw.githubusercontent.com/{username}/{username}/main/README.md",
            f"https://raw.githubusercontent.com/{username}/{username}/master/README.md"
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=3) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                logger.debug("HTTP %s fetching README for %s", e.code, username)
            except Exception as e:
                logger.debug("Error fetching README for %s: %s", username, e)
        return None

    def _fetch_skills(self, username: str, headers: dict) -> list[str]:
        """Fetch a user's repositories and extract their languages and topics to use as skills."""
        api_url = f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=15"
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                repos = json.loads(response.read().decode())
                
            skills = set()
            for repo in repos:
                # Add Primary Language
                if repo.get("language"):
                    skills.add(repo["language"])
                
                # Add Repository Topics
                topics = repo.get("topics") or []
                for topic in topics:
                    skills.add(topic)
                    
                # Search Description for common skills
                description = (repo.get("description") or "").lower()
                common_skills = ["react", "node", "django", "flask", "kubernetes", "docker", "aws", "gcp", "azure", "tensorflow", "pytorch"]
                for cs in common_skills:
                    if cs in description:
                        skills.add(cs)
                        
            return list(skills)
        except Exception as e:
            logger.debug("Could not fetch repo skills for %s: %s", username, e)
            return []
