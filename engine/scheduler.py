"""
SM-2 spaced repetition scheduling, per concept.

Quality is graded 0-5 (the original SuperMemo-2 scale): 0-2 is a failed
recall, 3-5 is a successful recall of increasing ease. A failed review
resets the repetition count and interval back to one day. A successful
review increments the repetition count; by the classic SM-2 algorithm the
first two successful reviews use fixed intervals (1 day, then 6 days),
and from the third successful review onward the interval grows by
multiplying the previous interval by the (also just-updated) ease factor.
The ease factor update formula and the 1.3 floor are the standard SM-2
values — nothing here deviates from the published algorithm.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MIN_EASE_FACTOR = 1.3
DEFAULT_EASE_FACTOR = 2.5


@dataclass(frozen=True)
class SM2State:
    ease_factor: float = DEFAULT_EASE_FACTOR
    interval_days: int = 0
    repetitions: int = 0
    due_date: date = date.min


def _new_ease_factor(ease_factor: float, quality: int) -> float:
    ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return max(MIN_EASE_FACTOR, ef)


def review(state: SM2State, quality: int, today: date | None = None) -> SM2State:
    """
    quality: 0-5 (SM-2 scale). today: the review date — defaults to the
    real current date; pass it explicitly for deterministic tests.
    """
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    today = today or date.today()
    ease_factor = _new_ease_factor(state.ease_factor, quality)

    if quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        repetitions = state.repetitions + 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = round(state.interval_days * ease_factor)

    due_date = today + timedelta(days=interval_days)

    return SM2State(
        ease_factor=ease_factor,
        interval_days=interval_days,
        repetitions=repetitions,
        due_date=due_date,
    )
