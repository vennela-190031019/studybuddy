"""
Bayesian Knowledge Tracing (BKT) for per-learner, per-concept mastery.

Standard BKT has four parameters:
  - p_init  (P(L0)): prior probability the learner already knows the
    concept before any observations. It seeds a new learner's mastery
    estimate for a concept they haven't been quizzed on yet; update()
    itself never reads it (there's nothing to compute once you already
    have a mastery estimate to update from).
  - p_learn (P(T)):  probability of transitioning from "not known" to
    "known" after one practice opportunity (the learning rate).
  - p_slip  (P(S)):  probability of answering incorrectly despite knowing
    the concept (a careless mistake).
  - p_guess (P(G)):  probability of answering correctly despite not
    knowing the concept (a lucky guess).

ASSUMPTION: p_init=0.5 is a "no information" prior, not a value drawn from
a specific published dataset — standard BKT leaves p_init as a free
parameter that's normally fit per learner/skill. p_learn=0.4, p_slip=0.1,
and p_guess=0.2 are representative values of the kind commonly cited in
tutoring-system BKT literature (e.g. Corbett & Anderson 1995-style fits
tend to land slip around 0.1 and guess around 0.2-0.3), picked here as a
reasonable, documented default rather than a specific paper's fitted value.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.5
    p_learn: float = 0.4
    p_slip: float = 0.1
    p_guess: float = 0.2


DEFAULT_PARAMS = BKTParams()


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


def update(p_mastery: float, correct: bool, params: BKTParams = DEFAULT_PARAMS) -> float:
    """
    One BKT update step: Bayesian posterior given the observed response,
    followed by the learning transition. Returns the new mastery
    probability, always in [0, 1].
    """
    p_mastery = _clamp(p_mastery)

    if correct:
        numerator = p_mastery * (1 - params.p_slip)
        denominator = numerator + (1 - p_mastery) * params.p_guess
    else:
        numerator = p_mastery * params.p_slip
        denominator = numerator + (1 - p_mastery) * (1 - params.p_guess)

    posterior = numerator / denominator if denominator > 0 else p_mastery
    posterior = _clamp(posterior)

    new_mastery = posterior + (1 - posterior) * params.p_learn
    return _clamp(new_mastery)
