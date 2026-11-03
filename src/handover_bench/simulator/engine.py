"""Shared execution and failure model, driven by per-UE policy decisions.

This module owns everything a policy must not touch directly: association,
handover preparation/execution timing, radio-link monitoring (approximated
from SINR -- see docs/assumptions.md), RLF recovery, ping-pong accounting,
cell load and packet delivery. Every policy (the A3 baseline included) is
replayed through this same engine, so scores reflect only the policy's
"stay"/"request_handover" decisions.
"""

from bisect import bisect_right
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from ..api import StudentPolicy
from ..config import SCHEMA_VERSION, Config
from .events import PacketRecord, ScenarioResult, UEResult
from .scenario import Scenario
from .scheduler import equal_share_bits


class StepCounter:
    """Idempotent-start countdown counter (see baselines/a3.py header for
    the 3GPP timer/counter semantics this mirrors)."""

    def __init__(self, max_steps: int) -> None:
        self.max_steps = max(1, max_steps)
        self.cnt = 0
        self.active = False
        self.done = False

    def start(self) -> None:
        if not self.active and not self.done:
            self.active = True
            self.cnt = 0

    def step(self) -> None:
        if self.active:
            self.cnt += 1
            if self.cnt >= self.max_steps:
                self.active = False
                self.done = True

    def reset(self) -> None:
        self.active = False
        self.done = False
        self.cnt = 0

    @property
    def pending(self) -> bool:
        return self.active or self.done


@dataclass
class _QueuedPacket:
    packet_id: str
    arrival_time_ms: int
    size_bytes: int
    deadline_abs_ms: int
    remaining_bits: float


@dataclass
class _UEState:
    ue_id: str
    mode: str
    policy: StudentPolicy
    phase: str = "searching"  # searching | idle | preparing | executing | rlf_recovery
    serving_cell: str | None = None
    target_cell: str | None = None
    out_of_sync: bool = False
    n310: StepCounter = field(default=None)  # type: ignore[assignment]
    n311: StepCounter = field(default=None)  # type: ignore[assignment]
    t310: StepCounter = field(default=None)  # type: ignore[assignment]
    rlfr: StepCounter = field(default=None)  # type: ignore[assignment]
    ho_prep: StepCounter = field(default=None)  # type: ignore[assignment]
    ho_exec: StepCounter = field(default=None)  # type: ignore[assignment]
    mts_active: bool = False
    mts_remaining: int = 0
    queue: deque = field(default_factory=deque)
    recent_events: list = field(default_factory=list)
    result: UEResult = field(default=None)  # type: ignore[assignment]


def _steps(ms: int, delta_t_ms: int) -> int:
    """Round a millisecond duration to whole steps of the *scenario's own*
    delta_t_ms (which need not equal Config.delta_t_ms -- the scenario's
    replay clock is authoritative; see docs/assumptions.md)."""
    return max(1, round(ms / delta_t_ms))


def _steps_allow_zero(ms: int, delta_t_ms: int) -> int:
    """Like `_steps`, but 0ms rounds to 0 steps (used for the reporting
    delay, where "no delay" must mean exactly that)."""
    return max(0, round(ms / delta_t_ms))


def _make_counters(cfg: Config, delta_t_ms: int) -> dict[str, StepCounter]:
    return {
        "n310": StepCounter(cfg.n310),
        "n311": StepCounter(cfg.n311),
        "t310": StepCounter(_steps(cfg.t310_ms, delta_t_ms)),
        "rlfr": StepCounter(_steps(cfg.rlf_recovery_ms, delta_t_ms)),
        "ho_prep": StepCounter(_steps(cfg.ho_prep_ms, delta_t_ms)),
        "ho_exec": StepCounter(_steps(cfg.ho_exec_ms, delta_t_ms)),
    }


def _record_event(state: _UEState, kind: str, t_ms: int) -> None:
    state.recent_events.append({"event": kind, "time_ms": t_ms})
    if len(state.recent_events) > 5:
        state.recent_events.pop(0)


def _best_candidate(measurements: dict, q_in_db: float) -> str | None:
    best_cell, best_sinr = None, None
    for cell_id, m in measurements.items():
        sinr = m.rs_sinr_db if m.rs_sinr_db is not None else m.rsrp_dbm
        if sinr is not None and sinr > q_in_db and (best_sinr is None or sinr > best_sinr):
            best_cell, best_sinr = cell_id, sinr
    return best_cell


