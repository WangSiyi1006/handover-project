"""Write an evaluation result to disk as JSON, for the dashboard and for
grading records."""

import json
from pathlib import Path
from typing import Any


def write_report(result: dict[str, Any], out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "results.json"
    path.write_text(json.dumps(result, indent=2, default=str))
    return path


def read_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())
