"""Local, static HTML results viewer.

Renders one self-contained HTML file summarising a completed evaluation
(student vs A3 baseline, per-scenario breakdown). No server, no network
calls -- `handover-bench dashboard` just writes this file and points the
student at it; students are not responsible for developing the dashboard.
"""

import html
from pathlib import Path
from typing import Any

_STYLE = """
body { font-family: -apple-system, Segoe UI, sans-serif; margin: 2rem; color: #1a1a1a; background: #fafafa; }
h1, h2 { margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; background: white; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: right; font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; }
th { background: #f0f0f0; }
.score { font-size: 2rem; font-weight: 700; }
.delta-pos { color: #147a2e; }
.delta-neg { color: #b3261e; }
.na { color: #999; }
"""


def _fmt(v: Any) -> str:
    if v is None:
        return '<span class="na">N/A</span>'
    if isinstance(v, float):
        return f"{v:.4f}"
    return html.escape(str(v))


def _metric_rows(
    student_agg: dict,
    baseline_agg: dict,
    fields: list[tuple[str, str]],
    reference_agg: dict | None = None,
) -> str:
    rows = []
    for key, label in fields:
        reference_cell = "" if reference_agg is None else f"<td>{_fmt(reference_agg.get(key))}</td>"
        rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{_fmt(student_agg.get(key))}</td>"
            f"<td>{_fmt(baseline_agg.get(key))}</td>{reference_cell}</tr>"
        )
    return "\n".join(rows)


AGGREGATE_FIELDS = [
    ("ho_attempts", "Handover attempts"),
    ("ho_completed", "Handover completions"),
    ("ho_failed", "Handover failures"),
    ("ho_success_rate", "Handover success rate (completed / (completed + failed))"),
    ("ho_failures_per_ue_min", "Handover failures per UE-minute"),
    ("rlf_events", "RLF events"),
    ("rlf_per_ue_min", "RLF per UE-minute"),
    ("ping_pong_events", "Ping-pong events"),
    ("ping_pong_per_ue_min", "Ping-pong per UE-minute"),
    ("outage_fraction", "Outage fraction (of active UE-time)"),
    ("ho_interruption_fraction", "HO interruption fraction (of active UE-time)"),
    ("radio_outage_fraction", "Attached below Q_out, no delivery (of active UE-time)"),
    ("goodput_ratio", "Delivered goodput / offered traffic"),
    ("deadline_delivery_ratio", "Delivered within deadline / offered traffic"),
    ("delay_p50_ms", "Packet delay p50 (ms)"),
    ("delay_p95_ms", "Packet delay p95 (ms)"),
    ("delay_p99_ms", "Packet delay p99 (ms)"),
    ("deadline_misses", "Deadline misses (count)"),
    ("undelivered_packets", "Undelivered packets at scenario end"),
]


