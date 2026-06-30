# TalentFlow - Candidate Profile Transformer

TalentFlow is a robust data ingestion, normalization, and canonicalization pipeline built to transform messy candidate data from disparate sources (ATS systems, HRIS databases, and unstructured Resumes) into unified, standardized Candidate Profiles.

It satisfies all evaluation criteria laid out in the Candidate Profile Transformer problem statement, featuring a modern modular architecture, deterministic merging logic, confidence scoring, and a sleek web UI.

---

## 🚀 Features

- **Multi-Source Ingestion**: Parses JSON (ATS payloads), CSV (HRIS exports), and plain text, PDF, or DOCX (Resumes).
- **Advanced Normalization**:
  - Validates and standardizes Phone Numbers to E.164 format.
  - Normalizes Dates to `YYYY-MM` and computes `years_experience`.
  - Canonicalizes Skills against known aliases (e.g., "ML" -> "Machine Learning").
  - Standardizes Country and Region names.
- **Deterministic Merging & Identity Resolution**: Uses Union-Find logic on emails to group profiles and deterministic hashing for fallback candidate IDs. Resolves field conflicts using source weighting.
- **Confidence Scoring**: Evaluates the completeness and reliability of each unified profile and calculates a 0.0 to 1.0 confidence score.
- **Extensible Configuration**: Supports JSON-based configuration policies for custom output projections (field selection, renaming, and missing value policies).
- **Secure Web UI**: Beautiful, glassmorphic UI built with modern HTML/CSS/JS communicating with a hardened FastAPI backend.

---

## 🏗 System Architecture

The pipeline follows a strict multi-stage synchronous architecture to ensure data integrity and traceability:

1. **Ingestion**: Detects file types and routes to appropriate parsers.
2. **Extraction**: Parsers (JSON, CSV, Resume) extract raw data into `IntermediateRecord` models.
3. **Normalization**: Applies canonical rules to phones, dates, locations, and skills.
4. **Merging**: Groups records by identity (Email overlap -> Name match fallback) and resolves conflicts using `source_weight` and union operations.
5. **Confidence Scoring**: Computes a confidence score based on field completeness and source weights.
6. **Projection (Optional)**: Applies a custom config policy to reshape the canonical profiles.
7. **Validation & Output**: Emits the final output as a standardized JSON structure.

---

## 🛠 Tech Stack

- **Core**: Python 3.11+
- **Data Validation**: Pydantic v2
- **API Backend**: FastAPI
- **Parsing**: `python-dateutil`, `phonenumbers`, `pycountry`, `pymupdf` (PDF), `python-docx` (DOCX)
- **CLI**: Click
- **Frontend**: Vanilla JS, CSS Variables, Glassmorphism design (PulseAI inspired)
- **Testing**: Pytest (100+ tests covering parsers, edge cases, e2e)

---

## 📦 Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/hariteja-01/TalentFlow.git
   cd TalentFlow
   ```

2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   ```

---

## 💻 Usage

### Command Line Interface (CLI)

You can run the pipeline directly from your terminal using the `talentflow` CLI tool.

**Basic Usage:**
```bash
talentflow -i sample_inputs/ -o sample_outputs/output.json
```

**With Custom Configuration Policy:**
```bash
talentflow -i sample_inputs/ -o sample_outputs/custom.json -c config.json
```

### Web UI

TalentFlow includes a beautiful, fully responsive Web UI.

1. **Start the API server:**
   ```bash
   python -m api.index
   # Or using uvicorn:
   # uvicorn api.index:app --reload
   ```
2. **Open the App:** Navigate to `http://localhost:8000` in your browser.
3. **Process Files:** Drag & drop your JSON, CSV, TXT, PDF, or DOCX files to see the pipeline run in real-time.

---

## 🧪 Testing

The repository includes a comprehensive test suite covering unit tests, edge cases, and end-to-end pipeline execution.

```bash
# Run all tests
pytest tests/ -v
```

---

## 🔒 Security & Privacy

- **CORS Protection**: The FastAPI backend is configured with strict CORS rules to prevent unauthorized cross-origin requests.
- **XSS Mitigation**: The Web UI uses proper HTML escaping for all user-supplied data before DOM insertion.
- **File Validation**: The API validates file extensions and enforces a 10MB file size limit before processing.

---

## 📄 License

This project was built for the Eightfold Candidate Profile Transformer evaluation.
