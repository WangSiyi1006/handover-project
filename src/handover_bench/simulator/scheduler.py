"""Bandwidth-sharing scheduler.

Only "equal_share" is implemented in 0.1.0: a cell's bandwidth is split
equally, each step, among the UEs currently associated with it that have
outstanding backlog. This is the one documented, deterministic scheduler
required by the initial scope; see docs/assumptions.md for its limitations
(no proportional fairness, no QoS classes).
"""

import math


def equal_share_bits(
    bandwidth_hz: float,
    delta_t_ms: int,
    ue_sinr_db: dict[str, float],
) -> dict[str, float]:
    """Split `bandwidth_hz` equally among the UEs in `ue_sinr_db` (those
    with backlog this step) and return bits deliverable per UE this step,
    via Shannon capacity at each UE's own SINR."""
    n = len(ue_sinr_db)
    if n == 0:
        return {}
    share_hz = bandwidth_hz / n
    dt_s = delta_t_ms / 1000.0
    bits = {}
    for ue_id, sinr_db in ue_sinr_db.items():
        sinr_lin = 10 ** (sinr_db / 10)
        rate_bps = share_hz * math.log2(1 + max(sinr_lin, 0.0))
        bits[ue_id] = rate_bps * dt_s
    return bits
