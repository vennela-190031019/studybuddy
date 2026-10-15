#!/usr/bin/env python3
"""
Stage 3b dev harness: compares v2 selector variants against v1 and
random, on DEV_SEEDS only. Produces sim/variants_dev.md, recording every
variant's results including losers. This is for choosing a variant
during development — the number that actually judges whether v2 beats
random comes only from sim/run_final_report.py, on HELDOUT_SEEDS, which
this file never imports.

    python -m sim.variants_dev
"""
from __future__ import annotations

import statistics
from pathlib import Path

from sim.engine_v2_sim import simulate_learner
from sim.run_sim import _rng, bootstrap_ci
from sim.seeds import DEV_SEEDS

NUM_LEARNERS_PER_SEED = 60
BUDGETS = [5, 10, 20, 40, 80]
VARIANTS = ["linear", "sqrt", "fixed"]


def _population(policy: str, budget: int, v2_variant: str | None = None):
    kwargs = {"v2_variant": v2_variant} if v2_variant else {}
    return [
        simulate_learner(seed, learner_idx, policy, budget, **kwargs)
        for seed in DEV_SEEDS
        for learner_idx in range(NUM_LEARNERS_PER_SEED)
    ]


def _summarize(outcomes, random_outcomes, ci_rng) -> dict:
    skills = [o.final_mean_true_skill for o in outcomes]
    mins = [o.min_per_concept_skill for o in outcomes]
    diffs = [o.final_mean_true_skill - r.final_mean_true_skill for o, r in zip(outcomes, random_outcomes)]
    mean, _, _ = bootstrap_ci(skills, ci_rng)
    dmean, dlo, dhi = bootstrap_ci(diffs, ci_rng)
    return {
        "mean_final_skill": mean,
        "mean_min_skill": statistics.fmean(mins),
        "diff_vs_random_mean": dmean,
        "diff_vs_random_ci": (dlo, dhi),
    }


def run() -> str:
    num_learners = NUM_LEARNERS_PER_SEED * len(DEV_SEEDS)
    lines = [
        "# Stage 3b dev variant comparison (DEV_SEEDS only — not the final judgment)",
        "",
        f"{NUM_LEARNERS_PER_SEED} learners x {len(DEV_SEEDS)} dev seeds = {num_learners} "
        "learners per policy per budget. All three v2 coverage-penalty variants are "
        "recorded below, including losers.",
        "",
        "| Budget | Policy | Mean final skill | Mean min-per-concept skill | Diff vs random (95% CI) |",
        "|---|---|---|---|---|",
    ]
    for budget in BUDGETS:
        random_outcomes = _population("random", budget)
        v1_outcomes = _population("v1", budget)
        ci_rng = _rng("dev", budget, "bootstrap")

        def row(label: str, outcomes) -> None:
            s = _summarize(outcomes, random_outcomes, ci_rng)
            lines.append(
                f"| {budget} | {label} | {s['mean_final_skill']:.3f} "
                f"| {s['mean_min_skill']:.3f} "
                f"| {s['diff_vs_random_mean']:+.3f} [{s['diff_vs_random_ci'][0]:+.3f}, {s['diff_vs_random_ci'][1]:+.3f}] |"
            )

        row("random", random_outcomes)
        row("v1 (BKT+SM-2+lowest-mastery)", v1_outcomes)
        for variant in VARIANTS:
            v2_outcomes = _population("v2", budget, v2_variant=variant)
            row(f"v2:{variant}", v2_outcomes)

    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    print(report)
    (Path(__file__).parent / "variants_dev.md").write_text(report)


if __name__ == "__main__":
    main()