def _build_observation(
    scenario: Scenario,
    state: _UEState,
    t_ms: int,
    delayed_t_ms: int,
    observed_measurements: dict,
    cell_ue_counts: dict[str, int],
    nominal_cell_capacity_ues: int,
) -> dict:
    """`observed_measurements` is what the policy is allowed to see this
    step -- already shifted by Config.measurement_report_delay_ms, i.e. it
    may lag the engine's own (undelayed) ground truth used for radio-link
    monitoring and packet delivery. `cell_ue_counts` is the association
    count from the *previous* replay step (this step's counts are not yet
    fully known while UEs are still deciding one at a time); see
    docs/assumptions.md."""
    serving_rsrp = None
    if state.serving_cell is not None and state.serving_cell in observed_measurements:
        serving_rsrp = observed_measurements[state.serving_cell].rsrp_dbm

    candidates = [
        {
            "cell_id": cid,
            "rsrp_dbm": m.rsrp_dbm,
            "rs_sinr_db": m.rs_sinr_db,
            "eligible": cid != state.serving_cell,
        }
        for cid, m in observed_measurements.items()
        if cid != state.serving_cell
    ]

    def _load(cell_id: str) -> float:
        return min(1.0, cell_ue_counts.get(cell_id, 0) / nominal_cell_capacity_ues)

    mob = scenario.mobility.get(state.ue_id, {}).get(t_ms)
    obs = {
        "schema_version": SCHEMA_VERSION,
        "time_ms": t_ms,
        "measurement_time_ms": delayed_t_ms,
        "ue_id": state.ue_id,
        "serving_cell_id": state.serving_cell,
        "serving_rsrp_dbm": serving_rsrp,
        "candidates": candidates,
        "ho_phase": state.phase,
        "recent_events": list(state.recent_events),
        "has_position": mob is not None,
        "has_load": True,
        "serving_cell_load": _load(state.serving_cell) if state.serving_cell else None,
        "candidate_cell_loads": {c["cell_id"]: _load(c["cell_id"]) for c in candidates},
        "queue_backlog_bytes": int(sum(p.remaining_bits for p in state.queue) // 8),
    }
    if mob is not None:
        obs.update(
            {
                "x_m": mob.x_m,
                "y_m": mob.y_m,
                "z_m": mob.z_m,
                "speed_mps": mob.speed_mps,
                "heading_deg": mob.heading_deg,
            }
        )
    return obs


def run_scenario(
    scenario: Scenario,
    policy_factory: Callable[[], StudentPolicy],
    config: Config | None = None,
) -> ScenarioResult:
    """Replay `scenario` with one fresh policy instance per UE."""
    cfg = config or Config()
    policy_config = {
        "delta_t_ms": scenario.delta_t_ms,
        "a3_hysteresis_db": cfg.a3_hysteresis_db,
        "a3_offset_db": cfg.a3_offset_db,
        "a3_cell_offset_db": cfg.a3_cell_offset_db,
        "a3_object_offset_db": cfg.a3_object_offset_db,
        "a3_ttt_ms": cfg.a3_ttt_ms,
    }
    mts_steps = _steps(cfg.min_time_of_stay_ms, scenario.delta_t_ms)
    delay_steps = _steps_allow_zero(cfg.measurement_report_delay_ms, scenario.delta_t_ms)

    ue_states: dict[str, _UEState] = {}
    # Step t_ms covers the interval [t_ms, t_ms + delta_t_ms). A packet is
    # queued in the step containing its arrival and can be served from its
    # own arrival time onward within that step (see the delivery loop), so
    # delay is not quantised to the replay step.
    packets_by_arrival: dict[int, list] = {}
    for p in scenario.traffic:
        idx = bisect_right(scenario.time_grid_ms, p.arrival_time_ms) - 1
        step_ms = scenario.time_grid_ms[min(max(idx, 0), len(scenario.time_grid_ms) - 1)]
        packets_by_arrival.setdefault(step_ms, []).append(p)

    result = ScenarioResult(scenario_id=scenario.scenario_id, delta_t_ms=scenario.delta_t_ms)
    # Association counts from the previous step, exposed as "load" in this
    # step's observations (this step's own counts aren't fully known until
    # every UE has decided -- see _build_observation).
    prev_cell_ue_counts: dict[str, int] = {}

    for t_idx, t_ms in enumerate(scenario.time_grid_ms):
        step_connected: dict[str, tuple[str, float]] = {}  # ue_id -> (cell_id, sinr_db), deliverable
        step_attached: dict[str, str] = {}  # ue_id -> cell_id, incl. radio outage (for load)
        delayed_t_ms = scenario.time_grid_ms[max(0, t_idx - delay_steps)]

        for ue_id in scenario.ue_ids:
            mob = scenario.mobility.get(ue_id, {}).get(t_ms)
            present = mob is not None and mob.active
            state = ue_states.get(ue_id)

            if not present:
                continue
            if state is None:
                policy = policy_factory()
                policy.reset(dict(policy_config))
                counters = _make_counters(cfg, scenario.delta_t_ms)
                state = _UEState(
                    ue_id=ue_id,
                    mode=scenario.ue_mode.get(ue_id, "unknown"),
                    policy=policy,
                    result=UEResult(ue_id=ue_id, mode=scenario.ue_mode.get(ue_id, "unknown")),
                    **counters,
                )
                ue_states[ue_id] = state

            measurements = {m.cell_id: m for m in scenario.radio.get(ue_id, {}).get(t_ms, [])}
            delayed_measurements = (
                measurements
                if delay_steps == 0
                else {
                    m.cell_id: m
                    for m in scenario.radio.get(ue_id, {}).get(delayed_t_ms, [])
                }
            )
            state.result.active_steps += 1

            for c in (state.n310, state.n311, state.t310, state.rlfr, state.ho_prep, state.ho_exec):
                c.step()
            if state.mts_active:
                state.mts_remaining -= 1
                if state.mts_remaining <= 0:
                    state.mts_active = False

            if state.phase in ("idle", "preparing") and state.serving_cell is not None:
                m = measurements.get(state.serving_cell)
                sinr = m.rs_sinr_db if (m and m.rs_sinr_db is not None) else (m.rsrp_dbm if m else None)
                if sinr is None or sinr < cfg.q_out_db:
                    state.out_of_sync = True
                elif sinr > cfg.q_in_db:
                    state.out_of_sync = False
                if state.out_of_sync:
                    state.n311.reset()
                    if not state.t310.pending:
                        state.n310.start()
                else:
                    state.n310.reset()
                    if state.t310.pending:
                        state.n311.start()
            else:
                state.n310.reset()
                state.n311.reset()
                state.t310.reset()

            rlf_triggered = False
            if state.n310.done:
                state.n310.reset()
                state.n311.reset()
                state.t310.start()
            elif state.n311.done:
                state.n310.reset()
                state.n311.reset()
                state.t310.reset()
            elif state.t310.done:
                state.t310.reset()
                state.n310.reset()
                state.n311.reset()
                rlf_triggered = True

            if rlf_triggered and state.phase in ("idle", "preparing", "executing"):
                if state.phase == "preparing":
                    state.result.ho_failed += 1
                    state.ho_prep.reset()
                elif state.phase == "executing":
                    state.result.ho_failed += 1
                    state.ho_exec.reset()
                state.result.rlf_events += 1
                state.phase = "rlf_recovery"
                state.serving_cell = None
                state.target_cell = None
                state.rlfr.reset()
                state.rlfr.start()
                _record_event(state, "rlf", t_ms)

            if state.phase == "searching" or state.phase == "rlf_recovery":
                candidate = _best_candidate(measurements, cfg.q_in_db)
                if state.phase == "rlf_recovery":
                    if state.rlfr.done:
                        if candidate is not None:
                            state.serving_cell = candidate
                            state.phase = "idle"
                            state.rlfr.reset()
                            state.out_of_sync = False
                            _record_event(state, "rlf_recovered", t_ms)
                        else:
                            state.rlfr.reset()
                            state.rlfr.start()
                elif candidate is not None:
                    state.serving_cell = candidate
                    state.phase = "idle"

            elif state.phase == "preparing" and not rlf_triggered:
                if state.ho_prep.done:
                    state.ho_prep.reset()
                    if state.t310.active:
                        state.result.ho_failed += 1
                        state.result.rlf_events += 1
                        state.phase = "rlf_recovery"
                        state.serving_cell = None
                        state.target_cell = None
                        state.rlfr.reset()
                        state.rlfr.start()
                        _record_event(state, "ho_failed", t_ms)
                    else:
                        state.ho_exec.reset()
                        state.ho_exec.start()
                        state.phase = "executing"
                        state.serving_cell = None  # service interrupted during execution
                        if state.mts_active:
                            state.result.ping_pong_events += 1
                            _record_event(state, "ping_pong", t_ms)
                        state.mts_active = True
                        state.mts_remaining = mts_steps

            elif state.phase == "executing":
                if state.ho_exec.done:
                    state.ho_exec.reset()
                    target = state.target_cell
                    m = measurements.get(target) if target else None
                    sinr = m.rs_sinr_db if (m and m.rs_sinr_db is not None) else (m.rsrp_dbm if m else None)
                    if target is None or sinr is None or sinr < cfg.q_out_db:
                        state.result.ho_failed += 1
                        state.result.rlf_events += 1
                        state.phase = "rlf_recovery"
                        state.serving_cell = None
                        state.target_cell = None
                        state.rlfr.reset()
                        state.rlfr.start()
                        _record_event(state, "ho_failed", t_ms)
                    else:
                        state.serving_cell = target
                        state.target_cell = None
                        state.phase = "idle"
                        state.out_of_sync = False
                        state.result.ho_completed += 1
                        _record_event(state, "ho_completed", t_ms)

            if state.phase == "idle":
                obs = _build_observation(
                    scenario,
                    state,
                    t_ms,
                    delayed_t_ms,
                    delayed_measurements,
                    prev_cell_ue_counts,
                    cfg.nominal_cell_capacity_ues,
                )
                action = state.policy.decide(obs)
                target = action.get("target_cell_id") if isinstance(action, dict) else None
                if (
                    isinstance(action, dict)
                    and action.get("action") == "request_handover"
                    and target in delayed_measurements
                    and target != state.serving_cell
                ):
                    state.result.ho_attempts += 1
                    state.target_cell = target
                    state.phase = "preparing"
                    state.ho_prep.reset()
                    state.ho_prep.start()
                    _record_event(state, "ho_attempt", t_ms)

            connected = state.phase in ("idle", "preparing") and state.serving_cell is not None
            if connected:
                state.result.connected_steps += 1
                step_attached[ue_id] = state.serving_cell
                m = measurements.get(state.serving_cell)
                sinr = m.rs_sinr_db if (m and m.rs_sinr_db is not None) else (m.rsrp_dbm if m else -30.0)
                if sinr < cfg.q_out_db:
                    # Still attached (N310/T310 may be running), but below
                    # Q_out the control channel is assumed undecodable: no
                    # delivery this step. Staying on a fading cell must cost
                    # service, not only an eventual RLF.
                    state.result.radio_outage_steps += 1
                else:
                    step_connected[ue_id] = (state.serving_cell, sinr)
            else:
                state.result.outage_steps += 1
                if state.phase == "executing":
                    state.result.ho_interruption_steps += 1

            for pkt in packets_by_arrival.get(t_ms, []):
                if pkt.ue_id == ue_id:
                    state.queue.append(
                        _QueuedPacket(
                            packet_id=pkt.packet_id,
                            arrival_time_ms=pkt.arrival_time_ms,
                            size_bytes=pkt.size_bytes,
                            deadline_abs_ms=pkt.arrival_time_ms + pkt.deadline_ms,
                            remaining_bits=pkt.size_bytes * 8,
                        )
                    )

        cell_ue_counts: dict[str, int] = {}
        for cell_id in step_attached.values():
            cell_ue_counts[cell_id] = cell_ue_counts.get(cell_id, 0) + 1
        prev_cell_ue_counts = cell_ue_counts

        by_cell: dict[str, dict[str, float]] = {}
        for ue_id, (cell_id, sinr) in step_connected.items():
            state = ue_states[ue_id]
            if state.queue:
                by_cell.setdefault(cell_id, {})[ue_id] = sinr

        for cell_id, ue_sinr in by_cell.items():
            cell = scenario.cells[cell_id]
            bits_per_ue = equal_share_bits(cell.bandwidth_hz, scenario.delta_t_ms, ue_sinr)
            step_end_ms = t_ms + scenario.delta_t_ms
            for ue_id, budget_bits in bits_per_ue.items():
                state = ue_states[ue_id]
                # Serve the FIFO queue at a constant rate across the step,
                # never before a packet's own arrival; the delivery time is
                # when its last bit is sent, not the step boundary.
                bits_per_ms = budget_bits / scenario.delta_t_ms
                cursor_ms = float(t_ms)
                while bits_per_ms > 0 and state.queue:
                    pkt = state.queue[0]
                    start_ms = max(cursor_ms, float(pkt.arrival_time_ms))
                    if start_ms >= step_end_ms:
                        break
                    finish_ms = start_ms + pkt.remaining_bits / bits_per_ms
                    if finish_ms <= step_end_ms:
                        cursor_ms = finish_ms
                        result.packets.append(
                            PacketRecord(
                                packet_id=pkt.packet_id,
                                ue_id=ue_id,
                                arrival_time_ms=pkt.arrival_time_ms,
                                size_bytes=pkt.size_bytes,
                                deadline_abs_ms=pkt.deadline_abs_ms,
                                delivered=True,
                                delivery_time_ms=round(finish_ms, 3),
                                delivered_bytes=pkt.size_bytes,
                            )
                        )
                        state.queue.popleft()
                    else:
                        pkt.remaining_bits -= (step_end_ms - start_ms) * bits_per_ms
                        break

    for state in ue_states.values():
        if state.phase in ("preparing", "executing"):
            state.result.ho_ongoing_at_end += 1
        for pkt in state.queue:
            delivered_bytes = pkt.size_bytes - int(pkt.remaining_bits // 8)
            result.packets.append(
                PacketRecord(
                    packet_id=pkt.packet_id,
                    ue_id=state.ue_id,
                    arrival_time_ms=pkt.arrival_time_ms,
                    size_bytes=pkt.size_bytes,
                    deadline_abs_ms=pkt.deadline_abs_ms,
                    delivered=False,
                    delivery_time_ms=None,
                    delivered_bytes=max(0, delivered_bytes),
                )
            )
        result.ue_results[state.ue_id] = state.result

    return result
