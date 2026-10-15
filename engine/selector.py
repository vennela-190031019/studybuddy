"""
Picks the next concept to quiz a learner on.

`select_next` is the adaptive policy: among due concepts, pick the one
with the lowest mastery, breaking ties deterministically by concept_id so
the choice never depends on input ordering or dict iteration order.

`random_selector` is a baseline for the stage 3 comparison — it picks
uniformly among due concepts using a caller-supplied, seedable
`random.Random`, so a fixed seed always reproduces the same picks.
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
