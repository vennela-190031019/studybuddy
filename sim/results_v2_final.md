# StudyBuddy Adaptive — stage 3b final report (HELD-OUT seeds)

Policies: random, v1 (BKT + SM-2 + lowest-mastery, frozen — see sim/results_v1.md), v2:sqrt (forgetting-aware mastery estimate + coverage-aware selection, chosen from sim/variants_dev.md on DEV_SEEDS, never on these seeds). 2000 learners per policy per budget (20 held-out seeds x 100 learners/seed). Metrics are the learner's TRUE skill, never the selector's estimate.

**Verdict: v2 does NOT beat random at every held-out budget — stated plainly, as instructed.**

| Budget | Policy | Mean final true skill (95% CI) | Diff vs random (95% CI) | Mean min-per-concept skill | Worst-case min-per-concept skill |
|---|---|---|---|---|---|
| 5 | random | 0.224 [0.221, 0.228] | — | 0.119 | 0.000 |
| 5 | v1 | 0.210 [0.207, 0.214] | -0.014 [-0.015, -0.014] | 0.119 | 0.000 |
| 5 | v2:sqrt | 0.231 [0.228, 0.234] | +0.007 [+0.006, +0.007] | 0.119 | 0.000 |
| 10 | random | 0.269 [0.265, 0.273] | — | 0.121 | 0.000 |
| 10 | v1 | 0.249 [0.246, 0.253] | -0.020 [-0.020, -0.019] | 0.093 | 0.000 |
| 10 | v2:sqrt | 0.279 [0.275, 0.283] | +0.010 [+0.009, +0.010] | 0.184 | 0.028 |
| 20 | random | 0.320 [0.315, 0.325] | — | 0.164 | 0.001 |
| 20 | v1 | 0.306 [0.301, 0.311] | -0.014 [-0.015, -0.013] | 0.122 | 0.000 |
| 20 | v2:sqrt | 0.329 [0.323, 0.334] | +0.009 [+0.008, +0.009] | 0.218 | 0.016 |
| 40 | random | 0.357 [0.350, 0.363] | — | 0.210 | 0.001 |
| 40 | v1 | 0.342 [0.336, 0.349] | -0.015 [-0.016, -0.014] | 0.168 | 0.000 |
| 40 | v2:sqrt | 0.359 [0.352, 0.366] | +0.002 [+0.001, +0.003] | 0.229 | 0.008 |
| 80 | random | 0.372 [0.365, 0.379] | — | 0.232 | 0.001 |
| 80 | v1 | 0.345 [0.338, 0.353] | -0.027 [-0.028, -0.026] | 0.160 | 0.000 |
| 80 | v2:sqrt | 0.371 [0.364, 0.378] | -0.001 [-0.001, -0.000] | 0.253 | 0.003 |
