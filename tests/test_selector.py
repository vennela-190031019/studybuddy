import random

from engine.selector import ConceptState, random_selector, round_robin_selector, select_next


def test_select_next_prefers_due_low_mastery_concept():
    states = [
        ConceptState("b-high-mastery-but-due", mastery=0.9, due=True),
        ConceptState("a-low-mastery-not-due", mastery=0.1, due=False),
        ConceptState("c-due-and-lowest", mastery=0.3, due=True),
    ]
    picked = select_next(states)
    assert picked.concept_id == "c-due-and-lowest"


def test_select_next_ignores_non_due_concepts_entirely():
    states = [
        ConceptState("not-due", mastery=0.0, due=False),
        ConceptState("due", mastery=0.8, due=True),
    ]
    picked = select_next(states)
    assert picked.concept_id == "due"


def test_select_next_returns_none_when_nothing_due():
    states = [ConceptState("x", mastery=0.1, due=False)]
    assert select_next(states) is None


def test_select_next_breaks_ties_deterministically_by_concept_id():
    states_a = [
        ConceptState("zebra", mastery=0.5, due=True),
        ConceptState("apple", mastery=0.5, due=True),
    ]
    states_b = list(reversed(states_a))

    assert select_next(states_a).concept_id == "apple"
    assert select_next(states_b).concept_id == "apple"


def test_random_selector_is_reproducible_for_a_fixed_seed():
    states = [
        ConceptState("a", mastery=0.5, due=True),
        ConceptState("b", mastery=0.2, due=True),
        ConceptState("c", mastery=0.8, due=True),
    ]

    picks_1 = [random_selector(states, random.Random(42)).concept_id for _ in range(10)]
    picks_2 = [random_selector(states, random.Random(42)).concept_id for _ in range(10)]
    assert picks_1 == picks_2


def test_random_selector_only_picks_due_concepts():
    states = [
        ConceptState("due-1", mastery=0.5, due=True),
        ConceptState("due-2", mastery=0.5, due=True),
        ConceptState("not-due", mastery=0.0, due=False),
    ]
    rng = random.Random(0)
    for _ in range(50):
        picked = random_selector(states, rng)
        assert picked.due is True


def test_random_selector_returns_none_when_nothing_due():
    states = [ConceptState("x", mastery=0.1, due=False)]
    assert random_selector(states, random.Random(0)) is None


def test_round_robin_selector_is_deterministic():
    concept_ids = ["a", "b", "c"]
    picks_1 = [round_robin_selector(concept_ids, step) for step in range(20)]
    picks_2 = [round_robin_selector(concept_ids, step) for step in range(20)]
    assert picks_1 == picks_2


def test_round_robin_selector_cycles_in_fixed_order():
    concept_ids = ["a", "b", "c"]
    picks = [round_robin_selector(concept_ids, step) for step in range(7)]
    assert picks == ["a", "b", "c", "a", "b", "c", "a"]


def test_round_robin_selector_covers_all_concepts_evenly():
    concept_ids = ["a", "b", "c", "d"]
    cycles = 25
    counts = {cid: 0 for cid in concept_ids}
    for step in range(len(concept_ids) * cycles):
        counts[round_robin_selector(concept_ids, step)] += 1
    assert all(count == cycles for count in counts.values())


def test_round_robin_selector_rejects_empty_concept_list():
    import pytest

    with pytest.raises(ValueError):
        round_robin_selector([], step=0)
