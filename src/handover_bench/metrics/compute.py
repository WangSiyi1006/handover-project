"""Metric definitions.

Every rate below states its denominator explicitly (docs/metrics.md mirrors
this). Metrics are computed PER SCENARIO first, then averaged unweighted
across scenarios, so one large scenario cannot dominate the suite result.
A ratio is `None` ("N/A") when its denominator is zero (e.g. no handovers
attempted, or a scenario with no offered traffic) rather than silently
reported as 0 or 1.
"""

import statistics
from typing import Any

from ..simulator.events import ScenarioResult


def _rate(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return values[idx]


def _mode_breakdown(ue_results) -> dict[str, dict[str, Any]]:
    by_mode: dict[str, list] = {}
    for ue in ue_results:
        by_mode.setdefault(ue.mode, []).append(ue)
    out = {}
    for mode, ues in by_mode.items():
        attempts = sum(u.ho_attempts for u in ues)
        completed = sum(u.ho_completed for u in ues)
        failed = sum(u.ho_failed for u in ues)
        active = sum(u.active_steps for u in ues)
        outage = sum(u.outage_steps + u.radio_outage_steps for u in ues)
        out[mode] = {
            "num_ues": len(ues),
            "ho_attempts": attempts,
            "ho_completed": completed,
            "ho_failed": failed,
            "ho_success_rate": _rate(completed, completed + failed),
            "outage_fraction": _rate(outage, active),
        }
    return out


def _scenario_metrics(result: ScenarioResult) -> dict[str, Any]:
    ues = list(result.ue_results.values())
    active_steps = sum(u.active_steps for u in ues)
    connected_steps = sum(u.connected_steps for u in ues)
    # Unattached steps plus attached-but-below-Q_out steps (no delivery).
    outage_steps = sum(u.outage_steps + u.radio_outage_steps for u in ues)
    radio_outage_steps = sum(u.radio_outage_steps for u in ues)
    interruption_steps = sum(u.ho_interruption_steps for u in ues)

    ho_attempts = sum(u.ho_attempts for u in ues)
    ho_completed = sum(u.ho_completed for u in ues)
    ho_failed = sum(u.ho_failed for u in ues)
    ho_ongoing = sum(u.ho_ongoing_at_end for u in ues)
    rlf_events = sum(u.rlf_events for u in ues)
    pp_events = sum(u.ping_pong_events for u in ues)

    ue_minutes = active_steps * result.delta_t_ms / 60_000.0

    packets = result.packets
    offered_bytes = sum(p.size_bytes for p in packets)
    delivered_bytes = sum(p.delivered_bytes for p in packets)
    delivered_within_deadline_bytes = sum(
        p.size_bytes
        for p in packets
        if p.delivered and p.delivery_time_ms is not None and p.delivery_time_ms <= p.deadline_abs_ms
    )
    deadline_misses = sum(
        1
        for p in packets
        if p.delivered and p.delivery_time_ms is not None and p.delivery_time_ms > p.deadline_abs_ms
    )
    undelivered_count = sum(1 for p in packets if not p.delivered)
    remaining_backlog_bytes = sum(
        p.size_bytes - p.delivered_bytes for p in packets if not p.delivered
    )
    delays_ms = [
        p.delivery_time_ms - p.arrival_time_ms
        for p in packets
        if p.delivered and p.delivery_time_ms is not None
    ]

    return {
        "scenario_id": result.scenario_id,
        "num_ues": len(ues),
        "ho_attempts": ho_attempts,
        "ho_completed": ho_completed,
        "ho_failed": ho_failed,
        "ho_ongoing_at_end": ho_ongoing,
        "ho_success_rate": _rate(ho_completed, ho_completed + ho_failed),
        "ho_failure_rate": _rate(ho_failed, ho_attempts),
        "rlf_events": rlf_events,
        "ping_pong_events": pp_events,
        "ping_pong_rate_per_completed_ho": _rate(pp_events, ho_completed),
        "outage_fraction": _rate(outage_steps, active_steps) or 0.0,
        "ho_interruption_fraction": _rate(interruption_steps, active_steps) or 0.0,
        "radio_outage_fraction": _rate(radio_outage_steps, active_steps) or 0.0,
        "offered_bytes": offered_bytes,
        "delivered_bytes": delivered_bytes,
        "goodput_ratio": _rate(delivered_bytes, offered_bytes),
        "deadline_delivery_ratio": _rate(delivered_within_deadline_bytes, offered_bytes),
        "deadline_misses": deadline_misses,
        "undelivered_packets": undelivered_count,
        "remaining_backlog_bytes": remaining_backlog_bytes,
        "delay_p50_ms": _percentile(delays_ms, 0.50),
        "delay_p95_ms": _percentile(delays_ms, 0.95),
        "delay_p99_ms": _percentile(delays_ms, 0.99),
        "ho_failures_per_ue_min": _rate(ho_failed, ue_minutes) or 0.0,
        "rlf_per_ue_min": _rate(rlf_events, ue_minutes) or 0.0,
        "ping_pong_per_ue_min": _rate(pp_events, ue_minutes) or 0.0,
        "ho_attempts_per_ue_min": _rate(ho_attempts, ue_minutes) or 0.0,
        "per_mode": _mode_breakdown(ues),
        "per_ue": {
            u.ue_id: {
                "mode": u.mode,
                "ho_attempts": u.ho_attempts,
                "ho_completed": u.ho_completed,
                "ho_failed": u.ho_failed,
                "outage_fraction": _rate(u.outage_steps + u.radio_outage_steps, u.active_steps),
            }
            for u in ues
        },
    }


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.fmean(present) if present else None


def compute_metrics(results: list[ScenarioResult]) -> dict[str, Any]:
    """Compute per-scenario metrics and their unweighted average.

    `results` is normally one policy's replay of every scenario in a suite.
    """
    per_scenario = [_scenario_metrics(r) for r in results]

    numeric_fields = [
        "ho_success_rate",
        "ho_failure_rate",
        "outage_fraction",
        "ho_interruption_fraction",
        "radio_outage_fraction",
        "goodput_ratio",
        "deadline_delivery_ratio",
        "delay_p50_ms",
        "delay_p95_ms",
        "delay_p99_ms",
        "ho_failures_per_ue_min",
        "rlf_per_ue_min",
        "ping_pong_per_ue_min",
        "ho_attempts_per_ue_min",
        "ping_pong_rate_per_completed_ho",
    ]
    count_fields = [
        "ho_attempts",
        "ho_completed",
        "ho_failed",
        "ho_ongoing_at_end",
        "rlf_events",
        "ping_pong_events",
        "deadline_misses",
        "undelivered_packets",
    ]

    aggregate: dict[str, Any] = {f: _mean([s[f] for s in per_scenario]) for f in numeric_fields}
    aggregate.update({f: sum(s[f] for s in per_scenario) for f in count_fields})
    aggregate["num_scenarios"] = len(per_scenario)

    return {"per_scenario": per_scenario, "aggregate": aggregate}
