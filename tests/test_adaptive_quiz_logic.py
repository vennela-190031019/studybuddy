import os

import pytest

from adaptive_quiz.logic import (
    DEFAULT_POLICY,
    QuizBuildResult,
    assign_passage,
    build_evidence,
    build_llm_grounded_quiz,
    build_quiz,
    extract_supporting_sentence,
    grade_and_update_mastery,
    is_demo_mode,
    load_demo_document,
    load_demo_questions,
    locate_passage_span,
    ordered_concept_ids,
    plain_language_reason,
    render_notes_html,
)
from engine.grounding import Question
from src.schemas import Quiz, QuizQuestion


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


# ---------------------------------------------------------------------------
# Stage 5: build_llm_grounded_quiz / assign_passage.
#
# Every test below passes an explicit generate_quiz_fn stub — none of them
# ever let build_llm_grounded_quiz resolve its default (the real
# src.quiz_generator.generate_quiz), so no test in this file makes a
# network call. The real-API path is intentionally only exercised manually
# (see docs/FINDINGS.md's "Manual test checklist").
# ---------------------------------------------------------------------------

MITO_PASSAGE = (
    "Mitochondria are membrane-bound organelles found in most eukaryotic cells. "
    "The Mitochondria generate most of the cell's supply of adenosine triphosphate "
    "(ATP), used as a source of chemical energy."
)
PHOTOSYNTHESIS_PASSAGE = (
    "Photosynthesis is the process used by plants to convert light energy into "
    "chemical energy. During Photosynthesis, chlorophyll in the chloroplast "
    "absorbs sunlight."
)
PASSAGES = [MITO_PASSAGE, PHOTOSYNTHESIS_PASSAGE]


def _mc_question(id_, question, correct_answer):
    return QuizQuestion(id=id_, type="short_answer", question=question, correct_answer=correct_answer)


def test_assign_passage_picks_the_highest_overlap_passage():
    passage = assign_passage(
        "What molecule do mitochondria produce for energy?",
        "ATP (adenosine triphosphate)",
        PASSAGES,
    )
    assert passage == MITO_PASSAGE


def test_assign_passage_returns_none_when_nothing_overlaps():
    passage = assign_passage("What is the boiling point of mercury?", "356.7 degrees Celsius", PASSAGES)
    assert passage is None


def test_assign_passage_returns_none_for_no_passages():
    assert assign_passage("anything", "anything", []) is None


def test_assign_passage_ties_go_to_the_earliest_passage():
    identical = ["shared unique keyword alpha", "shared unique keyword alpha"]
    assert assign_passage("shared keyword alpha question", "answer", identical) == identical[0]


def test_question_supported_by_notes_is_kept():
    stub = lambda notes, num_questions=6: Quiz(
        questions=[
            _mc_question(1, "What molecule do mitochondria produce for energy?", "ATP (adenosine triphosphate)"),
        ]
    )
    result = build_llm_grounded_quiz("some notes", PASSAGES, generate_quiz_fn=stub)
    assert result.ok is True
    assert len(result.kept_questions) == 1
    assert result.kept_questions[0].citation == MITO_PASSAGE
    assert result.dropped_questions == []


def test_invented_unsupported_question_is_dropped_with_passage_and_reason():
    stub = lambda notes, num_questions=6: Quiz(
        questions=[
            _mc_question(
                1,
                "How many mitochondria exist in a typical human liver cell?",
                "Approximately 2000 mitochondria.",
            ),
        ]
    )
    result = build_llm_grounded_quiz("some notes", PASSAGES, generate_quiz_fn=stub)
    assert result.ok is True
    assert result.kept_questions == []
    assert len(result.dropped_questions) == 1

    dropped_question, reason = result.dropped_questions[0]
    assert dropped_question.citation == MITO_PASSAGE  # assignment still happened
    assert "overlap" in reason


def test_passage_assignment_is_deterministic_regardless_of_question_order():
    q_mito = _mc_question(1, "What molecule do mitochondria produce for energy?", "ATP (adenosine triphosphate)")
    q_photo = _mc_question(
        2, "What pigment absorbs sunlight during photosynthesis?", "Chlorophyll in the chloroplast."
    )

    stub_forward = lambda notes, num_questions=6: Quiz(questions=[q_mito, q_photo])
    stub_reversed = lambda notes, num_questions=6: Quiz(questions=[q_photo, q_mito])

    forward = build_llm_grounded_quiz("notes", PASSAGES, generate_quiz_fn=stub_forward)
    reversed_ = build_llm_grounded_quiz("notes", PASSAGES, generate_quiz_fn=stub_reversed)

    forward_citations = {q.id: q.citation for q in forward.kept_questions}
    reversed_citations = {q.id: q.citation for q in reversed_.kept_questions}
    assert forward_citations == reversed_citations == {"1": MITO_PASSAGE, "2": PHOTOSYNTHESIS_PASSAGE}


def test_generator_exception_returns_clear_error_and_no_questions():
    def stub(notes, num_questions=6):
        raise RuntimeError("the model API is down")

    result = build_llm_grounded_quiz("notes", PASSAGES, generate_quiz_fn=stub)
    assert result.ok is False
    assert "the model API is down" in result.error
    assert result.kept_questions == []
    assert result.dropped_questions == []