def render_html_report(result: dict[str, Any]) -> str:
    student = result["student"]
    baseline = result["a3_baseline"]
    reference = result.get("no_handover_reference")
    reference_agg = reference["metrics"]["aggregate"] if reference else None
    reference_header = "<th>Never hand over (reference)</th>" if reference else ""
    reference_html = ""
    if reference:
        reference_html = (
            f'<p>Never hand over: <span class="score">{reference["score"]["score"]}</span> '
            "(comparison reference: a policy that never requests a handover. "
            "Initial attachment and reconnection after radio link failure are "
            "automatic. The supplied always-stay starter behaves identically; "
            "A3 remains the grading baseline.)</p>"
        )
    delta = result["score_delta_vs_a3"]
    delta_class = "delta-pos" if delta >= 0 else "delta-neg"
    status = student.get("status", "invalid" if student["errors"] else "valid")
    invalid_html = ""
    if status == "invalid":
        invalid_html = (
            '<p class="delta-neg">This run is invalid and receives score 0 because '
            "a student scenario failed. Metrics and scenario scores below describe "
            "only successful scenarios and are diagnostic.</p>"
        )

    student_rows = {row["scenario_id"]: row for row in student["metrics"]["per_scenario"]}
    baseline_rows = {row["scenario_id"]: row for row in baseline["metrics"]["per_scenario"]}
    failed_ids = {error["scenario_id"] for error in student["errors"]}
    scenario_rows = []
    for sid in result["scenario_ids"]:
        s_row = student_rows.get(sid, {})
        b_row = baseline_rows.get(sid, {})
        scenario_status = "Failed" if sid in failed_ids else "Valid" if s_row else "Unavailable"
        scenario_rows.append(
            "<tr><td>{sid}</td><td>{status}</td><td>{s_score}</td><td>{s_out}</td><td>{s_gp}</td>"
            "<td>{b_out}</td><td>{b_gp}</td></tr>".format(
                sid=html.escape(sid),
                status=scenario_status,
                s_score=_fmt(s_row.get("score", {}).get("score")),
                s_out=_fmt(s_row.get("outage_fraction")),
                s_gp=_fmt(s_row.get("goodput_ratio")),
                b_out=_fmt(b_row.get("outage_fraction")),
                b_gp=_fmt(b_row.get("goodput_ratio")),
            )
        )

    component_rows = []
    for name, ratio in student["score"]["ratios"].items():
        component = student["score"].get("components", {}).get(name, {})
        contribution = component.get("weighted_log_contribution")
        contribution_html = "N/A" if contribution is None else f"{contribution:+.6f}"
        effect = component.get("effect", "N/A")
        effect_class = {"gain": "delta-pos", "regression": "delta-neg"}.get(effect, "")
        direction = {"higher": "Higher is better", "lower": "Lower is better"}.get(
            component.get("direction"), "N/A"
        )
        component_rows.append(
            f"<tr><td>{html.escape(name)}</td><td>{direction}</td>"
            f"<td>{_fmt(student['score']['weights'][name])}</td><td>{_fmt(ratio)}</td>"
            f'<td class="{effect_class}">{contribution_html}</td>'
            f"<td>{_fmt(component.get('score_factor'))}</td>"
            f'<td class="{effect_class}">{html.escape(effect)}</td></tr>'
        )

    errors_html = ""
    for run_name, run in (("student", student), ("a3_baseline", baseline)):
        if run["errors"]:
            items = "".join(
                f"<li><b>{html.escape(e['scenario_id'])}</b><pre>{html.escape(e['traceback'])}</pre></li>"
                for e in run["errors"]
            )
            errors_html += f"<h3>Errors ({html.escape(run_name)})</h3><ul>{items}</ul>"

    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>handover-bench results</title><style>{_STYLE}</style></head>
<body>
<h1>handover-bench evaluation results</h1>
<p>Algorithm: <code>{html.escape(result['algorithm_path'])}</code></p>
<p>Suite: <code>{html.escape(result['data_dir'])}</code> ({len(result['scenario_ids'])} scenario(s))</p>

<h2>Score</h2>
<p>Composite index relative to the A3 baseline, which always scores 100.0.
There is no imposed score cap, but each fixed suite has a finite mathematical
upper bound. Scores above 100 indicate a better weighted combination of
KPIs; scores below 100 indicate a worse combination. This index is not a
percentage assignment mark.</p>
<p>Your algorithm: <span class="score">{student['score']['score']}</span></p>
<p>Run status: <b>{html.escape(status)}</b></p>
{invalid_html}
<p>A3 baseline: <span class="score">{baseline['score']['score']}</span> (reference)</p>
{reference_html}
<p>Delta vs A3: <span class="{delta_class}">{delta:+.2f}</span></p>

<h2>Score components</h2>
<p>Each ratio is &gt; 1 where your algorithm beats the A3 baseline on that
metric, &lt; 1 where it falls short, and exactly 1 at parity. Outage,
RLF, handover-failure, ping-pong and attempt rates are lower-is-better.</p>
<p>Negative weighted log contributions penalise regressions. Each score
factor is the exponential of its contribution: score = 100 &times; the
product of all factors. These are multiplicative effects, not deductions
in index points.</p>
<table>
<tr><th>Component</th><th>Preferred direction</th><th>Weight</th><th>Your ratio vs A3</th><th>Weighted log contribution</th><th>Score factor</th><th>Effect</th></tr>
{"".join(component_rows)}
</table>

<h2>Aggregate metrics (successful scenarios only if a run is invalid)</h2>
<table>
<tr><th>Metric</th><th>Your algorithm</th><th>A3 baseline</th>{reference_header}</tr>
{_metric_rows(student['metrics']['aggregate'], baseline['metrics']['aggregate'], AGGREGATE_FIELDS, reference_agg)}
</table>

<h2>Per-scenario (outage fraction / goodput ratio)</h2>
<p>Each scenario score uses its matching A3 reference. The overall score
uses aggregate KPIs and is not the mean of the scenario scores.</p>
<table>
<tr><th>Scenario</th><th>Status</th><th>Score</th><th>Your outage</th><th>Your goodput</th><th>A3 outage</th><th>A3 goodput</th></tr>
{"".join(scenario_rows)}
</table>

{errors_html}
</body>
</html>
"""


def write_dashboard(result: dict[str, Any], out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "dashboard.html"
    path.write_text(render_html_report(result))
    return path
