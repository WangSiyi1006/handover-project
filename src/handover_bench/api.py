"""Student algorithm contract (versioned independently of the simulator).

Students submit a single ``algorithm.py`` file defining a ``StudentPolicy``
class matching this interface. The simulator owns metric calculation and
network state; the policy only returns a decision each time it is consulted.

One ``StudentPolicy`` instance is created per UE and reset at the start of
each scenario (see README.md) -- policies may keep history across
calls for the same UE, but never see future observations, and never see
other UEs' private state.
"""

from typing import Protocol, TypedDict

from .config import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "Observation", "CandidateCell", "Action", "StudentPolicy"]


class CandidateCell(TypedDict, total=False):
    cell_id: str
    rsrp_dbm: float
    rs_sinr_db: float  # optional; present only if the scenario provides it
    eligible: bool  # meets the A3-style measurement thresholds this step


class Observation(TypedDict, total=False):
    schema_version: str
    time_ms: int  # current decision time (when you must act)
    measurement_time_ms: int  # when the shown measurement was actually taken;
    # <= time_ms, lagging it by Config.measurement_report_delay_ms. Do not
    # assume measurement_time_ms == time_ms -- a nonzero reporting delay
    # means "candidates"/"serving_rsrp_dbm" reflect the network as it was at
    # measurement_time_ms, not "now". You may retain past observations
    # yourself (this policy instance persists across steps for this UE) to
    # derive velocity/acceleration/trend features; the simulator does not
    # pre-compute or hand you kinematic derivatives.
    ue_id: str
    serving_cell_id: str | None
    serving_rsrp_dbm: float | None
    candidates: list[CandidateCell]
    ho_phase: str  # one of: "idle", "preparing", "executing", "rlf_recovery"
    recent_events: list[dict]  # bounded history of this UE's past outcomes

    # Optional observations (only present when the scenario/config enables
    # them -- check `has_position`/`has_load` before relying on them).
    has_position: bool
    x_m: float
    y_m: float
    z_m: float  # altitude above ground, metres (0.0 for ground-bound modes)
    speed_mps: float
    heading_deg: float
    has_load: bool
    # Heuristic association-count-based load fraction in [0, 1] from the
    # PREVIOUS replay step (this step's own counts aren't final until every
    # UE has decided) -- not a real PRB/admission-control figure; see
    # README.md. `None` if the cell had no prior observation.
    serving_cell_load: float | None
    candidate_cell_loads: dict[str, float]
    queue_backlog_bytes: int  # this UE's own undelivered-packet backlog


class Action(TypedDict, total=False):
    action: str  # "stay" or "request_handover"
    target_cell_id: str | None


class StudentPolicy(Protocol):
    """Interface every submitted algorithm.py must implement."""

    def reset(self, config: dict) -> None:
        """Called once per UE at the start of each scenario."""
        ...

    def decide(self, observation: Observation) -> Action:
        """Called once per UE at each policy step while the UE is idle.

        Must return {"action": "stay"} or
        {"action": "request_handover", "target_cell_id": <a cell_id from
        observation["candidates"]>}. Invalid or missing target cells are
        treated as "stay" by the simulator.
        """
        ...


class ExampleStayPolicy:
    """Minimal reference implementation: never requests a handover."""

    def reset(self, config: dict) -> None:
        pass

    def decide(self, observation: Observation) -> Action:
        return {"action": "stay", "target_cell_id": None}
