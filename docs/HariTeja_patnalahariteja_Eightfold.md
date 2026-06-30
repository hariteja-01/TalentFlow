# TalentFlow: Multi-Source Candidate Data Transformer
**Candidate:** Hari Teja | **Email:** patnalahariteja@gmail.com

## 1. Pipeline Architecture
The pipeline is designed as a modular, 6-stage DAG to ensure deterministic execution and clear separation of concerns:
1. **Ingestion (`detect`)**: Scans input files and identifies the source type (CSV, JSON ATS, PDF Resume, GitHub URLs) by applying structural heuristics. Files are read in deterministic alphabetical order.
2. **Extraction (`extract`)**: Source-specific parsers extract intermediate data. The `ResumeParser` heavily relies on regex and structural cues, prioritizing "honestly-empty over wrong-but-confident" by only extracting from designated sections.
3. **Normalization (`normalize`)**: Cleans extracted data (e.g., standardizing phones to E.164, parsing dates to YYYY-MM, mapping countries to ISO-3166 alpha-2).
4. **Identity & Merging (`merge`)**: Resolves candidate identity across sources. It uses a Union-Find algorithm based primarily on `emails`. When conflicts arise, data is merged field-by-field based on `source_weight`.
5. **Confidence Scoring (`score`)**: Evaluates the completeness, source reliability, and agreement across sources to emit granular confidence metrics.
6. **Projection (`validate & project`)**: Morphs the internal canonical record into a runtime-configurable JSON shape, handling missing values and omitting fields per user configuration.

## 2. Canonical Schema & Normalizations
The internal canonical schema provides a strict, typed structure (`pydantic.BaseModel`):
- `candidate_id` (UUID), `full_name` (String), `emails` (String Array)
- `phones` (String Array): **Normalized** via the `phonenumbers` library to strictly formatted E.164. Invalid sequences drop out.
- `location` (Object): `{city, region, country}`. **Normalized** by mapping country strings (e.g., "UK", "United States") to ISO-3166 alpha-2 ("GB", "US").
- `links` (Object): `{linkedin, github, portfolio, other[]}`.
- `experience`, `education` (Objects): Dates are **Normalized** into strict `YYYY-MM` formats using fuzzy parsing logic.
- `skills` (Array): **Normalized** against a canonical dictionary (e.g., "js" → "JavaScript").
- `provenance` (Array): Tracks `{field, source, method}` for every individual data point.

## 3. Merge / Conflict-Resolution Policy & Confidence
**Conflict Policy**: We rely on *Email-based Identity Resolution* followed by *Source Weighting*. 
When aggregating data for a candidate, sources are ranked by trustworthiness (ATS JSON [0.9] > CSV [0.7] > PDF Resume [0.65] > GitHub [0.4]). If multiple sources provide a conflicting scalar value (e.g., `headline`), the value from the highest-weight source strictly wins. Array fields (like `skills` or `emails`) are unioned and deduplicated.

**Confidence Formula**: 
`confidence(f) = source_weight × completeness × agreement_bonus`
- **Completeness**: Drops to 0.0 if the field is omitted/null/empty array.
- **Agreement Bonus**: 1.2x boost if ≥ 2 independent sources agree on the exact value (capped at 1.0).
Overall confidence is the arithmetic mean of all field scores.

## 4. Runtime Configurable Output (Projection Layer)
TalentFlow implements a robust Projection Layer to divorce the canonical state from output demands without code changes. A JSON runtime config can:
- **Select / Rename**: Extract nested fields via JSON paths (`"from": "emails[0]"` → mapped to `"primary_email"`).
- **Format Toggle**: Run per-field normalizations (e.g., `"normalize": "E164"`) or hide sections (`"include_provenance": false`).
- **On-Missing Policy**: If a required field is empty, the pipeline respects the `"on_missing"` key, behaving gracefully (`"null"` sets it to null, `"omit"` removes the key, `"error"` throws an exception).

## 5. Edge Cases Handled & Deliberate Scope Cuts
### Edge Cases Successfully Handled:
1. **Garbage Data / Financial Statements**: The Resume Parser utilizes structural guardrails (headers like "Technical Skills:") and strict pattern validation (preventing "6th Floor" from being tagged as a skill). If unsure, it returns `[]` (Honestly-empty).
2. **Missing / Unparseable Sources**: Encrypted PDFs, syntax-error JSONs, or zero-row CSVs degrade gracefully and log warnings without crashing the pipeline.
3. **GitHub API Constraints**: Extracts languages and bios optimally but implements cascading fallback (API -> HTML Scraping -> Heuristics) if Rate Limit (HTTP 403) is breached.

### Deliberately Descoped (Under Time Pressure):
- **Image-only PDF OCR**: Current implementation parses text via PyMuPDF. Pure images return an empty record rather than utilizing heavy frameworks like Tesseract OCR.
- **LLM Extraction**: Standardized on deterministic regexes rather than Generative AI to guarantee 100% determinism, execution speed, and absolute explainability on 10k+ candidates.
- **LinkedIn Profile Scraping**: Deliberately bypassed live scraping logic as LinkedIn aggressively rate-limits/blocks unauthenticated bots.
