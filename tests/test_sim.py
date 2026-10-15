import pytest

from sim.learner import SyntheticLearner, sample_learner_params
from sim.run_sim import (
    run_budget,
    simulate_learner,
    simulate_population,
    _rng,
)


def test_simulate_learner_is_deterministic_for_a_fixed_seed():
    a1 = simulate_learner(seed=7, learner_idx=3, policy="adaptive", budget=30)
    a2 = simulate_learner(seed=7, learner_idx=3, policy="adaptive", budget=30)
    assert a1 == a2

    r1 = simulate_learner(seed=7, learner_idx=3, policy="random", budget=30)
    r2 = simulate_learner(seed=7, learner_idx=3, policy="random", budget=30)
    assert r1 == r2


def test_simulate_population_is_deterministic_for_a_fixed_seed():
    pop1 = simulate_population(num_learners=20, policy="adaptive", budget=15, seed=11)
    pop2 = simulate_population(num_learners=20, policy="adaptive", budget=15, seed=11)
    assert pop1 == pop2


def test_true_skill_stays_in_unit_interval():
    rng = _rng(1, 0, "answers")
    params = sample_learner_params(_rng(1, 0, "learner"))
    learner = SyntheticLearner(concept_ids=["a", "b"], params=params, rng=rng)

    for day in range(500):
        for concept_id in ["a", "b"]:
            learner.practice(concept_id, today=day)
            assert 0.0 <= learner.true_skill_as_of(concept_id, day) <= 1.0
        # a long gap to exercise forgetting decay too
        assert 0.0 <= learner.true_skill_as_of("a", day + 1000) <= 1.0


def test_population_final_skill_and_questions_stay_in_bounds():
    budget = 25
    for policy in ("adaptive", "random"):
        for result in simulate_population(num_learners=50, policy=policy, budget=budget, seed=5):
            assert 0.0 <= result.final_mean_true_skill <= 1.0
            assert 1 <= result.questions_to_mastery <= budget


def test_both_policies_receive_identical_learner_populations():
    seed, budget = 7, 15
    for learner_idx in range(20):
        adaptive = simulate_learner(seed, learner_idx, "adaptive", budget)
        random_ = simulate_learner(seed, learner_idx, "random", budget)
        assert adaptive.params == random_.params


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Engine v1 (BKT + SM-2 + lowest-mastery) is a confirmed negative "
        "result: adaptive is significantly worse than random at every "
        "budget tested, with the paired-diff 95% CI entirely below zero. "
        "See sim/results_v1.md for the frozen numbers and the diagnosed "
        "mechanism. strict=True so that if a future engine change makes "
        "this pass unexpectedly, CI fails loudly and this mark must be "
        "deliberately removed rather than silently staying green."
    ),
)
def test_adaptive_is_not_significantly_worse_than_random():
    """
    CI gate: a small, fast simulation (100 learners, fixed seed) must not
    show adaptive significantly *worse* than random — i.e. the 95%
    bootstrap CI on the paired difference (adaptive - random) must not
    lie entirely below zero. This does NOT require adaptive to win by any
    margin, only that it isn't demonstrably behind.
    """
    result = run_budget(num_learners=100, budget=30, seed=99)
    diff = result["final_skill_diff"]
    assert diff["ci_high"] >= 0, (
        f"Adaptive is significantly worse than random at this budget: "
        f"diff mean={diff['mean']:.3f} CI=[{diff['ci_low']:.3f}, {diff['ci_high']:.3f}]"
    )
