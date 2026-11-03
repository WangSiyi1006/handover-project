"""Evaluate a student algorithm.py against the A3 baseline on a suite of
scenarios. This is the public practice evaluator. The separate instructor
runner shares the simulator, metric calculation and score while isolating
student policy execution -- see docs/submission.md.

This runs student code in-process. It is adequate for local practice, but
NOT the isolated/sandboxed execution required for grading. Use the
separate instructor runner for private submissions.
"""

import importlib.util
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Type

from ..api import StudentPolicy
from ..baselines.a3 import A3Policy
from ..baselines.no_handover import NoHandoverPolicy
from ..config import Config
from ..metrics.compute import compute_metrics
from ..metrics.scoring import compute_score
from ..simulator.engine import run_scenario
from ..simulator.scenario import list_scenario_ids, load_scenario


def load_policy_class(algorithm_path: str | Path) -> Type[StudentPolicy]:
    """Import `algorithm_path` and return its `StudentPolicy` class."""
    algorithm_path = Path(algorithm_path).resolve()
    if not algorithm_path.exists():
        raise FileNotFoundError(algorithm_path)

    module_name = f"handover_bench_submission_{abs(hash(str(algorithm_path)))}"
    spec = importlib.util.spec_from_file_location(module_name, algorithm_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {algorithm_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "StudentPolicy"):
        raise AttributeError(f"{algorithm_path} does not define a StudentPolicy class")
    return module.StudentPolicy


def _run_policy_on_suite(
    policy_factory,
    data_dir: Path,
    scenario_ids: list[str],
    config: Config,
) -> dict[str, Any]:
    """Replay `policy_factory` over every scenario and compute its metrics.
    Scoring is a separate step (compute_score) since the score is relative
    to the A3 baseline's metrics on the same scenarios -- see
    metrics/scoring.py."""
    results = []
    errors = []
    start = time.monotonic()
    for sid in scenario_ids:
        scenario = load_scenario(data_dir, sid)
        try:
            results.append(run_scenario(scenario, policy_factory, config))
        except Exception:  # noqa: BLE001 -- isolate one scenario's crash from the rest
            errors.append({"scenario_id": sid, "traceback": traceback.format_exc()})
    runtime_s = time.monotonic() - start

    metrics = compute_metrics(results)
    return {
        "status": "invalid" if errors else "valid",
        "metrics": metrics,
        "errors": errors,
        "runtime_s": round(runtime_s, 3),
        "num_scenarios_evaluated": len(results),
    }


def evaluate(
    algorithm_path: str | Path,
    data_dir: str | Path,
    scenario_ids: list[str] | None = None,
    config: Config | None = None,
    include_no_handover_reference: bool = True,
) -> dict[str, Any]:
    """Evaluate one algorithm.py against every scenario in `data_dir`,
    alongside the A3 baseline on the same scenarios.

    A student failure on any scenario invalidates the whole run, assigning
    score 0. Successful-scenario metrics remain available for diagnosis but
    are never scored as a reduced suite. Baseline failures abort evaluation:
    an incomplete reference cannot yield a fair student score.
    """
    cfg = config or Config()
    data_dir = Path(data_dir)
    scenario_ids = scenario_ids or list_scenario_ids(data_dir)
    if not scenario_ids:
        raise ValueError(f"No scenarios found in {data_dir}")

    student_cls = load_policy_class(algorithm_path)
    student_run = _run_policy_on_suite(student_cls, data_dir, scenario_ids, cfg)
    baseline_run = _run_policy_on_suite(A3Policy, data_dir, scenario_ids, cfg)
    if baseline_run["errors"]:
        failed_ids = ", ".join(error["scenario_id"] for error in baseline_run["errors"])
        raise RuntimeError(f"A3 baseline failed on scenario(s): {failed_ids}; evaluation aborted")

    baseline_aggregate = baseline_run["metrics"]["aggregate"]
    if student_run["errors"]:
        student_run["score"] = {
            "score": 0.0,
            "reason": "A student scenario failed; the whole run is invalid and receives score 0.",
            "ratios": {},
            "weights": {},
            "components": {},
        }
    else:
        student_run["score"] = compute_score(student_run["metrics"]["aggregate"], baseline_aggregate, cfg)
    # The baseline's own score against itself is 100.0 by construction --
    # it IS the reference the student is scored against, not a competitor.
    baseline_run["score"] = compute_score(baseline_aggregate, baseline_aggregate, cfg)
    # Unscored floor for comparison: never requests a handover.
    reference_run = None
    if include_no_handover_reference:
        reference_run = _run_policy_on_suite(NoHandoverPolicy, data_dir, scenario_ids, cfg)
        reference_run["score"] = compute_score(
            reference_run["metrics"]["aggregate"], baseline_aggregate, cfg
        )
    baseline_rows = {
        row["scenario_id"]: row for row in baseline_run["metrics"]["per_scenario"]
    }
    for row in baseline_rows.values():
        row["score"] = compute_score(row, row, cfg)
    for row in student_run["metrics"]["per_scenario"]:
        row["score"] = compute_score(row, baseline_rows[row["scenario_id"]], cfg)

    return {
        "status": student_run["status"],
        "algorithm_path": str(Path(algorithm_path).resolve()),
        "data_dir": str(data_dir.resolve()),
        "scenario_ids": scenario_ids,
        "student": student_run,
        "a3_baseline": baseline_run,
        "no_handover_reference": reference_run,
        "score_delta_vs_a3": round(student_run["score"]["score"] - 100.0, 2),
    }