def test_malformed_output_missing_fields_returns_clear_error():
    class BrokenQuestion:
        id = 1
        question = "What is X?"
        # no correct_answer attribute at all

    class BrokenQuiz:
        questions = [BrokenQuestion()]

    result = build_llm_grounded_quiz("notes", PASSAGES, generate_quiz_fn=lambda notes, num_questions=6: BrokenQuiz())
    assert result.ok is False
    assert result.error
    assert result.kept_questions == []


def test_malformed_output_wrong_type_returns_clear_error():
    # generate_quiz_fn returns something with no .questions at all
    result = build_llm_grounded_quiz(
        "notes", PASSAGES, generate_quiz_fn=lambda notes, num_questions=6: "not a quiz object"
    )
    assert result.ok is False
    assert result.error


def test_malformed_output_empty_list_returns_clear_error():
    result = build_llm_grounded_quiz(
        "notes", PASSAGES, generate_quiz_fn=lambda notes, num_questions=6: Quiz(questions=[])
    )
    assert result.ok is False
    assert "no usable questions" in result.error


def test_demo_path_still_works_with_no_api_key(no_api_key):
    # build_llm_grounded_quiz is independent of demo mode / env vars by
    # design (it only runs when the page decides a key is present), and
    # the existing demo/template path (build_quiz) is untouched by stage 5.
    result = build_quiz(document_text=None)
    assert result.demo_mode is True
    assert result.document_text == load_demo_document()


# ---------------------------------------------------------------------------
# Stage 6, Part A: evidence view (span location, sentence extraction, HTML
# escaping).
# ---------------------------------------------------------------------------


def test_locate_passage_span_exact_match():
    notes = "Intro paragraph.\n\nMitochondria produce ATP for the cell.\n\nOutro paragraph."
    passage = "Mitochondria produce ATP for the cell."
    span = locate_passage_span(notes, passage)
    assert span is not None
    start, end = span
    assert notes[start:end] == passage


def test_locate_passage_span_handles_whitespace_differences():
    notes = "Intro.\n\nMitochondria   produce\nATP for   the cell.\n\nOutro."
    passage = "Mitochondria produce ATP for the cell."
    span = locate_passage_span(notes, passage)
    assert span is not None
    start, end = span
    # the original (whitespace-irregular) substring is returned, not the
    # normalized passage string
    assert notes[start:end] == "Mitochondria   produce\nATP for   the cell."


def test_locate_passage_span_returns_none_when_not_found():
    notes = "This text is about photosynthesis and chlorophyll."
    passage = "This sentence does not appear anywhere in the notes at all."
    assert locate_passage_span(notes, passage) is None


def test_locate_passage_span_handles_empty_inputs():
    assert locate_passage_span("", "something") is None
    assert locate_passage_span("something", "") is None


def test_extract_supporting_sentence_picks_best_matching_sentence():
    passage = (
        "Mitochondria are membrane-bound organelles. "
        "Mitochondria generate ATP for the cell. "
        "Chloroplasts are found only in plants."
    )
    sentence = extract_supporting_sentence(
        "What do mitochondria generate?", "ATP", passage
    )
    assert sentence == "Mitochondria generate ATP for the cell."


def test_build_evidence_locates_sentence_in_original_notes():
    notes = "Para one.\n\nMitochondria generate ATP for the cell. They are tiny.\n\nPara three."
    questions = [
        Question(
            id="mito",
            question="What do mitochondria generate?",
            answer="ATP",
            citation="Mitochondria generate ATP for the cell. They are tiny.",
        )
    ]
    evidence = build_evidence(notes, questions)
    assert evidence["mito"].sentence == "Mitochondria generate ATP for the cell."
    assert evidence["mito"].span is not None
    start, end = evidence["mito"].span
    assert notes[start:end] == "Mitochondria generate ATP for the cell."


def test_render_notes_html_escapes_untrusted_notes_with_no_highlight():
    notes = "Click <script>alert('x')</script> here."
    output = render_notes_html(notes, None)
    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_render_notes_html_escapes_untrusted_notes_with_highlight():
    notes = "before <img src=x onerror=alert(1)> after"
    # highlight exactly the malicious-looking span
    start = notes.index("<img")
    end = start + len("<img src=x onerror=alert(1)>")
    output = render_notes_html(notes, (start, end))

    assert "<img" not in output
    assert "onerror=alert(1)>" not in output
    assert "&lt;img" in output
    # our own wrapper tag is legitimately present as literal HTML
    assert '<mark class="aq-highlight">' in output
    assert "</mark>" in output


def test_render_notes_html_highlighted_text_is_escaped_not_raw():
    notes = "The passage says: 5 < 10 and 10 > 5, which is true."
    start = notes.index("5 < 10")
    end = start + len("5 < 10")
    output = render_notes_html(notes, (start, end))
    assert "5 &lt; 10" in output
    assert "5 < 10" not in output


def test_plain_language_reason_translates_known_reasons():
    assert "No matching passage" in plain_language_reason("no citation provided")
    assert "didn't share enough wording" in plain_language_reason("keyword overlap 0.00 < 0.4")
