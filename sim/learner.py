"""
Synthetic learner model for the stage 3 simulation.

Built deliberately differently from the BKT model the selector uses, so
the comparison can't be accused of baking in the answer:
  - True skill grows by a saturating practice rule (skill moves a fraction
    of the remaining distance to 1.0 on every practice), not BKT's
    Bayesian posterior-update rule.
  - Skill decays exponentially over simulated days without practice — BKT
    has no concept of forgetting at all.
  - The probability of a correct answer is a smooth logistic function of
    true skill, not BKT's discrete slip/guess parameters.
The selector never sees true_skill — only right/wrong outcomes, which it
feeds into BKT to get a mastery estimate.

ASSUMPTIONS (documented, not tuned to favor either policy):
  - Growth comes from the act of practicing itself, regardless of whether
    the answer was right or wrong — modeling "attempting recall
    strengthens it" rather than an explicit feedback effect.
  - Forgetting is exponential decay in simulated days since last practice.
  - The logistic steepness (8.0) and midpoint (0.5) are fixed constants
    shared by every learner; only starting_skill, learning_rate, and
    forgetting_rate are sampled per learner, from the ranges below.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

LOGISTIC_STEEPNESS = 8.0
LOGISTIC_MIDPOINT = 0.5

STARTING_SKILL_RANGE = (0.0, 0.3)
LEARNING_RATE_RANGE = (0.05, 0.3)
FORGETTING_RATE_RANGE = (0.01, 0.1)


@dataclass(frozen=True)
class LearnerParams:
    starting_skill: float
    learning_rate: float
    forgetting_rate: float


def sample_learner_params(rng: random.Random) -> LearnerParams:
    return LearnerParams(
        starting_skill=rng.uniform(*STARTING_SKILL_RANGE),
        learning_rate=rng.uniform(*LEARNING_RATE_RANGE),
        forgetting_rate=rng.uniform(*FORGETTING_RATE_RANGE),
    )


def answer_probability(true_skill: float) -> float:
    """Logistic function of true skill — intentionally not BKT's slip/guess form."""
    x = LOGISTIC_STEEPNESS * (true_skill - LOGISTIC_MIDPOINT)
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


@dataclass
class SyntheticLearner:
    concept_ids: list[str]
    params: LearnerParams
    rng: random.Random
    skill: dict[str, float] = field(init=False)
    last_practiced_day: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        self.skill = {cid: self.params.starting_skill for cid in self.concept_ids}
        self.last_practiced_day = {cid: 0 for cid in self.concept_ids}

    def _decayed(self, concept_id: str, today: int) -> float:
        elapsed = today - self.last_practiced_day[concept_id]
        skill = self.skill[concept_id]
        if elapsed > 0:
            skill *= math.exp(-self.params.forgetting_rate * elapsed)
        return _clamp(skill)

    def true_skill_as_of(self, concept_id: str, today: int) -> float:
        """Read-only: true skill at `today` including forgetting decay
        since the last practice, without mutating state."""
        return self._decayed(concept_id, today)

    def practice(self, concept_id: str, today: int) -> bool:
        """
        Simulates attempting `concept_id` on day `today`: applies any
        pending forgetting decay, draws a correct/incorrect outcome from
        the logistic answer probability, then applies practice growth.
        Returns whether the answer was correct.
        """
        decayed_skill = self._decayed(concept_id, today)
        p_correct = answer_probability(decayed_skill)
        correct = self.rng.random() < p_correct

        grown_skill = decayed_skill + self.params.learning_rate * (1 - decayed_skill)
        self.skill[concept_id] = _clamp(grown_skill)
        self.last_practiced_day[concept_id] = today
        return correct
