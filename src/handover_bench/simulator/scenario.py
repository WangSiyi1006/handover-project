"""Scenario container and CSV loader.

A Scenario holds the fixed, exogenous inputs for one replay: UE
mobility/presence, per-(UE, cell, time) radio measurements, packet traffic
and cell configuration. See datasets/schema.py for column definitions and
docs/assumptions.md for the fixed-interference assumption.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..datasets.schema import (
    CELLS_COLUMNS,
    MOBILITY_COLUMNS,
    RADIO_COLUMNS,
    TRAFFIC_COLUMNS,
    validate_columns,
)


@dataclass(frozen=True)
class Cell:
    cell_id: str
    x_m: float
    y_m: float
    height_m: float
    carrier_hz: float
    bandwidth_hz: float


@dataclass(frozen=True)
class RadioMeasurement:
    cell_id: str
    rsrp_dbm: float
    rs_sinr_db: float | None


@dataclass(frozen=True)
class Packet:
    packet_id: str
    ue_id: str
    arrival_time_ms: int
    size_bytes: int
    deadline_ms: int  # relative to arrival_time_ms


@dataclass(frozen=True)
class MobilitySample:
    active: bool
    x_m: float | None
    y_m: float | None
    z_m: float | None
    speed_mps: float | None
    heading_deg: float | None


@dataclass
class Scenario:
    scenario_id: str
    delta_t_ms: int
    time_grid_ms: list[int]
    cells: dict[str, Cell]
    ue_ids: list[str]
    ue_mode: dict[str, str]
    mobility: dict[str, dict[int, MobilitySample]]  # ue_id -> time_ms -> sample
    radio: dict[str, dict[int, list[RadioMeasurement]]]  # ue_id -> time_ms -> measurements
    traffic: list[Packet]

    def duration_ms(self) -> int:
        return self.time_grid_ms[-1] - self.time_grid_ms[0] if self.time_grid_ms else 0


def load_scenario(data_dir: str | Path, scenario_id: str) -> Scenario:
    data_dir = Path(data_dir)

    mobility_df = pd.read_csv(data_dir / "mobility.csv")
    radio_df = pd.read_csv(data_dir / "radio.csv")
    traffic_df = pd.read_csv(data_dir / "traffic.csv")
    cells_df = pd.read_csv(data_dir / "cells.csv")

    validate_columns(mobility_df, MOBILITY_COLUMNS, "mobility.csv")
    validate_columns(radio_df, RADIO_COLUMNS, "radio.csv")
    validate_columns(traffic_df, TRAFFIC_COLUMNS, "traffic.csv")
    validate_columns(cells_df, CELLS_COLUMNS, "cells.csv")

    mobility_df = mobility_df[mobility_df["scenario_id"] == scenario_id]
    radio_df = radio_df[radio_df["scenario_id"] == scenario_id]
    traffic_df = traffic_df[traffic_df["scenario_id"] == scenario_id]

    if radio_df.empty:
        raise ValueError(f"No radio.csv rows for scenario_id={scenario_id!r}")

    time_grid_ms = sorted(int(t) for t in radio_df["time_ms"].unique())
    if len(time_grid_ms) < 2:
        raise ValueError(f"Scenario {scenario_id!r} needs at least two time steps")
    delta_t_ms = time_grid_ms[1] - time_grid_ms[0]
    for a, b in zip(time_grid_ms, time_grid_ms[1:]):
        if b - a != delta_t_ms:
            raise ValueError(
                f"Scenario {scenario_id!r} radio.csv time_ms is not evenly spaced "
                f"(expected step {delta_t_ms}ms)"
            )

    cells = {
        row.cell_id: Cell(
            cell_id=row.cell_id,
            x_m=row.x_m,
            y_m=row.y_m,
            height_m=row.height_m,
            carrier_hz=row.carrier_hz,
            bandwidth_hz=row.bandwidth_hz,
        )
        for row in cells_df.itertuples(index=False)
    }

    ue_ids = sorted(set(mobility_df["ue_id"]) | set(radio_df["ue_id"]))

    ue_mode: dict[str, str] = {}
    mobility: dict[str, dict[int, MobilitySample]] = {ue: {} for ue in ue_ids}
    for row in mobility_df.itertuples(index=False):
        ue_mode.setdefault(row.ue_id, row.mode)
        mobility[row.ue_id][int(row.time_ms)] = MobilitySample(
            active=bool(row.active),
            x_m=row.x_m,
            y_m=row.y_m,
            z_m=row.z_m,
            speed_mps=row.speed_mps,
            heading_deg=row.heading_deg,
        )

    radio: dict[str, dict[int, list[RadioMeasurement]]] = {ue: {} for ue in ue_ids}
    for row in radio_df.itertuples(index=False):
        t = int(row.time_ms)
        bucket = radio[row.ue_id].setdefault(t, [])
        sinr = None if pd.isna(row.rs_sinr_db) else float(row.rs_sinr_db)
        bucket.append(
            RadioMeasurement(cell_id=row.cell_id, rsrp_dbm=float(row.rsrp_dbm), rs_sinr_db=sinr)
        )

    traffic = [
        Packet(
            packet_id=str(row.packet_id),
            ue_id=row.ue_id,
            arrival_time_ms=int(row.arrival_time_ms),
            size_bytes=int(row.size_bytes),
            deadline_ms=int(row.deadline_ms),
        )
        for row in traffic_df.itertuples(index=False)
    ]
    traffic.sort(key=lambda p: p.arrival_time_ms)

    return Scenario(
        scenario_id=scenario_id,
        delta_t_ms=delta_t_ms,
        time_grid_ms=time_grid_ms,
        cells=cells,
        ue_ids=ue_ids,
        ue_mode=ue_mode,
        mobility=mobility,
        radio=radio,
        traffic=traffic,
    )


def list_scenario_ids(data_dir: str | Path) -> list[str]:
    radio_df = pd.read_csv(Path(data_dir) / "radio.csv", usecols=["scenario_id"])
    return sorted(radio_df["scenario_id"].unique().tolist())
