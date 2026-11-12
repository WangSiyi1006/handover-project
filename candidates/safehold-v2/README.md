# COMP3014J Handover — team code

`algorithm.py` is the self-contained `StudentPolicy` used as the starting point for team changes. Use Python 3.11 and keep the policy within the assignment's single-file and dependency limits. Run the tests when you change the policy, and compare policies with the same official evaluator, scenario set and settings.

## Test the policy

No benchmark or third-party packages are needed for the unit tests.

```sh
python -m unittest discover -s tests -v
```

## Run the official practice suite

From the repository root, place the official course copy of `handover-bench` in `benchmark/handover-bench/` (the directory containing `pyproject.toml`). This directory and all generated evaluation results are ignored by Git.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -e benchmark/handover-bench
.\.venv\Scripts\python.exe scripts\evaluate.py
```

macOS/Linux:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install -e benchmark/handover-bench
.venv/bin/python scripts/evaluate.py
```

If you already have the course benchmark installed in a Python environment, use that interpreter and pass `--benchmark <path-to-handover-bench>` to point to its local checkout. Use `--algorithm <path-to-policy.py>` to compare another policy. Relative paths are resolved from the repository root. Each run writes to a new directory under `results/`.
