from datetime import date

from engine.scheduler import MIN_EASE_FACTOR, SM2State, review


def test_successful_reviews_grow_the_interval():
    today = date(2026, 1, 1)
    state = SM2State()

    state = review(state, quality=5, today=today)
    assert state.interval_days == 1

    today = state.due_date
    state = review(state, quality=5, today=today)
    assert state.interval_days == 6

    today = state.due_date
    state = review(state, quality=5, today=today)
    # third+ success: interval = previous_interval * ease_factor
    assert state.interval_days == round(6 * state.ease_factor)
    assert state.interval_days > 6


def test_failed_review_resets_interval_and_repetitions():
    today = date(2026, 1, 1)
    state = SM2State()
    for _ in range(3):
        state = review(state, quality=5, today=today)
        today = state.due_date
    assert state.repetitions == 3
    assert state.interval_days > 6

    failed = review(state, quality=1, today=today)
    assert failed.interval_days == 1
    assert failed.repetitions == 0
    assert (failed.due_date - today).days == 1


def test_ease_factor_never_drops_below_floor():
    today = date(2026, 1, 1)
    state = SM2State()
    for _ in range(20):
        state = review(state, quality=0, today=today)
        today = state.due_date
        assert state.ease_factor >= MIN_EASE_FACTOR
    assert state.ease_factor == MIN_EASE_FACTOR


def test_higher_quality_grows_ease_factor_more():
    today = date(2026, 1, 1)
    low_quality = review(SM2State(), quality=3, today=today)
    high_quality = review(SM2State(), quality=5, today=today)
    assert high_quality.ease_factor > low_quality.ease_factor


def test_invalid_quality_raises():
    import pytest

    with pytest.raises(ValueError):
        review(SM2State(), quality=6, today=date(2026, 1, 1))
