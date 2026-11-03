"""Command-line entry point: `handover-bench <command> ...`."""

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .dashboard.html_report import write_dashboard
from .evaluation.report import write_report
from .evaluation.runner import evaluate


def _cmd_evaluate(args: argparse.Namespace) -> int:
    config = Config()
    result = evaluate(args.algorithm, args.suite, config=config)
    out_dir = Path(args.output)
    report_path = write_report(result, out_dir)
    dashboard_path = write_dashboard(result, out_dir)

    student = result["student"]
    baseline = result["a3_baseline"]
    print(f"Evaluated {result['algorithm_path']} on {len(result['scenario_ids'])} scenario(s).")
    print("  Score is a composite index relative to A3 (baseline = 100.0).")
    print("  No imposed cap; each fixed suite has a finite mathematical upper bound.")
    print(f"  Your score:  {student['score']['score']}")
    print(f"  A3 baseline: {baseline['score']['score']} (reference)")
    if result.get("no_handover_reference"):
        print(f"  Never hand over: {result['no_handover_reference']['score']['score']} (comparison reference)")
    print(f"  Delta:       {result['score_delta_vs_a3']:+.2f}")
    if student["errors"]:
        print(f"  WARNING: {len(student['errors'])} scenario(s) errored -- see {report_path}")
    print(f"Report:    {report_path}")
    print(f"Dashboard: {dashboard_path}")
    return 1 if student["errors"] else 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from .evaluation.report import read_report

    result = read_report(Path(args.results) / "results.json")
    path = write_dashboard(result, args.results)
    print(f"Dashboard: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handover-bench")
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("evaluate", help="Evaluate algorithm.py against the A3 baseline.")
    p_eval.add_argument("--algorithm", required=True)
    p_eval.add_argument("--suite", default="data/practice")
    p_eval.add_argument("--output", default="results/practice")
    p_eval.set_defaults(func=_cmd_evaluate)

    p_dash = sub.add_parser("dashboard", help="(Re)render the HTML dashboard from a results dir.")
    p_dash.add_argument("--results", required=True)
    p_dash.set_defaults(func=_cmd_dashboard)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
