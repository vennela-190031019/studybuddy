#!/usr/bin/env python3
"""
Stage 3 simulation: does adaptive selection (BKT mastery + SM-2 due dates
+ lowest-mastery selection, engine/selector.py's select_next) help
simulated learners reach mastery faster than picking uniformly at random
among due concepts (engine/selector.py's random_selector)?

Every metric is computed from the learner's TRUE hidden skill
(sim.learner.SyntheticLearner) — never from the selector's BKT estimate.
The estimate only decides WHICH concept gets picked each day; it is never
read when scoring a policy.

Both policies see identical learner populations: for a given learner
index, the starting skill, learning rate, forgetting rate, and the stream
of answer-correctness randomness are derived from the same seed
regardless of policy (see learner_params_for / _rng). Only the sequence
of concepts practiced differs, because the policies disagree on what to
ask next — that disagreement, and its downstream effect on true skill, is
the entire thing being measured.

Binary correct/incorrect outcomes are mapped to SM-2's 0-5 quality scale
as 5 (correct) / 1 (incorrect) — SM-2 was designed for a graded recall
quality we don't have here; this is a documented simplification, not a
standard SM-2 value.

If nothing is due yet on a given day (possible briefly before any concept
has been scheduled), both policies fall back to treating the full
concept set as eligible, using the same priority rule they'd use among
due concepts (lowest mastery for adaptive, uniform for random) — this
keeps the fixed question budget fully spent for both policies rather than
quietly shortchanging whichever policy builds longer SM-2 intervals sooner.

Run as a script to reproduce sim/results.json and sim/results.md:
    python sim/run_sim.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from engine.mastery import DEFAULT_PARAMS as BKT_DEFAULT_PARAMS
from engine.mastery import update as bkt_update
from engine.scheduler import SM2State
from engine.scheduler import review as sm2_review
from engine.selector import ConceptState, random_selector, select_next
from sim.learner import LearnerParams, SyntheticLearner, sample_learner_params

NUM_CONCEPTS = 6
CONCEPT_IDS = [f"concept-{i}" for i in range(NUM_CONCEPTS)]
MASTERY_TARGET = 0.8
START_DATE = date(2026, 1, 1)

DEFAULT_BUDGETS = [5, 10, 20, 40, 80]
DEFAULT_NUM_LEARNERS = 1000
DEFAULT_SEED = 42
BOOTSTRAP_RESAMPLES = 1000


def _derive_seed(*parts: object) -> int:
    """
    Deterministic integer seed from arbitrary parts, independent of
    Python's (per-process-randomized) string hash — plain hash() on a
    tuple containing strings would NOT reproduce across process runs,
    which would break the "deterministic for a fixed seed" requirement.
    """
    key = "|".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)


def _rng(*parts: object) -> random.Random:
    return random.Random(_derive_seed(*parts))


def learner_params_for(seed: int, learner_idx: int) -> LearnerParams:
    """Policy-independent by construction: no `policy` argument exists to vary."""
    return sample_learner_params(_rng(seed, learner_idx, "learner"))


@dataclass(frozen=True)
class LearnerResult:
    params: LearnerParams
    final_mean_true_skill: float
    questions_to_mastery: int  # capped at the budget if the target was never reached


def _select(policy: str, states: list[ConceptState], selection_rng: random.Random | None) -> ConceptState:
    picked = select_next(states) if policy == "adaptive" else random_selector(states, selection_rng)
    if picked is not None:
        return picked
    if policy == "adaptive":
        return min(states, key=lambda s: (s.mastery, s.concept_id))
    ordered = sorted(states, key=lambda s: s.concept_id)
    return ordered[selection_rng.randrange(len(ordered))]


def simulate_learner(seed: int, learner_idx: int, policy: str, budget: int) -> LearnerResult:
    params = learner_params_for(seed, learner_idx)
    answer_rng = _rng(seed, learner_idx, "answers")
    selection_rng = _rng(seed, learner_idx, "selector") if policy == "random" else None

    learner = SyntheticLearner(concept_ids=list(CONCEPT_IDS), params=params, rng=answer_rng)
    mastery = {cid: BKT_DEFAULT_PARAMS.p_init for cid in CONCEPT_IDS}
    schedule = {cid: SM2State() for cid in CONCEPT_IDS}

    questions_to_mastery = budget
    reached = False

    for day in range(budget):
        today_date = START_DATE + timedelta(days=day)
        states = [
            ConceptState(cid, mastery[cid], due=(schedule[cid].due_date <= today_date))
            for cid in CONCEPT_IDS
        ]
        concept_id = _select(policy, states, selection_rng).concept_id

        correct = learner.practice(concept_id, today=day)
        mastery[concept_id] = bkt_update(mastery[concept_id], correct, BKT_DEFAULT_PARAMS)
        quality = 5 if correct else 1
        schedule[concept_id] = sm2_review(schedule[concept_id], quality, today=today_date)

        if not reached:
            mean_true = statistics.fmean(learner.true_skill_as_of(cid, day) for cid in CONCEPT_IDS)
            if mean_true >= MASTERY_TARGET:
                questions_to_mastery = day + 1
                reached = True

    final_mean_true_skill = statistics.fmean(
        learner.true_skill_as_of(cid, budget - 1) for cid in CONCEPT_IDS
    )
    return LearnerResult(
        params=params,
        final_mean_true_skill=final_mean_true_skill,
        questions_to_mastery=questions_to_mastery,
    )


def simulate_population(num_learners: int, policy: str, budget: int, seed: int) -> list[LearnerResult]:
    return [simulate_learner(seed, i, policy, budget) for i in range(num_learners)]


def bootstrap_ci(
    values: list[float], rng: random.Random, n_resamples: int = BOOTSTRAP_RESAMPLES, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Percentile bootstrap. Returns (mean, ci_low, ci_high)."""
    n = len(values)
    mean = statistics.fmean(values)
    if n < 2:
        return mean, mean, mean

    resample_means = []
    for _ in range(n_resamples):
        resample = rng.choices(values, k=n)
        resample_means.append(statistics.fmean(resample))
    resample_means.sort()

    lo_idx = int((alpha / 2) * n_resamples)
    hi_idx = min(int((1 - alpha / 2) * n_resamples), n_resamples - 1)
    return mean, resample_means[lo_idx], resample_means[hi_idx]


