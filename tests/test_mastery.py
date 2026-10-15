from engine.mastery import BKTParams, DEFAULT_PARAMS, update


def test_mastery_always_in_unit_interval():
    p = 0.0
    for correct in [True, False, True, True, False, False, True]:
        p = update(p, correct)
        assert 0.0 <= p <= 1.0


def test_mastery_rises_after_correct_answer():
    new_p = update(DEFAULT_PARAMS.p_init, correct=True)
    assert new_p > DEFAULT_PARAMS.p_init


def test_mastery_falls_after_incorrect_answer():
    new_p = update(DEFAULT_PARAMS.p_init, correct=False)
    assert new_p < DEFAULT_PARAMS.p_init


def test_zero_guess_means_correct_answer_proves_mastery():
    # If guessing correctly without knowing is impossible, any correct
    # answer (from a learner with some non-zero prior) should make the
    # posterior certain, i.e. mastery after the update is 1.0.
    params = BKTParams(p_guess=0.0)
    new_p = update(0.5, correct=True, params=params)
    assert new_p == 1.0


def test_zero_slip_means_incorrect_answer_implies_unknown():
    # If a learner who knows the concept never slips, a wrong answer
    # proves the concept wasn't known yet (posterior 0), so the only
    # mastery gained comes from the learning transition itself.
    params = BKTParams(p_slip=0.0)
    new_p = update(0.5, correct=False, params=params)
    assert new_p == params.p_learn


def test_guess_one_means_correct_answer_is_uninformative():
    # If an unknowing learner always guesses correctly and never slips
    # when they do know it, a correct answer carries no evidence either
    # way, so the posterior (before the learning transition) equals the
    # prior exactly.
    params = BKTParams(p_guess=1.0, p_slip=0.0, p_learn=0.0)
    new_p = update(0.37, correct=True, params=params)
    assert new_p == 0.37


def test_slip_one_means_incorrect_answer_is_uninformative():
    # If a knowing learner always slips (gets it wrong anyway) and an
    # unknowing learner never guesses right, a wrong answer carries no
    # evidence either way.
    params = BKTParams(p_slip=1.0, p_guess=0.0, p_learn=0.0)
    new_p = update(0.62, correct=False, params=params)
    assert new_p == 0.62
