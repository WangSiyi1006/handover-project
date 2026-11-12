"""Run the unchanged course evaluator against a local policy."""

import argparse
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", default="algorithm.py", help="Policy file")
    parser.add_argument(
        "--benchmark",
        default="benchmark/handover-bench",
        help="Local official handover-bench directory",
    )
    parser.add_argument("--suite", help="Override the benchmark's data/practice directory")
    args = parser.parse_args()

    algorithm = (ROOT / args.algorithm).resolve()
    benchmark = (ROOT / args.benchmark).resolve()
    suite = (ROOT / args.suite).resolve() if args.suite else benchmark / "data" / "practice"
    if not algorithm.is_file():
        parser.error(f"Policy file not found: {algorithm}")
    if not (benchmark / "pyproject.toml").is_file():
        parser.error(f"Official benchmark not found: {benchmark}. See README.md or use --benchmark.")
    if not suite.is_dir():
        parser.error(f"Scenario directory not found: {suite}")
    if find_spec("handover_bench") is None:
        parser.error(f'Install the official benchmark in this Python environment: python -m pip install -e "{benchmark}"')

    output = ROOT / "results" / datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    print(f"Output: {output}", flush=True)
    result = subprocess.run(
        [
            sys.executable, "-m", "handover_bench.cli", "evaluate",
            "--algorithm", str(algorithm), "--suite", str(suite), "--output", str(output),
        ],
        cwd=benchmark,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
