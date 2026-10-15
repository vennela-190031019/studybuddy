"""
Forgetting-aware mastery estimate (v2).

v1 (engine/mastery.py) is standard BKT with no forgetting term: once the
posterior rises, it never decays just from the passage of time. That's
exactly the property stage 3's results (sim/results_v1.md) showed
causing trouble — the estimate saturates near 1.0 for almost any
practiced concept within 1-2 reviews, and then stays there even while
that concept's TRUE skill (sim/learner.py) is actively decaying from
forgetting. "Pick lowest mastery" then loses the ability to tell which
concepts actually need practice.

v2 reuses v1's BKT posterior + learning-transition update unchanged for
the within-review step (update() below just delegates to it), and adds a
second, separate operation: decaying the estimate back toward the prior
(p_init) as a function of elapsed time since the concept was last
reviewed. The estimate itself now "forgets," loosely mirroring the
learner's own forgetting, but through an entirely independent mechanism
and constant (see DEFAULT_DECAY_RATE below) — it is not told the
learner's true forgetting_rate.

DEFAULT_DECAY_RATE = 0.05 per day. This is a generic, round default
corresponding to a ~14-day half-life (exp(-0.05*t) = 0.5 => t =
ln(2)/0.05 ≈ 13.9 days) — a commonly cited ballpark for short-term
forgetting curves in spaced-repetition literature, picked as a plausible
general-purpose rate rather than fitted to this simulator. It is
deliberately NOT drawn from sim/learner.py's forgetting_rate sampling
range (0.01-0.1/day): that module is frozen for stage 3b, and v2 must
not be allowed to "cheat" by copying its answer out of the very
environment it's being tested against.
"""
from __future__ import annotations

import math

from engine.mastery import BKTParams, DEFAULT_PARAMS
from engine.mastery import update as bkt_update

DEFAULT_DECAY_RATE = 0.05  # per day; see module docstring for provenance


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


def update(p_mastery: float, correct: bool, params: BKTParams = DEFAULT_PARAMS) -> float:
    """Identical to v1's within-review update (engine.mastery.update).
    Forgetting is handled separately by decay_towards_prior(), since it's
    a function of elapsed time, not of an observed response."""
    return bkt_update(p_mastery, correct, params)


def decay_towards_prior(
    p_mastery: float,
    days_elapsed: float,
    params: BKTParams = DEFAULT_PARAMS,
    decay_rate: float = DEFAULT_DECAY_RATE,
) -> float:
    """
    Decays a mastery estimate toward params.p_init as time passes without
    practice:

        estimate(t) = p_init + (estimate(0) - p_init) * exp(-decay_rate * t)

    At t=0 this is the identity; as t -> infinity it relaxes fully back
    to the prior. Because this is a convex combination of p_mastery and
    p_init (both already in [0, 1]), the result is always in [0, 1].
    """
    if days_elapsed <= 0:
        return _clamp(p_mastery)
    weight = math.exp(-decay_rate * days_elapsed)
    decayed = params.p_init + (p_mastery - params.p_init) * weight
    return _clamp(decayed)
