"""Simulator, A3 baseline and scoring configuration.

Numerical values below (A3 offsets, timer durations, scoring weights and
epsilons) are the settings used for both the practice suite and the
assessment; see docs/standards.md and docs/assumptions.md.
"""

from dataclasses import dataclass, field

#: Version of the student observation/action schema (api.py), independent of
#: the simulator/package version.
SCHEMA_VERSION = "1.0"


@dataclass
class Config:
    """Configuration for one evaluation run.

    Timer fields ending in ``_ms`` are rounded to whole steps of the
    scenario's own replay clock (``Scenario.delta_t_ms``, from the spacing
    of radio.csv) when a scenario is replayed -- see
    simulator/engine.py:_steps. ``delta_t_ms`` here is only a default for
    code (e.g. baselines/a3.py in isolation) that has no scenario to read
    a clock from.
    """

    # --- Replay ---
    delta_t_ms: int = 100  # default step, used only where no scenario clock is available

    # --- A3 measurement event (3GPP TS 38.331, Sec. 5.5.4.4) ---
    # Entering: Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off
    # Leaving:  Mn + Ofn + Ocn + Hys < Mp + Ofp + Ocp + Off
    a3_hysteresis_db: float = 1.0
    a3_offset_db: float = 1.0
    a3_cell_offset_db: float = 0.0  # Ocn/Ocp, assumed equal across cells
    a3_object_offset_db: float = 0.0  # Ofn/Ofp, assumed equal across cells
    a3_ttt_ms: int = 320  # time-to-trigger

    # --- Radio link monitoring (approximated from SINR threshold; see
    # docs/assumptions.md for the gap to real in-sync/out-of-sync indications) ---
    q_out_db: float = -8.0
    q_in_db: float = -6.0
    n310: int = 10
    n311: int = 3
    t310_ms: int = 1000

    # --- Handover execution timing (experiment assumptions, not a fixed
    # 3GPP constant; see docs/assumptions.md) ---
    ho_prep_ms: int = 50
    ho_exec_ms: int = 40
    # RRC re-establishment after RLF: cell search/selection (T311), random
    # access and re-establishment signalling. Hundreds of ms to seconds in
    # practice, and it can fail to idle; 200 ms made RLF nearly as cheap as
    # a handover, so never handing over was barely penalised.
    rlf_recovery_ms: int = 1000
    min_time_of_stay_ms: int = 1000  # ping-pong monitoring window (MTS)

    # --- Scheduler / bandwidth sharing ---
    scheduler: str = "equal_share"  # only policy implemented in 0.1.0

    # --- Observation realism (see docs/assumptions.md) ---
    # Gap between a measurement being taken and a policy being allowed to
    # see it. 0 (default) preserves the original same-step behaviour;
    # instructors can raise this for realism without regenerating data.
    measurement_report_delay_ms: int = 0
    # Heuristic normaliser for the "load" fraction shown in observations
    # (associated-UE count / this value, clipped to 1.0) -- NOT a real PRB
    # or admission-control capacity figure.
    nominal_cell_capacity_ues: int = 50

    # --- Scoring weights (must sum to 1.0); see docs/metrics.md ---
    # The score is an A3-relative index relative to the A3 baseline (SPEC/
    # geomean-benchmark style): the baseline always scores exactly 100 by
    # construction, and a policy is scored as a weighted geometric mean of
    # its per-metric ratio to the baseline on the SAME scenarios. There is
    # no imposed cap, but the ideal KPI values give a finite upper bound
    # for each fixed suite. The index is not an academic percentage mark.
    # RLF is scored separately from HO failure: without it, a policy that
    # never hands over reaches good cells through RLF re-establishment at
    # no scored cost (see docs/metrics.md, "Never hand over").
    weight_goodput: float = 0.30
    weight_deadline_delivery: float = 0.20
    weight_outage: float = 0.20
    weight_rlf: float = 0.15
    weight_ho_failure: float = 0.05
    weight_ping_pong: float = 0.05
    weight_ho_attempts: float = 0.05

    # Additive smoothing so a per-metric ratio never divides by exactly
    # zero (e.g. a policy or the baseline with zero ping-pongs). Not a
    # scoring cap, but it sets how strongly near-zero differences are
    # magnified; the rationale for these values is in docs/metrics.md.
    score_ratio_epsilon: float = 0.02  # goodput, deadline delivery, outage ([0, 1] fractions)
    score_rate_epsilon: float = 0.05  # RLF, HO failure, ping-pong, attempts (per UE-minute; ~1 event per scenario)

    net_arch: list = field(default_factory=lambda: [64, 128, 64])  # reserved for ML policies

    def update(self, overrides: dict) -> "Config":
        """Return a copy of this config with the given fields overridden."""
        for key in overrides:
            if not hasattr(self, key):
                raise KeyError(f"Config has no attribute '{key}'")
        import dataclasses

        return dataclasses.replace(self, **overrides)
