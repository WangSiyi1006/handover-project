# ======================= TEAM DETAILS (fill in before submitting) =======================
# Brightspace group:
# Members (name, student number):
#   1.
#   2.
#   3.
# ==========================================================================================
"""Rule-based, load-aware handover policy (no machine learning).

Idea: A3 is slow (>2 dB margin + 320 ms TTT) and load-blind. This policy
  1. smooths RSRP with an EMA per cell (suppresses fast-fading noise),
  2. adds a load penalty so busy cells look worse (spreads UEs over cells),
  3. needs the target to be better by a margin for a few consecutive steps
     (a short, own "time-to-trigger"),
  4. lowers the margin / TTT when the serving link is weak or falling
     (leave *before* RLF),
  5. refuses targets whose SINR is too low (avoids handover failure),
  6. enforces a minimum dwell time after each request (avoids ping-pong).

All tunable numbers are the constants below; tune them on a subset of the
practice scenarios and validate on the rest.
"""

# ----------------------------- tunable parameters -----------------------------
EMA_ALPHA = 0.6            # weight of the newest RSRP sample (1.0 = no smoothing)
BASE_MARGIN_DB = 2.0       # target must beat serving by this much (after load penalty)
MIN_MARGIN_DB = 0.5        # margin floor when the serving link is weak/falling
NEED_STREAK = 2            # consecutive steps the condition must hold (normal case)
LOAD_WEIGHT_DB = 10.0      # dB penalty per 1.0 of cell load (load = UEs / 50)
MIN_TARGET_SINR_DB = -2.0  # ignore candidates with SINR below this (fail threshold is -8)
WEAK_RSRP_DBM = -105.0     # serving smoothed RSRP below this = "weak"
EMERGENCY_RSRP_DBM = -110.0  # below this: act immediately
FALLING_SLOPE_DB = -0.7    # smoothed RSRP change per step that counts as "falling"
TREND_BONUS_DB = 0.7       # margin reduction when serving is falling
WEAK_BONUS_DB = 0.8        # margin reduction when serving is weak
MIN_DWELL_MS = 1200        # min time between two requests (ping-pong is < 1000 ms)
EMERGENCY_DWELL_MS = 600   # shorter dwell allowed in an emergency
STALE_STEPS = 5            # drop a cell's filter if unseen for this many steps

_DEBUG = False             # set True while developing to see exceptions

_STAY = {"action": "stay"}


class StudentPolicy:
    def __init__(self):
        self._init_state(200)

    def reset(self, config: dict) -> None:
        dt = 200
        try:
            dt = int(config.get("delta_t_ms", 200))
        except Exception:
            pass
        self._init_state(dt)

    def _init_state(self, dt):
        # Per-UE state only (instance attributes, never shared between UEs).
        self._dt = max(1, dt)
        self._ema = {}          # cell_id -> [smoothed_rsrp, last_seen_time_ms]
        self._streak = {}       # cell_id -> consecutive steps the trigger held
        self._last_req_t = None  # time of our last handover request

    # ------------------------------------------------------------------
    def decide(self, observation: dict) -> dict:
        # An exception would invalidate the whole graded run, so fall back
        # to "stay" unless we are debugging.
        try:
            return self._decide(observation)
        except Exception:
            if _DEBUG:
                raise
            return dict(_STAY)

    # ------------------------------------------------------------------
    def _smooth(self, cell_id, raw, t):
        """Update the EMA of one cell; return (new_value, previous_value|None)."""
        entry = self._ema.get(cell_id)
        if entry is None or t - entry[1] > STALE_STEPS * self._dt:
            self._ema[cell_id] = [raw, t]
            return raw, None
        prev = entry[0]
        new = EMA_ALPHA * raw + (1.0 - EMA_ALPHA) * prev
        self._ema[cell_id] = [new, t]
        return new, prev

    @staticmethod
    def _load_of(loads, index, cell_id):
        # candidate_cell_loads may be a dict {cell_id: load} or a list aligned
        # with `candidates`. Check src/handover_bench/api.py to confirm.
        try:
            if isinstance(loads, dict):
                return float(loads.get(cell_id, 0.0))
            if isinstance(loads, (list, tuple)) and index < len(loads):
                return float(loads[index])
        except Exception:
            pass
        return 0.0

    def _decide(self, obs):
        t = obs["time_ms"]
        serving = obs["serving_cell_id"]
        cands = obs.get("candidates") or []

        # ---- smoothed serving signal and its trend ----
        s_f, s_prev = self._smooth(serving, float(obs["serving_rsrp_dbm"]), t)
        slope = 0.0 if s_prev is None else s_f - s_prev
        s_load = float(obs.get("serving_cell_load") or 0.0)
        s_adj = s_f - LOAD_WEIGHT_DB * s_load

        weak = s_f < WEAK_RSRP_DBM
        falling = slope < FALLING_SLOPE_DB
        emergency = s_f < EMERGENCY_RSRP_DBM

        margin = BASE_MARGIN_DB
        if falling:
            margin -= TREND_BONUS_DB
        if weak:
            margin -= WEAK_BONUS_DB
        margin = max(MIN_MARGIN_DB, margin)
        need = 1 if emergency else NEED_STREAK

        # ---- evaluate every candidate (always, to keep filters/streaks fresh) ----
        loads = obs.get("candidate_cell_loads")
        seen = set()
        best_id, best_adj = None, None
        for i, c in enumerate(cands):
            cid = c.get("cell_id")
            rsrp = c.get("rsrp_dbm")
            sinr = c.get("rs_sinr_db")
            if cid is None or cid == serving or rsrp is None:
                continue
            seen.add(cid)
            c_f, _ = self._smooth(cid, float(rsrp), t)
            c_load = self._load_of(loads, i, cid)
            c_adj = c_f - LOAD_WEIGHT_DB * c_load

            ok_sinr = sinr is not None and float(sinr) >= MIN_TARGET_SINR_DB
            if ok_sinr and (c_adj - s_adj) > margin:
                self._streak[cid] = self._streak.get(cid, 0) + 1
                if self._streak[cid] >= need and (best_adj is None or c_adj > best_adj):
                    best_id, best_adj = cid, c_adj
            else:
                self._streak[cid] = 0

        # forget streaks of cells that vanished from the candidate list
        for cid in list(self._streak):
            if cid not in seen:
                del self._streak[cid]

        if best_id is None:
            return dict(_STAY)

        # ---- minimum dwell since our last request (ping-pong guard) ----
        dwell = EMERGENCY_DWELL_MS if emergency else MIN_DWELL_MS
        if self._last_req_t is not None and (t - self._last_req_t) < dwell:
            return dict(_STAY)

        self._last_req_t = t
        self._streak.clear()
        return {"action": "request_handover", "target_cell_id": best_id}