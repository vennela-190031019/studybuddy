from engine.selector_v2 import CoverageConceptState, select_next


def test_prefers_lowest_decayed_mastery_when_coverage_is_equal():
    states = [
        CoverageConceptState("a", decayed_mastery=0.8, due=True, practice_count=2),
        CoverageConceptState("b", decayed_mastery=0.2, due=True, practice_count=2),
    ]
    picked = select_next(states)
    assert picked.concept_id == "b"


def test_coverage_penalty_can_override_a_slightly_lower_mastery():
    # "a" has much lower decayed mastery but has been hammered with
    # practice far more than "b" — the coverage penalty should be able to
    # push selection toward the under-practiced concept.
    states = [
        CoverageConceptState("a", decayed_mastery=0.3, due=True, practice_count=50),
        CoverageConceptState("b", decayed_mastery=0.5, due=True, practice_count=0),
    ]
    picked = select_next(states, variant="sqrt", penalty_weight=0.5)
    assert picked.concept_id == "b"


def test_ignores_non_due_concepts():
    states = [
        CoverageConceptState("a", decayed_mastery=0.9, due=False, practice_count=0),
        CoverageConceptState("b", decayed_mastery=0.95, due=True, practice_count=0),
    ]
    picked = select_next(states)
    assert picked.concept_id == "b"


def test_returns_none_when_nothing_due():
    states = [CoverageConceptState("a", decayed_mastery=0.1, due=False, practice_count=0)]
    assert select_next(states) is None


def test_ties_break_deterministically_by_concept_id():
    states_a = [
        CoverageConceptState("zebra", decayed_mastery=0.5, due=True, practice_count=3),
        CoverageConceptState("apple", decayed_mastery=0.5, due=True, practice_count=3),
    ]
    states_b = list(reversed(states_a))
    assert select_next(states_a).concept_id == "apple"
    assert select_next(states_b).concept_id == "apple"


def test_is_a_pure_deterministic_function_of_its_inputs():
    states = [
        CoverageConceptState("a", decayed_mastery=0.4, due=True, practice_count=3),
        CoverageConceptState("b", decayed_mastery=0.6, due=True, practice_count=1),
        CoverageConceptState("c", decayed_mastery=0.5, due=True, practice_count=0),
    ]
    for variant in ("linear", "sqrt", "fixed"):
        picks = [select_next(states, variant=variant).concept_id for _ in range(10)]
        assert len(set(picks)) == 1
