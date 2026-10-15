from sim.engine_v2_sim import simulate_learner


def test_v2_simulation_is_deterministic_for_a_fixed_seed():
    outcome_1 = simulate_learner(seed=123, learner_idx=4, policy="v2", budget=40)
    outcome_2 = simulate_learner(seed=123, learner_idx=4, policy="v2", budget=40)
    assert outcome_1 == outcome_2


def test_v2_simulation_is_deterministic_across_variants():
    for variant in ("linear", "sqrt", "fixed"):
        a = simulate_learner(seed=5, learner_idx=1, policy="v2", budget=30, v2_variant=variant)
        b = simulate_learner(seed=5, learner_idx=1, policy="v2", budget=30, v2_variant=variant)
        assert a == b


def test_v2_final_skill_and_min_skill_stay_in_unit_interval():
    for learner_idx in range(10):
        outcome = simulate_learner(seed=9, learner_idx=learner_idx, policy="v2", budget=60)
        assert 0.0 <= outcome.final_mean_true_skill <= 1.0
        assert 0.0 <= outcome.min_per_concept_skill <= 1.0
        assert outcome.min_per_concept_skill <= outcome.final_mean_true_skill


def test_v1_v2_and_random_policies_use_identical_learner_populations():
    seed, budget = 3, 20
    for learner_idx in range(10):
        outcomes = [
            simulate_learner(seed, learner_idx, policy, budget) for policy in ("random", "v1", "v2")
        ]
        assert outcomes[0].params == outcomes[1].params == outcomes[2].params
