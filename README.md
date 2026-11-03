# handover-bench

A trace-replay benchmark for handover algorithms (COMP3014J Performance of
Computer Systems). You write a handover policy in `algorithm.py`, evaluate
it locally against the NR A3 baseline on saved scenarios, and submit it
with `report.pdf`.

**Document 1 is your assignment brief:** task, submission, deadline, groups
and marking. **Document 2 provides the handover background and scoring
reference.** The two documents are supplied separately from this package. This README covers installing and running the
package, and the technical reference your code needs.

## Install and run

Python 3.10 or later is required; Python 3.11 is recommended because grading
uses it. The only runtime dependencies are `numpy` and `pandas`.

1. Unzip the package. Open a terminal in `student/handover-bench`, the folder
   containing `README.md` and `pyproject.toml`. If your unzip tool adds an
   outer folder, locate this folder inside it.
2. Create and activate a virtual environment using the commands for your OS.

   **macOS / Linux:**
   ```bash
   python3 --version
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows (Command Prompt, not PowerShell):**
   ```bat
   py -3 --version
   py -3 -m venv .venv
   .venv\Scripts\activate.bat
   ```

   Check that the version is at least 3.10. In Windows PowerShell, activate
   with `.\.venv\Scripts\Activate.ps1`; if script execution is blocked, use
   Command Prompt and the commands above.
3. Install the package (internet access is needed for installation):
   ```text
   python -m pip install -e .
   ```
4. Using your file manager, copy `examples/algorithm.py` into the
   `handover-bench` folder as `algorithm.py`. Copy it once, then edit that
   file and fill in your team details. Do not overwrite your edited policy
   by copying the starter again. Ensure the filename is not `algorithm.py.txt`.
5. Run the evaluator from the same folder, with the environment active:
   ```text
   handover-bench evaluate --algorithm algorithm.py --suite data/practice --output results/practice
   ```

The evaluator imports `algorithm.py` and calls its `StudentPolicy` class.
Running `python algorithm.py` alone does not run the simulation. The
`python -m handover_bench.cli evaluate ...` command is equivalent and can be
used with the same arguments if the installed `handover-bench` shortcut is
not found.

Each evaluation prints your score and writes `results/practice/results.json`
and `results/practice/dashboard.html`. Neither file is included in the ZIP.
Double-click `dashboard.html`, or use your browser's Open File command.
Viewing it requires no server or internet connection. The dashboard shows
your score against A3 (always 100), the seven KPI score factors and their
gains or penalties, aggregate KPIs and per-scenario results.

After editing `algorithm.py`, rerun step 5 and reload the browser page. In
each new terminal, return to the package folder and activate the environment
again; installation and copying the starter are one-time steps. Practice
scores are feedback; the performance grade uses fixed score intervals on a private suite, as described in
Document 1.

The *never hand over* reference always returns `{"action": "stay"}`. Initial
attachment and reconnection after radio link failure still happen in the
simulator. Its displayed index is for comparison only: it is neither an
extra grading baseline nor a guaranteed lower bound on scores.

If the command reports `No module named handover_bench`, activate the
environment and repeat step 3 from the folder containing `pyproject.toml`.
If `algorithm.py` or `data/practice` cannot be found, check your current
folder and filenames. If evaluation fails, read the terminal error and any
errors recorded in `results.json`; an older dashboard is not evidence of a
successful new run.

`data/practice/` contains all ten saved practice scenarios. Use these files
as supplied; no data generation or simulation tools are required.
For a step-by-step Windows and macOS guide, see `START_HERE.txt`.

## Learning from the always-stay starter

Purpose and decision rule. The supplied examples/algorithm.py is an always-stay starter that demonstrates the required interface. Its reset() method does nothing and its decide() method always returns {"action": "stay"}. It never requests a handover. The simulator still performs initial attachment and reconnection after radio link failure, so a device can change cell during recovery. Always staying is different from always requesting handover.

Measured result. On the supplied ten practice scenarios with the default configuration, the starter scores 84.93 against A3’s 100. Its composite index is therefore 15.07% below A3: (84.93 − 100)% = −15.07%. This is below the performance pass threshold of 100. Practice results are feedback; assessment uses the private suite. The score is not a percentage assignment mark. It produces the same decisions and results as the dashboard’s never hand over reference. Document 2, Section 8 shows the worked KPI comparison and score calculation.

Why it performs worse than A3. Avoiding handover requests eliminates handover attempts, handover failures and ping-pongs, but it can leave a moving device on a deteriorating link until radio link failure triggers recovery. On the practice suite, worse goodput, deadline delivery, outage and RLF metrics outweigh those handover-related gains. A3 can transfer a device before the serving link fails. Minimising the number of handovers alone does not solve this assignment.

Develop your own policy. Use the observation fields documented in README.md to decide when staying is harmful and which candidate could improve service. You can consider radio measurements, congestion, backlog and per-device history. Form a testable hypothesis about the trade-off your rule addresses. Explain when your policy requests handover and when it stays; do not assume that more or fewer handovers always improve the score.

Evaluate your changes. Compare your policy with A3 and the always-stay starter on identical scenarios. Inspect all seven KPI gains and penalties and the weakest scenarios, not only the aggregate score. Change one idea at a time and use an ablation to identify its effect. Use separate subsets of the supplied scenarios for tuning and validation, and report which you used. Do not tune on your validation subset. In your group report, explain your design, measured improvements and regressions, computational cost, and the commands needed to reproduce the results.

Submitting the supplied sample solution (examples/algorithm.py) as your solution will receive a fail grade for the assignment, regardless of its performance score or report mark. Changing only names, comments or formatting does not count as developing your own algorithm. You may use the sample as a starting point, but must develop, explain and evaluate your own changes.

## Your policy

`algorithm.py` defines one class. The simulator creates one instance per
UE (device) and calls:

```python
class StudentPolicy:
    def reset(self, config: dict) -> None:
        ...  # once when this UE first appears in each scenario

    def decide(self, observation: dict) -> dict:
        ...  # each 200 ms step while this UE is idle (not mid-handover)
        return {"action": "stay"}
        # or: {"action": "request_handover", "target_cell_id": "cell3"}
