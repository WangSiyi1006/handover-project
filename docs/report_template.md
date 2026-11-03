# Handover optimisation group report

Submit one shared report per group. This report contributes 10% of your
assignment grade; algorithm performance contributes 90% using the fixed
intervals in Document 1.

Brightspace group and members:  
Policy name/version:  
Python and benchmark versions:  
Practice suite and configuration:  

Replace the prompts below with your own analysis and export the completed
report to PDF. Submit `report.pdf` alongside the exact `algorithm.py`
evaluated here.

## 1. Objective and policy design

Explain the weaknesses you observed in A3 and the behaviour your policy is
intended to improve. Describe the observations used, per-user state,
handover decision rule, and parameter choices. Include concise pseudocode
and decision-time/memory complexity. Distinguish known facts from assumptions.

Identify what you changed from the supplied sample and why. Compare your
policy with the sample as well as A3, and support your contribution with
controlled experiments. Submitting the supplied sample as your solution
receives a fail grade for the assignment, regardless of its performance
score or report mark; changing only names, comments or formatting does not
count as developing your own algorithm.

## 2. Reproducible experimental setup

State the scenario set, configuration, command, dependencies, and hardware
used. Describe how parameters were selected; if you used optimisation or machine
learning offline, describe the training data, method, validation scenarios
and how the result is embedded in `algorithm.py`. Record random seeds if any
part of your policy or experiment is stochastic. Explain how comparison
conditions were kept identical and distinguish tuning data from validation
data, if you made that distinction.

```bash
handover-bench evaluate --algorithm algorithm.py --suite data/practice --output results/practice
```

Include the submitted code version or hash so the results can be traced to
the submitted policy. If you report runtime, explain what it measures and
whether simulator startup and baseline evaluation are included.

## 3. Results against A3

Complete the table using the evaluator's aggregate results. Report units,
absolute changes, and any undefined values as N/A; do not divide by a zero
baseline when computing a percentage change.

| KPI | A3 | Submitted policy | Absolute change | Interpretation |
|---|---:|---:|---:|---|
| Goodput ratio (higher is better) | | | | |
| Deadline delivery ratio (higher is better) | | | | |
| Outage fraction (lower is better) | | | | |
| RLF events per UE-minute (lower is better) | | | | |
| Handover failures per UE-minute (lower is better) | | | | |
| Ping-pong events per UE-minute (lower is better) | | | | |
| Handover attempts per UE-minute (lower is better) | | | | |
| Performance index | 100 | | | |

Add a per-scenario table or figure and discuss uneven performance. Include
useful diagnostics such as success rate or tail delay where they help
explain outcomes. Distinguish diagnostic improvements from scored gains.

## 4. Evidence for the improvement

Compare the final policy with at least one controlled variant that removes
or changes a key idea. Keep scenarios and other settings constant, and
report the index and affected KPIs for each variant.

| Variant | Controlled change | Index | KPI evidence | Explanation |
|---|---|---:|---|---|
| Baseline A3 | Reference | 100 | | |
| Variant/ablation | | | | |
| Final policy | | | | |

Explain why the observed changes support or weaken your original
hypothesis. Report unsuccessful ideas if they informed the final design.

## 5. Regressions, limitations, and generalisation

Identify every scored KPI that worsened relative to A3 and explain its
contribution to the result. Discuss the worst-performing scenarios, any
trade-off between service quality and handover frequency, dependence on
particular parameter values, and risks of overfitting the practice suite.
Explain which conclusions may change on unseen mobility, radio, or traffic
traces. Do not infer real-network guarantees from this simplified simulator.

## 6. Sources and development disclosure

Cite reused ideas and code. Disclose collaboration and tools in accordance
with the course policy. Identify your own contributions clearly.
