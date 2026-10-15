import os

import pytest

from adaptive_quiz.logic import (
    DEFAULT_POLICY,
    QuizBuildResult,
    build_quiz,
    grade_and_update_mastery,
    is_demo_mode,
    load_demo_document,
    load_demo_questions,
    ordered_concept_ids,
)
from engine.grounding import Question


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")


def test_demo_mode_is_active_when_no_key_is_set(no_api_key):
    assert is_demo_mode() is True


def test_demo_mode_is_inactive_when_key_is_set(with_api_key):
    assert is_demo_mode() is False


def test_build_quiz_selects_the_fixture_when_no_key_is_set(no_api_key):
    result = build_quiz(document_text=None)
    assert result.demo_mode is True
    assert result.document_text == load_demo_document()

    fixture_ids = {q.id for q in load_demo_questions()}
    seen_ids = {q.id for q, _ in result.dropped_questions} | {q.id for q in result.kept_questions}
    assert seen_ids == fixture_ids


def test_build_quiz_ignores_uploaded_text_in_demo_mode(no_api_key):
    result = build_quiz(document_text="Some completely different uploaded text about volcanoes.")
    assert result.demo_mode is True
    assert result.document_text == load_demo_document()


def test_build_quiz_does_not_silently_fall_back_to_fixture_when_key_is_set_and_text_is_empty(with_api_key):
    result = build_quiz(document_text="")
    assert result.demo_mode is False
    assert result.kept_questions == []
    assert result.dropped_questions == []


def test_build_quiz_uses_uploaded_text_when_key_is_set(with_api_key):
    text = (
        "Supervised learning trains a model on labeled examples. Supervised learning is "
        "common in classification tasks.\n\n"
        "Unsupervised learning finds structure in unlabeled data. Unsupervised learning "
        "does not require labels."
    )
    result = build_quiz(document_text=text)
    assert result.demo_mode is False
    assert result.document_text == text


def test_rejected_questions_are_never_in_kept_questions():
    result = build_quiz(document_text=None, demo_mode=True)
    kept_ids = {q.id for q in result.kept_questions}
    dropped_ids = {q.id for q, _ in result.dropped_questions}
    assert kept_ids.isdisjoint(dropped_ids)
    # the fixture's deliberately ungrounded question must actually be dropped
    assert "dna" in dropped_ids
    assert "dna" not in kept_ids


def test_dropped_questions_never_appear_in_quiz_ordering():
    result = build_quiz(document_text=None, demo_mode=True)
    ordered = ordered_concept_ids(result.kept_questions)
    dropped_ids = {q.id for q, _ in result.dropped_questions}
    assert dropped_ids.isdisjoint(set(ordered))


def test_round_robin_is_the_default_policy():
    assert DEFAULT_POLICY == "round_robin"


def test_default_ordering_matches_round_robin_explicitly():
    questions = [
        Question(id="a", question="q-a", answer="x", citation="c"),
        Question(id="b", question="q-b", answer="x", citation="c"),
        Question(id="c", question="q-c", answer="x", citation="c"),
    ]
    assert ordered_concept_ids(questions) == ordered_concept_ids(questions, policy="round_robin")


def test_grade_and_update_mastery_tracks_correctness_and_review_list():
    questions = [
        Question(id="a", question="What is X?", answer="apple banana cherry", citation="c"),
        Question(id="b", question="What is Y?", answer="dog elephant falcon", citation="c"),
    ]
    answers = {"a": "apple banana cherry please", "b": "totally unrelated nonsense"}
    mastery, review, correctness = grade_and_update_mastery(questions, answers)

    assert correctness["a"] is True
    assert correctness["b"] is False
    assert 0.0 <= mastery["a"] <= 1.0
    assert 0.0 <= mastery["b"] <= 1.0
    assert mastery["a"] > mastery["b"]
    assert "b" in review
