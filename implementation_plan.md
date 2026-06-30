# Implementation Plan

## 1. Fix Duplicate Profile Bug
The user reports that the web interface shows every candidate profile TWICE. 
**Diagnosis**:
- I will add `console.log` statements in `script.js` to track the `profiles` array length.
- I will check if `renderProfiles` is iterating twice, or if `result.profiles` from the backend actually contains duplicates.
- The likely culprit is the way `_group_by_identity` forms groups and how it handles Union-Find. If records don't overlap properly, they could form duplicate CanonicalProfiles. But the user says *every* candidate is duplicated. I will also check if `processFiles()` gets called twice (e.g. from both `drop` and `change` events firing).

## 2. Fix Multi-File Upload Bug
The user reports that only ONE file is being processed when multiple are uploaded.
**Diagnosis**:
- In `api/index.py`: `safe_filename = secure_filename(file.filename)`. If multiple files are uploaded without a filename, `secure_filename` returns `"unnamed_file"`, causing them to overwrite each other. I will ensure unique filenames in `api/index.py` by appending a UUID or counter to the temporary file path.

## 3. Implement GitHub API Parsing
**Implementation**:
- In `src/parsers/github_parser.py`, I will replace the current mocked or basic logic with full GitHub API integration using the `urllib.request` library (since we want to avoid extra dependencies if possible, or `requests` if it's in `requirements.txt`).
- `https://api.github.com/users/{username}` for name, bio, location, created_at, email, blog, public_repos.
- `https://api.github.com/users/{username}/repos` for analyzing top repositories to extract languages and infer skills from repository topics, names, and descriptions.

## 4. Intelligently Map GitHub Data to Canonical Schema
**Implementation**:
- name → full_name
- bio → headline
- location → location object
- blog → links.portfolio
- github URL → links.github
- languages from repos → skills array (name, confidence, sources=["github"])
- created_at → years_experience (current year - created_at year)
- public_repos count/activity → overall_confidence (this will be handled by the extraction and later scoring, but we can set `source_weight` or initial confidence).
- provenance → method "github-api".

## 5. Enhance with Repository Analysis
**Implementation**:
- Iterate over top repos (by stars/pushed_at).
- Extract `language`, `description`, `topics`.
- Look for keywords like "django", "react" in names to add to skills.

## 6. Secondary README Scraping
**Implementation**:
- Keep the `_fetch_readme` logic I already implemented, but make sure it gracefully fails and merges its extracted emails/phones with the API data.

## 7. Edge Cases & Tests
**Implementation**:
- Handle 404, 403 (Rate limit), timeouts.
- Add/update tests in `tests/test_parsers_edge_cases.py`. Test with "octocat", "torvalds", "hariteja-01".

## 8. Commit and Push
- Run all tests.
- Commit sequentially with descriptive messages.
- Push to GitHub.

## User Feedback Required
- Please approve this plan. I will immediately implement these fixes and features upon approval!
