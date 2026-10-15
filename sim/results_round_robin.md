# StudyBuddy Adaptive — stage 3c: round_robin baseline (HELD-OUT seeds)

Policies: random, round_robin (new: fixed-order cycling, no due-gating, no estimate), v1 (frozen), v2:sqrt (frozen from stage 3b). 2000 learners per policy per budget (20 held-out seeds x 100 learners/seed) — the same HELDOUT_SEEDS and budgets as sim/results_v2_final.md. Metrics are the learner's TRUE skill. Paired difference is reported against round_robin.

**Verdict: v2:sqrt does NOT consistently beat round_robin — it loses or ties at some budget(s), stated plainly, not tuned away.**

| Budget | Policy | Mean final true skill (95% CI) | Diff vs round_robin (95% CI) | Mean min-per-concept | Worst-case min-per-concept |
|---|---|---|---|---|---|
| 5 | random | 0.224 [0.221, 0.228] | -0.007 [-0.007, -0.006] | 0.119 | 0.000 |
| 5 | round_robin | 0.231 [0.228, 0.235] | — | 0.119 | 0.000 |
| 5 | v1 | 0.210 [0.207, 0.213] | -0.021 [-0.022, -0.021] | 0.119 | 0.000 |
| 5 | v2:sqrt | 0.231 [0.228, 0.235] | +0.000 [+0.000, +0.000] | 0.119 | 0.000 |
| 10 | random | 0.269 [0.265, 0.273] | -0.011 [-0.012, -0.011] | 0.121 | 0.000 |
| 10 | round_robin | 0.281 [0.276, 0.285] | — | 0.208 | 0.040 |
| 10 | v1 | 0.249 [0.246, 0.253] | -0.031 [-0.032, -0.030] | 0.093 | 0.000 |
| 10 | v2:sqrt | 0.279 [0.275, 0.283] | -0.002 [-0.002, -0.002] | 0.184 | 0.028 |
| 20 | random | 0.320 [0.315, 0.325] | -0.016 [-0.016, -0.015] | 0.164 | 0.001 |
| 20 | round_robin | 0.336 [0.330, 0.341] | — | 0.289 | 0.070 |
| 20 | v1 | 0.306 [0.301, 0.312] | -0.030 [-0.030, -0.029] | 0.122 | 0.000 |
| 20 | v2:sqrt | 0.329 [0.323, 0.334] | -0.007 [-0.007, -0.007] | 0.218 | 0.016 |
| 40 | random | 0.357 [0.351, 0.363] | -0.017 [-0.017, -0.016] | 0.210 | 0.001 |
| 40 | round_robin | 0.374 [0.367, 0.381] | — | 0.326 | 0.069 |
| 40 | v1 | 0.342 [0.336, 0.349] | -0.032 [-0.033, -0.031] | 0.168 | 0.000 |
| 40 | v2:sqrt | 0.359 [0.352, 0.365] | -0.015 [-0.015, -0.014] | 0.229 | 0.008 |
| 80 | random | 0.372 [0.364, 0.379] | -0.016 [-0.017, -0.016] | 0.232 | 0.001 |
| 80 | round_robin | 0.388 [0.381, 0.395] | — | 0.343 | 0.066 |
| 80 | v1 | 0.345 [0.338, 0.353] | -0.043 [-0.044, -0.042] | 0.160 | 0.000 |
| 80 | v2:sqrt | 0.371 [0.364, 0.379] | -0.017 [-0.018, -0.017] | 0.253 | 0.003 |