def run_budget(num_learners: int, budget: int, seed: int) -> dict:
    adaptive = simulate_population(num_learners, "adaptive", budget, seed)
    random_ = simulate_population(num_learners, "random", budget, seed)

    adaptive_skill = [r.final_mean_true_skill for r in adaptive]
    random_skill = [r.final_mean_true_skill for r in random_]
    adaptive_q = [r.questions_to_mastery for r in adaptive]
    random_q = [r.questions_to_mastery for r in random_]

    # Paired per-learner differences (same learner population, both policies).
    skill_diff = [a - r for a, r in zip(adaptive_skill, random_skill)]
    # Positive = adaptive needed fewer questions to reach the mastery target.
    questions_diff = [r - a for a, r in zip(adaptive_q, random_q)]

    ci_rng = _rng(seed, budget, "bootstrap")

    def summarize(values: list[float]) -> dict:
        mean, lo, hi = bootstrap_ci(values, ci_rng)
        return {"mean": mean, "ci_low": lo, "ci_high": hi}

    return {
        "budget": budget,
        "num_learners": num_learners,
        "adaptive_final_skill": summarize(adaptive_skill),
        "random_final_skill": summarize(random_skill),
        "final_skill_diff": summarize(skill_diff),
        "adaptive_questions_to_mastery": summarize(adaptive_q),
        "random_questions_to_mastery": summarize(random_q),
        "questions_to_mastery_diff": summarize(questions_diff),
    }


def run_all(
    num_learners: int = DEFAULT_NUM_LEARNERS,
    budgets: list[int] = DEFAULT_BUDGETS,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    return [run_budget(num_learners, b, seed) for b in budgets]


def render_markdown(results: list[dict], num_learners: int, seed: int) -> str:
    header = (
        f"# StudyBuddy Adaptive — stage 3 simulation results\n\n"
        f"{NUM_CONCEPTS} concepts, {num_learners} simulated learners per policy per budget, "
        f"seed={seed}. Metrics are the learner's TRUE skill, not the selector's BKT estimate.\n\n"
    )
    lines = [
        "| Budget | Adaptive final skill (95% CI) | Random final skill (95% CI) "
        "| Diff adaptive-random (95% CI) | Adaptive Q-to-mastery | Random Q-to-mastery "
        "| Q-to-mastery diff (95% CI) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        a, rd, d = r["adaptive_final_skill"], r["random_final_skill"], r["final_skill_diff"]
        aq, rq, qd = r["adaptive_questions_to_mastery"], r["random_questions_to_mastery"], r["questions_to_mastery_diff"]
        lines.append(
            f"| {r['budget']} "
            f"| {a['mean']:.3f} [{a['ci_low']:.3f}, {a['ci_high']:.3f}] "
            f"| {rd['mean']:.3f} [{rd['ci_low']:.3f}, {rd['ci_high']:.3f}] "
            f"| {d['mean']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] "
            f"| {aq['mean']:.1f} "
            f"| {rq['mean']:.1f} "
            f"| {qd['mean']:+.1f} [{qd['ci_low']:+.1f}, {qd['ci_high']:+.1f}] |"
        )
    return header + "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learners", type=int, default=DEFAULT_NUM_LEARNERS)
    parser.add_argument("--budgets", type=str, default=",".join(str(b) for b in DEFAULT_BUDGETS))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    budgets = [int(b) for b in args.budgets.split(",")]

    results = run_all(num_learners=args.learners, budgets=budgets, seed=args.seed)
    markdown = render_markdown(results, args.learners, args.seed)
    print(markdown)

    out_dir = Path(__file__).parent
    (out_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (out_dir / "results.md").write_text(markdown)


if __name__ == "__main__":
    main()
