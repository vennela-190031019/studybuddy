from engine.mastery import BKTParams
from engine.mastery_v2 import DEFAULT_DECAY_RATE, decay_towards_prior


def test_no_elapsed_time_is_identity():
    assert decay_towards_prior(0.9, days_elapsed=0) == 0.9


def test_decay_moves_estimate_toward_prior():
    params = BKTParams(p_init=0.5)
    high = decay_towards_prior(0.95, days_elapsed=10, params=params)
    assert params.p_init < high < 0.95


def test_decay_approaches_prior_as_time_grows():
    params = BKTParams(p_init=0.5)
    near = decay_towards_prior(0.95, days_elapsed=1, params=params)
    far = decay_towards_prior(0.95, days_elapsed=1000, params=params)
    assert abs(far - params.p_init) < abs(near - params.p_init)
    assert abs(far - params.p_init) < 1e-6


def test_decay_works_symmetrically_below_the_prior():
    params = BKTParams(p_init=0.5)
    low = decay_towards_prior(0.05, days_elapsed=10, params=params)
    assert 0.05 < low < params.p_init


def test_decay_stays_in_unit_interval_across_many_elapsed_times():
    params = BKTParams(p_init=0.5)
    for estimate in [0.0, 0.1, 0.5, 0.9, 1.0]:
        for elapsed in [0, 1, 5, 50, 10_000]:
            value = decay_towards_prior(estimate, elapsed, params=params)
            assert 0.0 <= value <= 1.0


def test_default_decay_rate_is_documented_and_distinct_from_learner_ranges():
    # Sanity check that the constant exists and isn't accidentally 0 or
    # negative — the actual provenance is documented in the module
    # docstring (a generic ~14-day half-life, not fit to this simulator).
    assert DEFAULT_DECAY_RATE > 0
