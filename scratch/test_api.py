import sys
from pathlib import Path
sys.path.append(str(Path(".").resolve()))
from fastapi.testclient import TestClient
from api.index import app
from pathlib import Path
import json

client = TestClient(app)

files = [
    ("files", ("resume_1.txt", Path("sample_inputs/unstructured/resume_jane_doe.txt").read_bytes(), "text/plain")),
    ("files", ("resume_2.txt", Path("sample_inputs/unstructured/resume_jane_doe.txt").read_bytes(), "text/plain"))
]

response = client.post("/api/process", files=files)
print(response.status_code)
data = response.json()
print("Extracted profiles via API:", len(data.get("profiles", [])))
for p in data.get("profiles", []):
    print(p.get("full_name"), p.get("emails"))
