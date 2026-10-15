"""
Picks the next concept to quiz a learner on.

`select_next` is the adaptive policy: among due concepts, pick the one
with the lowest mastery, breaking ties deterministically by concept_id so
the choice never depends on input ordering or dict iteration order.

`random_selector` is a baseline for the stage 3 comparison — it picks
uniformly among due concepts using a caller-supplied, seedable
`random.Random`, so a fixed seed always reproduces the same picks.

`round_robin_selector` is a second baseline (stage 3c): cycles through a
fixed concept order with no due-date gating and no mastery estimate at
all — the simplest possible policy, used to check whether the adaptive
machinery is earning its complexity over something even simpler than
uniform random.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptState:
    concept_id: str
    mastery: float
    due: bool


def select_next(states: list[ConceptState]) -> ConceptState | None:
    due = [s for s in states if s.due]
    if not due:
        return None
    return min(due, key=lambda s: (s.mastery, s.concept_id))


def random_selector(states: list[ConceptState], rng: random.Random) -> ConceptState | None:
    due = [s for s in states if s.due]
    if not due:
        return None
    # Sort first so the draw is a function of (due set, seed) alone, not
    # of whatever order the caller happened to pass states in.
    due.sort(key=lambda s: s.concept_id)
    index = rng.randrange(len(due))
    return due[index]


def round_robin_selector(concept_ids: list[str], step: int) -> str:
    """
    Cycles through `concept_ids` in the given fixed order: no due-date
    gating, no mastery estimate, not even randomness — just
    concept_ids[step % len(concept_ids)]. `step` is the 0-indexed
    position in the overall sequence (e.g. the simulation's day index),
    so calling this with steps 0, 1, 2, ... visits every concept exactly
    once per full cycle before repeating.
    """
    if not concept_ids:
        raise ValueError("concept_ids must be non-empty")
    return concept_ids[step % len(concept_ids)]
