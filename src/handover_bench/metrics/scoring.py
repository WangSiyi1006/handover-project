"""A3-relative score (weighted geometric mean).

The A3 baseline scores 100 against itself on the same scenario suite.
There is no imposed cap, but the KPI ranges and positive smoothing create
a finite mathematical upper bound for each fixed suite. Substituting
goodput = deadline delivery = 1 and all five lower-is-better KPIs = 0
gives an optimistic bound; joint attainability is not guaranteed.
KPI regressions reduce the index. The index is not an academic mark.

Weights and epsilons are identical for practice and private assessment.

Only handover failures per UE-minute are scored; success rate is reported
for information. Displayed success/failure ratios can have different
denominators when attempts remain unfinished.
"""

import math
from typing import Any

from ..config import Config


def _get(aggregate: dict[str, Any], key: str) -> float:
    value = aggregate.get(key)
    return float(value) if value is not None else 0.0


def _higher_is_better_ratio(student_value: float, baseline_value: float, eps: float) -> float:
    """> 1 when the student beats the baseline on a "more is better"
    metric (e.g. goodput), < 1 when it falls short. Never <= 0."""
    return (student_value + eps) / (baseline_value + eps)


def _lower_is_better_ratio(student_value: float, baseline_value: float, eps: float) -> float:
    """> 1 when the student beats the baseline on a "less is better"
    metric (e.g. handover failures per UE-minute). Never <= 0."""
    return (baseline_value + eps) / (student_value + eps)


def compute_score(
    student_aggregate: dict[str, Any],
    baseline_aggregate: dict[str, Any],
    config: Config | None = None,
) -> dict[str, Any]:
    """Score `student_aggregate` (from metrics.compute_metrics) relative to
    `baseline_aggregate` (normally the A3 baseline's aggregate on the same
    scenario suite). Passing the same aggregate for both always yields
    exactly 100.0 -- useful as a sanity check and as the baseline's own
    displayed score."""
    cfg = config or Config()
    r_eps = cfg.score_ratio_epsilon
    k_eps = cfg.score_rate_epsilon

    ratios = {
        "goodput": (
            _higher_is_better_ratio(
                _get(student_aggregate, "goodput_ratio"),
                _get(baseline_aggregate, "goodput_ratio"),
                r_eps,
            ),
            cfg.weight_goodput,
        ),
        "deadline_delivery": (
            _higher_is_better_ratio(
                _get(student_aggregate, "deadline_delivery_ratio"),
                _get(baseline_aggregate, "deadline_delivery_ratio"),
                r_eps,
            ),
            cfg.weight_deadline_delivery,
        ),
        # Outage is compared directly (lower is better), not as 1 - outage:
        # near 1, "connectivity" ratios compressed a 4x outage increase to
        # a ~1% factor while the near-zero event rates swung by >20%.
        "outage": (
            _lower_is_better_ratio(
                _get(student_aggregate, "outage_fraction"),
                _get(baseline_aggregate, "outage_fraction"),
                r_eps,
            ),
            cfg.weight_outage,
        ),
        "rlf": (
            _lower_is_better_ratio(
                _get(student_aggregate, "rlf_per_ue_min"),
                _get(baseline_aggregate, "rlf_per_ue_min"),
                k_eps,
            ),
            cfg.weight_rlf,
        ),
        "ho_failure": (
            _lower_is_better_ratio(
                _get(student_aggregate, "ho_failures_per_ue_min"),
                _get(baseline_aggregate, "ho_failures_per_ue_min"),
                k_eps,
            ),
            cfg.weight_ho_failure,
        ),
        "ping_pong": (
            _lower_is_better_ratio(
                _get(student_aggregate, "ping_pong_per_ue_min"),
                _get(baseline_aggregate, "ping_pong_per_ue_min"),
                k_eps,
            ),
            cfg.weight_ping_pong,
        ),
        "ho_attempts": (
            _lower_is_better_ratio(
                _get(student_aggregate, "ho_attempts_per_ue_min"),
                _get(baseline_aggregate, "ho_attempts_per_ue_min"),
                k_eps,
            ),
            cfg.weight_ho_attempts,
        ),
    }

    total_weight = sum(w for _, w in ratios.values())
    log_score = sum(w * math.log(ratio) for ratio, w in ratios.values()) / total_weight
    score = 100.0 * math.exp(log_score)
    components = {}
    for name, (ratio, weight) in ratios.items():
        contribution = weight * math.log(ratio) / total_weight
        components[name] = {
            "direction": "higher" if name in {"goodput", "deadline_delivery"} else "lower",
            "normalized_weight": weight / total_weight,
            "weighted_log_contribution": contribution,
            "score_factor": math.exp(contribution),
            "effect": "gain" if contribution > 0 else "regression" if contribution < 0 else "unchanged",
        }

    return {
        "score": round(score, 2),
        "ratios": {name: round(ratio, 4) for name, (ratio, _) in ratios.items()},
        "weights": {name: w for name, (_, w) in ratios.items()},
        # These retain full precision: 100 * product(score_factor) reproduces
        # the unrounded score. Negative log contributions are KPI penalties,
        # not additive deductions in index points.
        "components": components,
    }
