"""NR A3 measurement-event baseline policy.

Implements the A3 entering/leaving condition and per-neighbour
time-to-trigger (TTT) from 3GPP TS 38.331, Sec. 5.5.4.4 (see
docs/standards.md for the pinned edition and clause mapping):

    Entering: Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off
    Leaving:  Mn + Ofn + Ocn + Hys < Mp + Ofp + Ocp + Off

This module only performs *measurement reporting and handover selection*
(deciding whether/when to request a handover). Preparation, execution,
failure, RLF and ping-pong accounting are the simulator's shared execution
model (simulator/engine.py) and are identical for every policy, including
this baseline -- per the "measurement reporting distinct from handover
selection and execution" requirement in docs/standards.md.

Adapted from the A3/TTT state-machine logic in kit-cel/HandoverOptimDRL
(MIT licence); see THIRD_PARTY_NOTICES.md. That reference tracks a single
best neighbour; this version tracks per-neighbour TTT state, as required by
docs/standards.md.
"""

from ..api import Action, Observation


class A3Policy:
    """Reference NR A3 handover policy (one instance per UE)."""

    def __init__(self) -> None:
        self._hys = 1.0
        self._off = 1.0
        self._ofn = self._ofp = 0.0
        self._ocn = self._ocp = 0.0
        self._ttt_ms = 320
        self._flags: dict[str, bool] = {}
        self._ttt_started_at: dict[str, int] = {}

    def reset(self, config: dict) -> None:
        self._hys = config.get("a3_hysteresis_db", 1.0)
        self._off = config.get("a3_offset_db", 1.0)
        self._ofn = self._ofp = config.get("a3_object_offset_db", 0.0)
        self._ocn = self._ocp = config.get("a3_cell_offset_db", 0.0)
        self._ttt_ms = max(0, config.get("a3_ttt_ms", 320))
        self._flags = {}
        self._ttt_started_at = {}

    def decide(self, observation: Observation) -> Action:
        serving_rsrp = observation.get("serving_rsrp_dbm")
        time_ms = observation["time_ms"]
        candidates = observation.get("candidates", [])
        stay: Action = {"action": "stay", "target_cell_id": None}

        if serving_rsrp is None:
            self._flags.clear()
            self._ttt_started_at.clear()
            return stay

        seen = set()
        expired: list[tuple[float, str]] = []
        for cand in candidates:
            cid = cand["cell_id"]
            rsrp = cand["rsrp_dbm"]
            seen.add(cid)

            was_entering = self._flags.get(cid, False)
            entering_now = (
                rsrp + self._ofn + self._ocn - self._hys
                > serving_rsrp + self._ofp + self._ocp + self._off
            )
            leaving_now = (
                rsrp + self._ofn + self._ocn + self._hys
                < serving_rsrp + self._ofp + self._ocp + self._off
            )
            if entering_now:
                condition = True
            elif leaving_now:
                condition = False
            else:
                condition = was_entering  # inside hysteresis dead-zone: hold
            self._flags[cid] = condition

            if condition:
                # The entering sample starts the timer at elapsed time 0.
                # Use the replay clock rather than a rounded sample count:
                # a non-divisible duration must never trigger prematurely.
                started_at = self._ttt_started_at.setdefault(cid, time_ms)
                if time_ms - started_at >= self._ttt_ms:
                    expired.append((rsrp, cid))
            else:
                self._ttt_started_at.pop(cid, None)

        # Drop timer/condition state for cells no longer reported.
        for cid in list(self._flags):
            if cid not in seen:
                self._flags.pop(cid, None)
                self._ttt_started_at.pop(cid, None)

        if not expired:
            return stay

        # Multiple neighbours' TTT can expire the same step; pick the
        # strongest, matching the A3 event's intent (deterministic tie-break
        # per docs/assumptions.md).
        expired.sort(key=lambda item: item[0], reverse=True)
        target_rsrp, target_cell = expired[0]
        self._ttt_started_at.pop(target_cell, None)
        self._flags[target_cell] = False
        return {"action": "request_handover", "target_cell_id": target_cell}
