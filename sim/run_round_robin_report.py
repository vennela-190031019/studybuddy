#!/usr/bin/env python3
"""
Stage 3c: adds a round_robin baseline (engine.selector.round_robin_selector
— fixed-order cycling, no due-gating, no mastery estimate at all) next to
the existing random, v1, and v2:sqrt policies, on the SAME HELDOUT_SEEDS
and budgets used in sim/run_final_report.py.

This script does not change the random, v1, or v2 policies, and does not
touch sim/run_final_report.py or its output (sim/results_v2_final.*) —
it's a separate, additive comparison that reuses the same shared
simulation core (sim/engine_v2_sim.py) and the same held-out seeds.

    python -m sim.run_round_robin_report
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
POLICIES = ["random", "round_robin", "v1", "v2"]


def _population(policy: str, budget: int):
    kwargs = {"v2_variant": CHOSEN_V2_VARIANT} if policy == "v2" else {}
    return [
        simulate_learner(seed, learner_idx, policy, budget, **kwargs)
        for seed in HELDOUT_SEEDS
        for learner_idx in range(NUM_LEARNERS_PER_SEED)
    ]


def _summarize(outcomes, reference_outcomes, ci_rng) -> dict:
    skills = [o.final_mean_true_skill for o in outcomes]
    diffs = [o.final_mean_true_skill - r.final_mean_true_skill for o, r in zip(outcomes, reference_outcomes)]
    mean, lo, hi = bootstrap_ci(skills, ci_rng)
    dmean, dlo, dhi = bootstrap_ci(diffs, ci_rng)
    mins = [o.min_per_concept_skill for o in outcomes]
    return {
        "mean_final_skill": mean,
        "ci_low": lo,
        "ci_high": hi,
        "diff_vs_round_robin_mean": dmean,
        "diff_vs_round_robin_ci_low": dlo,
        "diff_vs_round_robin_ci_high": dhi,
        "mean_min_per_concept_skill": statistics.fmean(mins),
        "worst_min_per_concept_skill": min(mins),
    }


def run_all() -> list[dict]:
    results = []
    for budget in BUDGETS:
        populations = {policy: _population(policy, budget) for policy in POLICIES}
        round_robin_outcomes = populations["round_robin"]
        ci_rng = _rng("round_robin_report", budget, "bootstrap")

        results.append(
            {
                "budget": budget,
                "num_learners": len(round_robin_outcomes),
                **{
                    policy: _summarize(populations[policy], round_robin_outcomes, ci_rng)
                    for policy in POLICIES
                },
            }
        )
    return results


def render_markdown(results: list[dict]) -> str:
    v2_vs_rr = [r["v2"] for r in results]
    v2_wins_all = all(r["diff_vs_round_robin_ci_low"] > 0 for r in v2_vs_rr)
    v2_loses_any = any(r["diff_vs_round_robin_ci_high"] < 0 for r in v2_vs_rr)
    v2_ties_any = any(r["diff_vs_round_robin_ci_low"] <= 0 <= r["diff_vs_round_robin_ci_high"] for r in v2_vs_rr)

    if v2_wins_all:
        verdict = "v2:sqrt significantly beats round_robin at every held-out budget."
    elif v2_loses_any and not v2_wins_all:
        verdict = (
            "v2:sqrt does NOT consistently beat round_robin — it loses or ties at some budget(s), "
            "stated plainly, not tuned away."
        )
    elif v2_ties_any:
        verdict = (
            "v2:sqrt beats round_robin at some budgets and ties it (CI straddles zero) at others; "
            "never loses."
        )
    else:
        verdict = "see table — mixed result."

    lines = [
        "# StudyBuddy Adaptive — stage 3c: round_robin baseline (HELD-OUT seeds)",
        "",
        f"Policies: random, round_robin (new: fixed-order cycling, no due-gating, no estimate), "
        f"v1 (frozen), v2:{CHOSEN_V2_VARIANT} (frozen from stage 3b). "
        f"{results[0]['num_learners']} learners per policy per budget "
        f"({len(HELDOUT_SEEDS)} held-out seeds x {NUM_LEARNERS_PER_SEED} learners/seed) — "
        "the same HELDOUT_SEEDS and budgets as sim/results_v2_final.md. Metrics are the "
        "learner's TRUE skill. Paired difference is reported against round_robin.",
        "",
        f"**Verdict: {verdict}**",
        "",
        "| Budget | Policy | Mean final true skill (95% CI) | Diff vs round_robin (95% CI) | Mean min-per-concept | Worst-case min-per-concept |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        for label, key in [
            ("random", "random"),
            ("round_robin", "round_robin"),
            ("v1", "v1"),
            (f"v2:{CHOSEN_V2_VARIANT}", "v2"),
        ]:
            d = r[key]
            diff_str = (
                "—"
                if key == "round_robin"
                else f"{d['diff_vs_round_robin_mean']:+.3f} [{d['diff_vs_round_robin_ci_low']:+.3f}, {d['diff_vs_round_robin_ci_high']:+.3f}]"
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
    (out_dir / "results_round_robin.json").write_text(json.dumps(results, indent=2) + "\n")
    (out_dir / "results_round_robin.md").write_text(markdown)


if __name__ == "__main__":
    main()
