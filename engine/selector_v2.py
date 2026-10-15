"""
Coverage-aware selection (v2).

v1 (engine/selector.py) picks strictly by lowest mastery estimate among
due concepts. Stage 3's diagnosis of v1's negative result
(sim/results_v1.md) was that once BKT's estimate saturates near 1.0,
"lowest mastery" stops discriminating well, and practice ends up
concentrated unevenly across concepts — which costs mean true skill
because skill growth is concave (diminishing returns favor spreading
practice out, not piling it on one concept).

v2 scores each concept by

    priority = (1 - decayed_mastery) - penalty_weight * coverage_term(practice_count)

and picks the due concept with the highest priority, ties broken by the
smallest concept_id (same convention as v1). `decayed_mastery` is
expected to already be forgetting-decayed (engine.mastery_v2) by the
caller — this module doesn't decay anything itself, it only combines the
(already-decayed) mastery signal with an explicit coverage penalty so
heavily-practiced concepts stop monopolizing selection even if their
decayed mastery is still relatively low.

Three coverage_term variants were tried during development
(sim/variants_dev.py -> sim/variants_dev.md has the full comparison on
DEV_SEEDS):
  - "linear": practice_count / total_practices       (relative share)
  - "sqrt":   sqrt(practice_count) / sqrt(total_practices + 1)  (softer)
  - "fixed":  practice_count * FIXED_PENALTY_PER_PRACTICE  (absolute, unnormalized)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_PENALTY_WEIGHT = 0.5
FIXED_PENALTY_PER_PRACTICE = 0.03


@dataclass(frozen=True)
class CoverageConceptState:
    concept_id: str
    decayed_mastery: float
    due: bool
    practice_count: int


def _coverage_linear(practice_count: int, total_practices: int) -> float:
    return practice_count / total_practices if total_practices > 0 else 0.0


def _coverage_sqrt(practice_count: int, total_practices: int) -> float:
    return math.sqrt(practice_count) / math.sqrt(total_practices + 1)


def _coverage_fixed(practice_count: int, total_practices: int) -> float:
    return practice_count * FIXED_PENALTY_PER_PRACTICE


_VARIANTS = {
    "linear": _coverage_linear,
    "sqrt": _coverage_sqrt,
    "fixed": _coverage_fixed,
}


def priority(
    state: CoverageConceptState,
    total_practices: int,
    variant: str = "sqrt",
    penalty_weight: float = DEFAULT_PENALTY_WEIGHT,
) -> float:
    coverage_term = _VARIANTS[variant](state.practice_count, total_practices)
    return (1 - state.decayed_mastery) - penalty_weight * coverage_term


def select_next(
    states: list[CoverageConceptState],
    variant: str = "sqrt",
    penalty_weight: float = DEFAULT_PENALTY_WEIGHT,
) -> CoverageConceptState | None:
    due = [s for s in states if s.due]
    if not due:
        return None
    total_practices = sum(s.practice_count for s in states)
    return min(
        due,
        key=lambda s: (-priority(s, total_practices, variant, penalty_weight), s.concept_id),
    )
