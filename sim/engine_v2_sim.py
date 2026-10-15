"""
Shared simulation core for stage 3b: runs one learner under "random",
"v1" (frozen BKT + SM-2 + lowest-mastery, faithfully reproducing
sim/run_sim.py's "adaptive" policy using the same engine/mastery.py,
engine/scheduler.py and engine/selector.py components), or "v2"
(engine/mastery_v2.py + engine/selector_v2.py) — against the frozen
sim/learner.py synthetic learner.

Policy-agnostic AND seed-agnostic by design: every function here takes
seed/learner_idx as plain arguments and this module never imports
sim/seeds.py. Dev-vs-held-out seed selection happens only in the calling
scripts (sim/variants_dev.py uses DEV_SEEDS, sim/run_final_report.py uses
HELDOUT_SEEDS) — never inside the simulation engine itself.

v2 drops SM-2 due-date gating entirely: every concept is eligible for
selection every day. Timing/spacing is instead handled implicitly by
decaying the mastery estimate toward the prior over elapsed time
(engine/mastery_v2.decay_towards_prior) and by the coverage penalty in
engine/selector_v2.select_next, rather than by a binary due/not-due gate.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import timedelta

from engine.mastery import DEFAULT_PARAMS as BKT_DEFAULT_PARAMS
from engine.mastery import update as bkt_update
from engine.mastery_v2 import DEFAULT_DECAY_RATE, decay_towards_prior
from engine.scheduler import SM2State
from engine.scheduler import review as sm2_review
from engine.selector import ConceptState
from engine.selector import select_next as select_next_v1
from engine.selector_v2 import CoverageConceptState, DEFAULT_PENALTY_WEIGHT
from engine.selector_v2 import select_next as select_next_v2
from sim.learner import LearnerParams, SyntheticLearner
from sim.run_sim import CONCEPT_IDS, START_DATE, _rng, learner_params_for


@dataclass(frozen=True)
class LearnerOutcome:
    params: LearnerParams
    final_mean_true_skill: float
    min_per_concept_skill: float


def _final_outcome(learner: SyntheticLearner, params: LearnerParams, budget: int) -> LearnerOutcome:
    final_skills = [learner.true_skill_as_of(cid, budget - 1) for cid in CONCEPT_IDS]
    return LearnerOutcome(
        params=params,
        final_mean_true_skill=statistics.fmean(final_skills),
        min_per_concept_skill=min(final_skills),
    )


def simulate_learner(
    seed: int,
    learner_idx: int,
    policy: str,
    budget: int,
    v2_variant: str = "sqrt",
    v2_penalty_weight: float = DEFAULT_PENALTY_WEIGHT,
    v2_decay_rate: float = DEFAULT_DECAY_RATE,
) -> LearnerOutcome:
    """policy: "random" | "v1" | "v2". Same learner population (params,
    answer randomness) regardless of policy — see learner_params_for."""
    params = learner_params_for(seed, learner_idx)
    answer_rng = _rng(seed, learner_idx, "answers")
    learner = SyntheticLearner(concept_ids=list(CONCEPT_IDS), params=params, rng=answer_rng)

    if policy == "random":
        selection_rng = _rng(seed, learner_idx, "selector")
        for day in range(budget):
            concept_id = CONCEPT_IDS[selection_rng.randrange(len(CONCEPT_IDS))]
            learner.practice(concept_id, today=day)
        return _final_outcome(learner, params, budget)

    if policy == "v1":
        mastery = {cid: BKT_DEFAULT_PARAMS.p_init for cid in CONCEPT_IDS}
        schedule = {cid: SM2State() for cid in CONCEPT_IDS}
        for day in range(budget):
            today_date = START_DATE + timedelta(days=day)
            states = [
                ConceptState(cid, mastery[cid], due=(schedule[cid].due_date <= today_date))
                for cid in CONCEPT_IDS
            ]
            picked = select_next_v1(states)
            if picked is None:
                picked = min(states, key=lambda s: (s.mastery, s.concept_id))
            concept_id = picked.concept_id

            correct = learner.practice(concept_id, today=day)
            mastery[concept_id] = bkt_update(mastery[concept_id], correct, BKT_DEFAULT_PARAMS)
            quality = 5 if correct else 1
            schedule[concept_id] = sm2_review(schedule[concept_id], quality, today=today_date)
        return _final_outcome(learner, params, budget)

    if policy == "v2":
        mastery = {cid: BKT_DEFAULT_PARAMS.p_init for cid in CONCEPT_IDS}
        last_practiced = {cid: 0 for cid in CONCEPT_IDS}
        practice_count = {cid: 0 for cid in CONCEPT_IDS}
        ever_practiced = {cid: False for cid in CONCEPT_IDS}

        for day in range(budget):
            states = []
            for cid in CONCEPT_IDS:
                elapsed = (day - last_practiced[cid]) if ever_practiced[cid] else 0
                decayed = decay_towards_prior(mastery[cid], elapsed, decay_rate=v2_decay_rate)
                states.append(
                    CoverageConceptState(cid, decayed, due=True, practice_count=practice_count[cid])
                )
            picked = select_next_v2(states, variant=v2_variant, penalty_weight=v2_penalty_weight)
            concept_id = picked.concept_id

            correct = learner.practice(concept_id, today=day)
            mastery[concept_id] = bkt_update(mastery[concept_id], correct, BKT_DEFAULT_PARAMS)
            last_practiced[concept_id] = day
            practice_count[concept_id] += 1
            ever_practiced[concept_id] = True

        return _final_outcome(learner, params, budget)

    raise ValueError(f"unknown policy: {policy!r}")
