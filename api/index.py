from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Add src to python path for Vercel imports if necessary
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.pipeline.orchestrator import run_pipeline, load_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="TalentFlow Transformer API",
    description="API for parsing and merging candidate profiles from multiple sources."
)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "https://talent-flow-gules.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled API exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )

@app.get("/", response_class=HTMLResponse)
def read_root():
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>UI Template not found</h1>"

@app.get("/api")
def read_api_root():
    return {"message": "Welcome to the TalentFlow Transformer API. Use POST /api/process to process candidate files."}

@app.get("/api/samples")
def list_samples():
    sample_dir = Path(__file__).parent.parent / "sample_inputs"
    samples = []
    if sample_dir.exists():
        for root, dirs, files in os.walk(sample_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(sample_dir)
                samples.append(str(rel_path).replace('\\', '/'))
    return {"samples": samples}

@app.get("/api/configs")
def list_configs():
    config_dir = Path(__file__).parent.parent / "configs"
    configs = []
    if config_dir.exists():
        for file in config_dir.glob("*.json"):
            configs.append(file.name)
    return {"configs": configs}

@app.get("/api/samples/{file_path:path}")
def get_sample(file_path: str):
    sample_dir = Path(__file__).parent.parent / "sample_inputs"
    target_file = sample_dir / file_path
    
    # Security check to prevent directory traversal
    try:
        if not target_file.resolve().is_relative_to(sample_dir.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
    except AttributeError:
        # Fallback for python < 3.9
        if sample_dir.resolve() not in target_file.resolve().parents:
            raise HTTPException(status_code=403, detail="Access denied")
            
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Sample file not found")
        
    return FileResponse(target_file)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".json", ".csv", ".txt", ".pdf", ".docx"}

def secure_filename(filename: str) -> str:
    if not filename:
        return "unnamed_file"
    filename = os.path.basename(filename)
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    return filename

def validate_file_content(content: bytes, ext: str) -> bool:
    if len(content) == 0:
        return False
    if ext == ".pdf":
        return content.startswith(b"%PDF")
    if ext == ".docx":
        return content.startswith(b"PK\x03\x04")
    if ext in {".json", ".csv", ".txt"}:
        try:
            content[:1024].decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False
    return False

@app.post("/api/process")
async def process_files(files: list[UploadFile] = File(...), config_name: str = Form(None)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        for file in files:
            ext = Path(file.filename).suffix.lower() if file.filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")

            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail=f"File {file.filename} exceeds maximum size of 10MB")
                
            import uuid
            safe_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file_path = tmp_path / safe_filename
            with open(file_path, "wb") as f:
                f.write(content)
        
        try:
            config = None
            if config_name:
                config_path = Path(__file__).parent.parent / "configs" / config_name
                if config_path.exists():
                    config = load_config(config_path)

            # Run the pipeline on the temporary directory
            result = run_pipeline([tmp_path], config)
            
            # Serialize the resulting Pydantic models to dictionaries
            return JSONResponse(content={
                "profiles": [json.loads(p.model_dump_json()) for p in result.profiles],
                "warnings": result.warnings
            })
        except Exception as e:
            logger.error("Error processing files: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to process files")

# Local UI Server initialization
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.index:app", host="0.0.0.0", port=8000, reload=True)
