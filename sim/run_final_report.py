#!/usr/bin/env python3
"""
Stage 3b final report: random, v1 (frozen), and the single v2 variant
chosen from DEV_SEEDS experiments (sim/variants_dev.md: "sqrt" — tied
with "linear" on mean skill gains but with slightly better per-concept
coverage evenness at larger budgets, and both clearly ahead of "fixed"),
evaluated on HELDOUT_SEEDS — seeds never touched during variant
development. This is the first and only time these numbers are computed;
don't rerun this to "check" before picking a variant, that defeats the
point of holding them out.

    python -m sim.run_final_report
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from sim.engine_v2_sim import simulate_learner
from sim.run_sim import _rng, bootstrap_ci
from sim.seeds import HELDOUT_SEEDS

CHOSEN_V2_VARIANT = "sqrt"
NUM_LEARNERS_PER_SEED = 100
BUDGETS = [5, 10, 20, 40, 80]


def _population(policy: str, budget: int, v2_variant: str | None = None):
    kwargs = {"v2_variant": v2_variant} if v2_variant else {}
    return [
        simulate_learner(seed, learner_idx, policy, budget, **kwargs)
        for seed in HELDOUT_SEEDS
        for learner_idx in range(NUM_LEARNERS_PER_SEED)
    ]


def _summarize(outcomes, random_outcomes, ci_rng) -> dict:
    skills = [o.final_mean_true_skill for o in outcomes]
    diffs = [o.final_mean_true_skill - r.final_mean_true_skill for o, r in zip(outcomes, random_outcomes)]
    mean, lo, hi = bootstrap_ci(skills, ci_rng)
    dmean, dlo, dhi = bootstrap_ci(diffs, ci_rng)
    mins = [o.min_per_concept_skill for o in outcomes]
    return {
        "mean_final_skill": mean,
        "ci_low": lo,
        "ci_high": hi,
        "diff_vs_random_mean": dmean,
        "diff_vs_random_ci_low": dlo,
        "diff_vs_random_ci_high": dhi,
        "mean_min_per_concept_skill": statistics.fmean(mins),
        "worst_min_per_concept_skill": min(mins),
    }


def run_all() -> list[dict]:
    results = []
    for budget in BUDGETS:
        random_outcomes = _population("random", budget)
        v1_outcomes = _population("v1", budget)
        v2_outcomes = _population("v2", budget, v2_variant=CHOSEN_V2_VARIANT)
        ci_rng = _rng("final", budget, "bootstrap")

        results.append(
            {
                "budget": budget,
                "num_learners": len(random_outcomes),
                "random": _summarize(random_outcomes, random_outcomes, ci_rng),
                "v1": _summarize(v1_outcomes, random_outcomes, ci_rng),
                "v2": _summarize(v2_outcomes, random_outcomes, ci_rng),
            }
        )
    return results


def render_markdown(results: list[dict]) -> str:
    v2_beats_random = all(r["v2"]["diff_vs_random_ci_low"] >= 0 for r in results)
    v2_never_worse = all(r["v2"]["diff_vs_random_ci_high"] >= 0 for r in results)

    if v2_beats_random:
        verdict = "v2 significantly beats random at every held-out budget."
    elif v2_never_worse:
        verdict = (
            "v2 is not significantly worse than random at any held-out budget, and beats it "
            "at some, but does not significantly beat it at every budget."
        )
    else:
        verdict = "v2 does NOT beat random at every held-out budget — stated plainly, as instructed."

    lines = [
        "# StudyBuddy Adaptive — stage 3b final report (HELD-OUT seeds)",
        "",
        f"Policies: random, v1 (BKT + SM-2 + lowest-mastery, frozen — see sim/results_v1.md), "
        f"v2:{CHOSEN_V2_VARIANT} (forgetting-aware mastery estimate + coverage-aware selection, "
        f"chosen from sim/variants_dev.md on DEV_SEEDS, never on these seeds). "
        f"{results[0]['num_learners']} learners per policy per budget "
        f"({len(HELDOUT_SEEDS)} held-out seeds x {NUM_LEARNERS_PER_SEED} learners/seed). "
        "Metrics are the learner's TRUE skill, never the selector's estimate.",
        "",
        f"**Verdict: {verdict}**",
        "",
        "| Budget | Policy | Mean final true skill (95% CI) | Diff vs random (95% CI) | Mean min-per-concept skill | Worst-case min-per-concept skill |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        for label, key in [("random", "random"), ("v1", "v1"), (f"v2:{CHOSEN_V2_VARIANT}", "v2")]:
            d = r[key]
            diff_str = (
                "—"
                if key == "random"
                else f"{d['diff_vs_random_mean']:+.3f} [{d['diff_vs_random_ci_low']:+.3f}, {d['diff_vs_random_ci_high']:+.3f}]"
            )
            lines.append(
                f"| {r['budget']} | {label} "
                f"| {d['mean_final_skill']:.3f} [{d['ci_low']:.3f}, {d['ci_high']:.3f}] "
                f"| {diff_str} "
                f"| {d['mean_min_per_concept_skill']:.3f} "
                f"| {d['worst_min_per_concept_skill']:.3f} |"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    results = run_all()
    markdown = render_markdown(results)
    print(markdown)
    out_dir = Path(__file__).parent
    (out_dir / "results_v2_final.json").write_text(json.dumps(results, indent=2) + "\n")
    (out_dir / "results_v2_final.md").write_text(markdown)


if __name__ == "__main__":
    main()
