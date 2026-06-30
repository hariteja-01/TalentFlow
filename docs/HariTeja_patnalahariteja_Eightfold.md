# Candidate Profile Transformer — Design Document

**Hari Teja Patnala** · patnalahariteja@gmail.com

---

## 1. Pipeline Architecture

```
Source Files → Ingest → Extract → Normalize → Merge → Score → Project → Validate → Output JSON
```

Each stage is a pure function with typed inputs/outputs; errors are caught at stage boundaries and logged—never propagated.

| Stage | Responsibility | Error Boundary |
|---|---|---|
| **Ingest** | Detect format (CSV, JSON, PDF/DOCX/TXT, GitHub URL), route to parser | Corrupted file → skip + warn |
| **Extract** | Parse into `IntermediateRecord` (one per source) | Missing fields → `null` |
| **Normalize** | Phone → E.164, dates → YYYY-MM, country → ISO-3166, skills → canonical | Invalid value → `null` |
| **Merge** | Union-Find on identity keys → fused `CanonicalProfile` | Conflicts → source-weight resolution |
| **Score** | Compute per-field and overall confidence | — |
| **Project** | Apply output config to select/reshape fields | Missing path → `on_missing` policy |
| **Validate** | Assert output against config schema | Schema violation → raise |

**Parsers:** CSV and ATS JSON (structured; field-mapping layer for non-canonical ATS schemas) · Resume PDF/DOCX/TXT (unstructured; regex + heuristic section extraction) · GitHub profile URLs (unstructured; API fetch for repos, languages, bio).

## 2. Canonical Schema & Normalizations

| Field | Type | Notes |
|---|---|---|
| `candidate_id` | `str` | SHA-256 of sorted, lowercased emails |
| `full_name` | `str` | — |
| `emails` | `List[str]` | Deduplicated, lowercased |
| `phones` | `List[str]` | E.164 format |
| `location` | `{city, region, country}` | `country` = ISO-3166 alpha-2 |
| `links` | `{linkedin, github, portfolio, other[]}` | — |
| `headline` | `str \| null` | — |
| `years_experience` | `float \| null` | — |
| `skills` | `List[{name, confidence, sources[]}]` | Canonical name, per-skill confidence |
| `experience` | `List[{company, title, start, end, summary}]` | Dates as `YYYY-MM`; `"Present"` → `null` |
| `education` | `List[{institution, degree, field, end_year}]` | — |
| `provenance` | `List[{field, source, method}]` | Full audit trail |
| `overall_confidence` | `float` | Mean of field-level scores, 0.0–1.0 |

**Normalization rules:** Phone → E.164 via `libphonenumber` (`"(415) 555-2671"` → `"+14155552671"`; invalid → `null`) · Dates → `YYYY-MM` via `dateutil` (`"June 2020"` → `"2020-06"`) · Country → ISO-3166 via `pycountry` (`"United States"` → `"US"`, `"UK"` → `"GB"`) · Skills → alias dict (~100 entries): `"ML"` → `"Machine Learning"`, `"react"` → `"React"`; unknown → Title Case.

## 3. Merge & Conflict Resolution Policy

**Identity resolution — Union-Find:**  
*Primary key:* email overlap (any shared email → same person, applied transitively).  
*Secondary key:* exact name match (case-insensitive). Two records sharing either key are unioned into one cluster.

**Source priority weights:** JSON `0.9` > CSV `0.7` > Resume `0.6` > GitHub `0.4`

| Conflict type | Resolution |
|---|---|
| Scalar (`name`, `headline`) | Highest source weight wins |
| List (`emails`, `phones`) | Union all, deduplicate |
| Skills | Union; track confirming sources per skill |
| Experience / Education | Collect all; deduplicate by `(company, title)` or `(institution, degree)` |

**Example:** JSON `name="Jane M. Doe"` (0.9) vs. CSV `"Jane Doe"` (0.7) → JSON wins.

**Determinism:** Records sorted by `(source_weight desc, source_name desc)` before merge. `candidate_id` = SHA-256 of sorted, lowercased emails. Identical inputs always produce identical output.

**Confidence scoring:**  
Per-field: `source_weight × completeness × agreement_bonus` (agreement_bonus = `1.2×` if ≥2 sources agree).  
Per-skill: `base 0.5 + 0.15` per confirming source (capped at 1.0).  
Overall: mean of all field-level scores.

**Provenance:** Every retained value carries `{field, source, method}` — full traceability of where data came from and which rule selected it.

## 4. Runtime Configurable Output

The pipeline builds a full `CanonicalProfile` first, then applies a **projection config** (JSON) as the final stage — no code changes needed for new output shapes.

```json
{
  "fields": [{"path": "primary_email", "from": "emails[0]", "type": "string"}],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"
}
```

**`from` expressions:** array index (`emails[0]`), nested access (`location.country`), array spread (`skills[].name`).  
**`on_missing` policies:** `"null"` (return null) · `"omit"` (exclude key) · `"error"` (raise exception).  
Per-field normalization toggle available (`"normalize": "E164"` or `"canonical"`). Output validated against config schema post-projection.

## 5. Edge Cases & Limitations

**Handled:**
- Corrupted / image-only PDF → detect zero extracted text, log diagnostic, skip, pipeline continues
- ATS JSON with non-canonical fields → mapping layer resolves before extraction
- GitHub API 403 (rate limit) / 404 (not found) → log warning, degrade gracefully
- Conflicting emails across sources → union all, deduplicate, track in provenance
- Skill aliases (`"react"` / `"React"` / `"ReactJS"` → `"React"`)
- Empty CSV/JSON → skip with warning, never crash
- Config requests `emails[0]` on empty array → returns `null`, not error

**Deliberately omitted:**
- **OCR** for image-only PDFs — heavyweight dependency; kept pipeline lightweight
- **LLM-based extraction** — preferred determinism and zero-latency over marginal accuracy gains
- **Real-time LinkedIn scraping** — blocked by LinkedIn ToS
- **Database persistence** — pipeline is stateless and composable by design
