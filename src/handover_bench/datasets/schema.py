"""CSV schema for scenario datasets.

Units and conventions:
- All `*_ms` fields are integer milliseconds on the scenario's own clock
  (t=0 at scenario start).
- `deadline_ms` in traffic.csv is RELATIVE to the packet's arrival_time_ms
  (absolute deadline = arrival_time_ms + deadline_ms), not an absolute
  scenario time.
- radio.csv rows are the *fixed* propagation/measurement inputs: RSRP (and
  optionally reference-signal SINR / RSRQ) between a UE and a cell at a
  given time, computed independently of which cell the UE is actually
  associated with. They are replayed as-is; the simulator does not
  recompute them from association. See docs/assumptions.md
  ("fixed-interference assumption"). Only cell load and the resulting
  throughput/delay are recomputed from each policy's association decisions.
- A UE-cell pair only appears in radio.csv when that cell is a valid
  measurement candidate for the UE at that time (e.g. above a noise floor);
  absence means "not measurable", not RSRP = -inf.
- radio.csv's time_ms is the MEASUREMENT time. The evaluator, not the
  dataset, models reporting delay (the gap between a measurement being
  taken and a policy being allowed to see it) via
  Config.measurement_report_delay_ms, so instructors can tune realism
  without regenerating data; see docs/assumptions.md.
- mobility.csv's z_m is altitude above ground in metres: 0.0 for
  ground-bound modes (pedestrian/cyclist/car/bus/train), non-zero for
  aerial (uav).
"""

MOBILITY_COLUMNS = [
    "scenario_id",
    "time_ms",
    "ue_id",
    "mode",  # pedestrian | cyclist | car | bus | train | uav
    "x_m",
    "y_m",
    "z_m",  # altitude above ground, metres; 0.0 for ground-bound modes
    "speed_mps",
    "heading_deg",
    "active",  # 1 while the UE is present in the scenario, else 0
]

RADIO_COLUMNS = [
    "scenario_id",
    "time_ms",
    "ue_id",
    "cell_id",
    "rsrp_dbm",
    "rs_sinr_db",  # optional (fixed-SINR assumption); NaN if not provided
    "rsrq_db",  # optional; NaN if not provided
]

TRAFFIC_COLUMNS = [
    "scenario_id",
    "arrival_time_ms",
    "packet_id",
    "ue_id",
    "size_bytes",
    "deadline_ms",  # relative to arrival_time_ms
]

CELLS_COLUMNS = [
    "cell_id",
    "x_m",
    "y_m",
    "height_m",
    "carrier_hz",
    "bandwidth_hz",
]


def validate_columns(df, expected: list[str], name: str) -> None:
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")
