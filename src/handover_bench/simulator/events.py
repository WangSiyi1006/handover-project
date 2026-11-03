"""Result records produced by one scenario replay (simulator/engine.py) and
consumed by metrics/compute.py. These are the "recomputed consequences" of a
policy's decisions, as opposed to the replayed trace inputs.
"""

from dataclasses import dataclass, field


@dataclass
class UEResult:
    ue_id: str
    mode: str
    ho_attempts: int = 0
    ho_completed: int = 0
    ho_failed: int = 0
    ho_ongoing_at_end: int = 0
    rlf_events: int = 0
    ping_pong_events: int = 0
    connected_steps: int = 0
    outage_steps: int = 0
    ho_interruption_steps: int = 0  # subset of outage_steps: phase == "executing"
    # Attached (idle/preparing) but serving SINR < Q_out this step: control
    # channel assumed undecodable, so nothing is delivered. Kept separate
    # from outage_steps (unattached) so upstream replay comparisons still
    # compare like with like; metrics.outage_fraction adds both.
    radio_outage_steps: int = 0
    active_steps: int = 0


@dataclass
class PacketRecord:
    packet_id: str
    ue_id: str
    arrival_time_ms: int
    size_bytes: int
    deadline_abs_ms: int
    delivered: bool
    delivery_time_ms: float | None  # within-step time the last bit was sent
    delivered_bytes: int


@dataclass
class ScenarioResult:
    scenario_id: str
    delta_t_ms: int
    ue_results: dict[str, UEResult] = field(default_factory=dict)
    packets: list[PacketRecord] = field(default_factory=list)
