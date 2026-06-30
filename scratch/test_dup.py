import sys
from pathlib import Path
sys.path.append(str(Path(".").resolve()))
from src.pipeline.orchestrator import run_pipeline

res = run_pipeline([Path("sample_inputs")])
print("Extracted profiles:", len(res.profiles))
for p in res.profiles:
    print(p.full_name, p.emails)