```

A request is accepted only when the target is one of the listed candidates
and is not the serving cell. Unknown actions or missing/invalid target IDs
are treated as `stay`; malformed values that raise an exception invalidate
the run. Return the documented action dictionary. An
instance may keep history in `self` across calls for the same UE, but it
never sees other UEs or future observations. `config` contains
`delta_t_ms` and the A3 parameters (`a3_hysteresis_db`, `a3_offset_db`,
`a3_cell_offset_db`, `a3_object_offset_db`, `a3_ttt_ms`).
`examples/algorithm.py` is a working example, and
`src/handover_bench/api.py` defines the types.

### Observation fields

| Field | Meaning |
|---|---|
| `time_ms` | Current decision time |
| `measurement_time_ms` | When the shown measurements were taken (equal to `time_ms`: the reporting delay is 0 ms) |
| `ue_id` | This UE's identifier |
| `serving_cell_id`, `serving_rsrp_dbm` | Serving cell and its RSRP (dBm) |
| `candidates` | List of neighbour cells, each with `cell_id`, `rsrp_dbm`, `rs_sinr_db` (dB) and `eligible` (always true in this release) |
| `ho_phase` | `"idle"` whenever `decide()` is called |
| `recent_events` | Up to five recent events for this UE, each `{"event", "time_ms"}`; events are `ho_attempt`, `ho_completed`, `ho_failed`, `ping_pong`, `rlf`, `rlf_recovered` |
| `serving_cell_load`, `candidate_cell_loads` | Congestion signal from the previous step: UEs attached to the cell divided by 50, capped at 1.0 (a heuristic, not exact resource usage) |
| `queue_backlog_bytes` | This UE's undelivered data |
| `has_position`, `x_m`, `y_m`, `z_m`, `speed_mps`, `heading_deg` | Position (m), altitude (non-zero only for `uav`), speed and heading |

The serving cell's SINR is not included, only its RSRP. Position, speed and heading are available, but acceleration and trends of
radio measurements are not; keep past observations in `self` and derive
those features yourself.

## Fixed performance grading

Your group submits one `algorithm.py` and one shared `report.pdf`. Algorithm
performance contributes 90% and the group report contributes 10% of the
assignment grade. Use the fixed intervals in Document 1; class rank and
grade quotas do not determine grades.
An index increase from 100 to 135 is a 35% composite-index improvement,
not a throughput improvement or an assignment percentage mark. There is no
imposed cap, but every fixed suite has a finite mathematical score bound.

## Submission rules

**Submitting the supplied sample solution (examples/algorithm.py) as your solution will receive a fail grade for the assignment, regardless of its performance score or report mark. Changing only names, comments or formatting does not count as developing your own algorithm. You may use the sample as a starting point, but must develop, explain and evaluate your own changes.**

- **Team details.** Fill in the comment block at the top of `algorithm.py`
  (copied from the starter) with your Brightspace group and every member's
  name and student number.
- **One self-contained file**, `algorithm.py`, of at most 1 MiB, compatible
  with Python 3.11. Grading installs only the Python standard library,
  `numpy`, `pandas` and `handover_bench`; importing anything else (for
  example `torch` or `sklearn`) fails and invalidates the whole run.
- **No file, network or evaluator access.** Use only the observation. Do
  not read trace files, hard-code routes or scenario identifiers, or modify
  the evaluator.
- **Per-UE state only.** Keep history in instance attributes, not in
  module-level or class-level variables shared between UEs.
- **Reproducible randomness.** If your policy uses randomness, create your
  own seeded generator (for example `numpy.random.default_rng(0)`).
- **Tuned parameters and learned models.** You may use optimisation or
  machine learning offline, with any tools, as long as the result is
  written into `algorithm.py`: either hard-coded parameter values in a
  rule, or a small model (linear or logistic regression, a small decision
  tree, a small neural network) whose parameters are stored in the file and
  evaluated with `numpy`. Separate model or weight files are not accepted.
  Validate on supplied scenarios you did not train or tune on.
- **Execution limits** during grading: 512 MiB RAM, one CPU, 30 s start-up,
  2 s per `reset()` or `decide()` call, and 180 s per scenario including
  the simulator. A scenario has roughly 4,000 `decide()` calls, so aim for
  a few milliseconds per call. The local evaluator does not enforce these
  limits.
- A submission that fails on any scenario (exception, timeout or missing
  import) is invalid and scores 0.

Start your report from `docs/report_template.md` and export it to PDF.

## Modelling assumptions

- **Replay clock.** The simulator advances in 200 ms steps. Handover and recovery timers are
  rounded up to whole steps and last at least one step, so handover
  preparation (50 ms) and execution (40 ms) each take one step, and the
  UE has no service during the execution step. A3 time-to-trigger uses
  elapsed time: its 320 ms threshold is first reached 400 ms after the
  entering sample on this grid. The entering RSRP advantage is strictly
  greater than 2 dB; the hysteresis state is retained between entering and
  leaving thresholds.
- **Fixed interference.** RSRP and SINR come from the saved traces and do
  not depend on which cell each UE uses. Your decisions change cell load,
  and therefore each UE's share of bandwidth, throughput and delay.
- **Scheduler.** Each step, a cell's 20 MHz is split equally between its
  attached UEs that have data waiting; each UE's rate follows the Shannon
  formula at its own SINR. Packets are served in order of arrival within
  each 200 ms step.
- **Radio link monitoring.** A UE is out of sync when its serving SINR is
  below -8 dB and in sync above -6 dB. While attached below -8 dB it
  receives no data (counted as outage). After 10 out-of-sync steps (2 s),
  a 1 s timer (T310) starts; if the link has not recovered by then, radio
  link failure (RLF) is declared. Re-establishment takes 1 s and then
  connects to the cell with the highest SINR above -6 dB.
- **Handover outcome.** A handover fails if radio link failure occurs
  during preparation, if the source link is already failing (T310 running)
  when preparation ends, or if the target's SINR is below -8 dB when
  execution ends. A failure counts as a handover failure
  and an RLF.
- **Ping-pong.** A handover whose execution starts less than 1 s after the
  previous handover's execution started counts as ping-pong.
- **No cancellation.** `decide()` is not called during preparation or
  execution, so a started handover cannot be cancelled.
- **Practice data.** The supplied traces are synthetic benchmark scenarios.
  They support comparisons within this simplified simulator and do not
  establish performance in a real mobile network.

## Standards basis

The package implements a documented subset of NR mobility procedures, not
full 3GPP compliance.

| Behaviour | 3GPP reference |
|---|---|
| A3 entering and leaving conditions | TS 38.331 V18.1.0, Sec. 5.5.4.4 |
| Time-to-trigger, per neighbour | TS 38.331, Sec. 5.5.4.1 |
| Measurement reporting separate from handover execution | TS 38.331, Sec. 5.5.4 and Sec. 5.3.5 |
| Handover preparation and execution (durations are assumptions) | TS 38.331, Sec. 5.3.5 |
| Radio link monitoring, N310/N311/T310 (approximated from SINR) | TS 38.331, Sec. 5.3.10 |
| RLF recovery (approximated as re-selecting the best cell) | TS 38.331, Sec. 5.3.10.3 |
| Ping-pong (minimum time of stay) | Evaluation convention, not a 3GPP counter |

## Package contents

```
START_HERE.txt             Step-by-step Windows and macOS setup
algorithm.py (yours)        Copy of examples/algorithm.py that you edit
examples/algorithm.py       Always-stay interface starter (84.93 on practice)
data/practice/              Ten practice scenarios (CSV)
docs/report_template.md     Group report structure
src/handover_bench/
    api.py                  Policy interface and observation types
    config.py               Simulator, A3 and scoring settings
    baselines/              A3 baseline and the never-hand-over reference
    simulator/              Execution engine, scheduler, scenario loading
    metrics/                KPI definitions and the score (scoring.py)
    datasets/               Saved-data CSV schema
    evaluation/, dashboard/, cli.py   Evaluator, dashboard and command line
```

## Licence

MIT (see `LICENSE`). `baselines/a3.py` adapts A3 and timer logic from
kit-cel/HandoverOptimDRL (MIT); see `THIRD_PARTY_NOTICES.md`.
