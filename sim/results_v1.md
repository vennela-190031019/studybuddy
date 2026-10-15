# StudyBuddy Adaptive — engine v1 (BKT + SM-2 + lowest-mastery): negative result, adaptive loses to random

**This file is frozen — do not overwrite.** It is the stage 3 baseline
that stage 3b's engine v2 is measured against. Reproduced from
`sim/results.json` (seed=42, 1000 simulated learners per policy per
budget, 6 concepts). Metrics are the learner's TRUE skill
(`sim/learner.py`), never the selector's BKT estimate.

v1 = `engine/mastery.py` (standard BKT, no forgetting term) +
`engine/scheduler.py` (SM-2) + `engine/selector.py` (`select_next`:
pick lowest mastery among due concepts).

| Budget | Adaptive final skill (95% CI) | Random final skill (95% CI) | Diff adaptive-random (95% CI) | Adaptive Q-to-mastery | Random Q-to-mastery | Q-to-mastery diff (95% CI) |
|---|---|---|---|---|---|---|
| 5 | 0.211 [0.207, 0.216] | 0.227 [0.222, 0.232] | -0.016 [-0.016, -0.015] | 5.0 | 5.0 | +0.0 [+0.0, +0.0] |
| 10 | 0.253 [0.248, 0.258] | 0.275 [0.269, 0.280] | -0.021 [-0.022, -0.020] | 10.0 | 10.0 | +0.0 [+0.0, +0.0] |
| 20 | 0.315 [0.307, 0.322] | 0.330 [0.323, 0.337] | -0.015 [-0.016, -0.014] | 20.0 | 20.0 | +0.0 [+0.0, +0.0] |
| 40 | 0.354 [0.344, 0.364] | 0.372 [0.363, 0.382] | -0.018 [-0.019, -0.017] | 40.0 | 40.0 | +0.0 [+0.0, +0.0] |
| 80 | 0.359 [0.348, 0.369] | 0.386 [0.377, 0.396] | -0.028 [-0.029, -0.026] | 79.9 | 80.0 | +0.1 [+0.0, +0.1] |

**Finding:** adaptive is significantly worse than random at every budget
tested — the 95% CI on the paired difference sits entirely below zero in
every row. Diagnosed cause (see stage 3 summary): BKT's mastery estimate
has no forgetting term, so it ratchets up toward ~0.9+ after 1-2
practices on almost any concept regardless of correctness, and then
stays there even as true skill decays from forgetting. "Pick lowest
mastery" then loses discriminating power and ends up allocating practice
less evenly across concepts than random does by chance; since true-skill
growth is concave (diminishing returns), uneven allocation costs mean
final skill.
