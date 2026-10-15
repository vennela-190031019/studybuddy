"""
Logic for the Adaptive Quiz Streamlit page (pages/1_Adaptive_Quiz.py).
Deliberately Streamlit-free so it's directly unit-testable — the page
file itself should only call into here and render the results.

Pipeline: document text -> concepts (engine.concepts) -> candidate
questions -> grounding verification (engine.grounding, MockGroundingVerifier
— free, deterministic) -> kept questions presented in the quiz, dropped
questions listed separately -> round_robin_selector decides question
order -> engine.mastery (BKT) tracks a per-concept mastery estimate as
the learner answers.

Two question-generation paths:
  - No OPENAI_API_KEY: demo/template path (build_quiz) — bundled fixture
    document + fixture questions, or a deterministic free template
    generator over the user's own text. Never calls an LLM, never costs
    anything.
  - OPENAI_API_KEY present and notes supplied: build_llm_grounded_quiz
    calls the EXISTING, real src.quiz_generator.generate_quiz() (the
    same function app.py's main quiz uses), then runs every generated
    question through the same free, deterministic MockGroundingVerifier
    before anything reaches the quiz — so the LLM only ever gets to
    *propose* questions; grounding decides what the learner actually sees.

Evidence view: for each kept question, build_evidence() locates the
specific sentence (within its assigned passage) that best supports it,
and its character span inside the original notes — so the page can
highlight exactly what's being cited rather than a whole paragraph.
Notes are untrusted user text; render_notes_html() escapes all of it
before embedding it in HTML, so highlighting can never inject markup.

CAVEAT, stated plainly: build_llm_grounded_quiz's real-API code path
(generate_quiz actually calling OpenAI) is NOT exercised by this
project's automated tests or CI — tests inject a stub generator so no
network call is ever made in CI. It has only been verified with
generate_quiz replaced by a stub. See docs/FINDINGS.md's "Manual test
checklist" to validate it yourself against the real API with your own
key. This mirrors the same "adapter behind the same interface,
explicitly untested until run" caveat already used for
engine/grounding.py's LLMGroundingVerifier.
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from engine.concepts import Concept, extract_concepts
from engine.grounding import MockGroundingVerifier, Question, filter_grounded
from engine.mastery import DEFAULT_PARAMS
from engine.mastery import update as bkt_update
from engine.selector import round_robin_selector

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_POLICY = "round_robin"
AVAILABLE_POLICIES = ["round_robin", "random", "lowest_mastery"]
MASTERY_REVIEW_THRESHOLD = 0.6

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "of", "in", "on", "at", "for", "with", "as",
    "to", "from", "by", "that", "this", "these", "those", "it", "its",
    "what", "which", "who", "when", "where", "how", "why", "do", "does",
    "did", "has", "have", "had", "can", "could", "would", "should", "will",
}


def is_demo_mode() -> bool:
    """Demo mode is active whenever no OPENAI_API_KEY is configured."""
    return not bool(os.environ.get("OPENAI_API_KEY", "").strip())


def load_demo_document() -> str:
    return (FIXTURES_DIR / "sample_document.txt").read_text()


def load_demo_questions() -> list[Question]:
    data = json.loads((FIXTURES_DIR / "sample_questions.json").read_text())
    return [
        Question(id=item["id"], question=item["question"], answer=item["answer"], citation=item["citation"])
        for item in data
    ]


def generate_template_questions(concepts: list[Concept]) -> list[Question]:
    """One question per concept, citing its first source passage verbatim."""
    questions = []
    for concept in concepts:
        if not concept.passages:
            continue
        passage = concept.passages[0]
        questions.append(
            Question(
                id=concept.id,
                question=f"Based on the text, what does it say about {concept.name}?",
                answer=passage,
                citation=passage,
            )
        )
    return questions


@dataclass(frozen=True)
class QuizBuildResult:
    document_text: str
    demo_mode: bool
    kept_questions: list[Question]
    dropped_questions: list[tuple[Question, str]]


def build_quiz(document_text: str | None, demo_mode: bool | None = None) -> QuizBuildResult:
    """
    If demo_mode (explicitly passed, or auto-detected via is_demo_mode()
    when not passed), loads the bundled sample document + fixture
    questions, regardless of document_text. Otherwise runs document_text
    through concept extraction and template question generation — if
    document_text is empty in that case, returns an empty result rather
    than silently falling back to the fixture, so the demo-mode banner
    (driven by is_demo_mode() alone) never disagrees with what a given
    quiz build actually used. Either way, every candidate question is
    run through the (free, deterministic) grounding verifier before
    being split into kept vs. dropped.
    """
    if demo_mode is None:
        demo_mode = is_demo_mode()

    if demo_mode:
        text = load_demo_document()
        candidates = load_demo_questions()
    else:
        text = document_text or ""
        candidates = generate_template_questions(extract_concepts(text)) if text.strip() else []

    kept, dropped = filter_grounded(candidates, MockGroundingVerifier())
    return QuizBuildResult(
        document_text=text,
        demo_mode=demo_mode,
        kept_questions=kept,
        dropped_questions=dropped,
    )


def ordered_concept_ids(questions: list[Question], policy: str = DEFAULT_POLICY) -> list[str]:
    """Decides the order questions are presented in. round_robin is the
    default — the baseline that won the stage 3 simulation
    (docs/FINDINGS.md) — included as literal cycling through the
    available concepts; "random" and "lowest_mastery" (v1's tie-break
    order, since there's no evidence yet to rank by) are offered for
    comparison, not as defaults."""
    concept_ids = [q.id for q in questions]
    if policy == "round_robin":
        return [round_robin_selector(concept_ids, step) for step in range(len(concept_ids))]
    if policy == "random":
        import random

        rng = random.Random(0)
        shuffled = list(concept_ids)
        rng.shuffle(shuffled)
        return shuffled
    if policy == "lowest_mastery":
        return sorted(concept_ids)
    raise ValueError(f"unknown policy: {policy!r}")


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def grade_answer(question: Question, user_answer: str) -> bool:
    """Free, deterministic grading: correct if the learner's answer
    shares enough keywords with the model answer. Same style of heuristic
    as engine.grounding.MockGroundingVerifier, intentionally — no LLM call."""
    user_keywords = _keywords(user_answer or "")
    if not user_keywords:
        return False
    answer_keywords = _keywords(question.answer)
    if not answer_keywords:
        return False
    overlap = user_keywords & answer_keywords
    return len(overlap) / len(answer_keywords) >= 0.3


def grade_and_update_mastery(
    questions: list[Question],
    answers: dict[str, str],
    mastery: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[str], dict[str, bool]]:
    """
    Grades every question against the learner's answers, updates a
    per-concept BKT mastery estimate (engine.mastery, same defaults as
    the simulation), and returns (mastery, concepts_to_review, correctness).
    """
    mastery = dict(mastery) if mastery else {}
    correctness: dict[str, bool] = {}

    for question in questions:
        mastery.setdefault(question.id, DEFAULT_PARAMS.p_init)
        correct = grade_answer(question, answers.get(question.id, ""))
        correctness[question.id] = correct
        mastery[question.id] = bkt_update(mastery[question.id], correct)

    concepts_to_review = [cid for cid, m in mastery.items() if m < MASTERY_REVIEW_THRESHOLD]
    return mastery, concepts_to_review, correctness


def assign_passage(question_text: str, answer_text: str, passages: list[str]) -> str | None:
    """
    Deterministic word-overlap match: scores each passage by how many
    keywords it shares with (question_text + answer_text), and returns
    the passage with the highest score. Ties go to the earliest passage
    in the list (strict ">" below, so an equal-scoring later passage
    never displaces an earlier one) — deterministic regardless of
    question order, since each call only depends on its own arguments.
    Returns None if there are no passages, or none share any keyword
    with the question/answer at all.
    """
    if not passages:
        return None
    target_keywords = _keywords(question_text) | _keywords(answer_text)
    if not target_keywords:
        return None

    best_passage: str | None = None
    best_score = 0
    for passage in passages:
        score = len(target_keywords & _keywords(passage))
        if score > best_score:
            best_score = score
            best_passage = passage
    return best_passage


@dataclass(frozen=True)
class LLMQuizBuildResult:
    ok: bool
    error: str | None
    generated_count: int
    kept_questions: list[Question]
    dropped_questions: list[tuple[Question, str]]


def build_llm_grounded_quiz(
    notes: str,
    passages: list[str],
    num_questions: int = 6,
    generate_quiz_fn=None,
) -> LLMQuizBuildResult:
    """
    Calls generate_quiz_fn (defaults to the real, existing
    src.quiz_generator.generate_quiz — see the module docstring's
    caveat: that real-API path is not exercised by this project's tests)
    to get LLM-written questions, assigns each one its best-matching
    source passage by deterministic word overlap (assign_passage), then
    runs every question through the free, deterministic
    MockGroundingVerifier before anything reaches the quiz.

    Any exception from the generator, or any malformed output (missing
    fields, wrong type, an empty question list), is caught here and
    turned into a clear ok=False error result — this function never
    raises, and it never falls back to any other question source; the
    caller (the page) is expected to show the error and stop, not
    silently substitute the template/demo path.
    """
    if generate_quiz_fn is None:
        from src.quiz_generator import generate_quiz as generate_quiz_fn

    try:
        quiz = generate_quiz_fn(notes, num_questions=num_questions)
        raw_questions = list(quiz.questions)
        candidates = []
        for raw in raw_questions:
            question_id = str(raw.id)
            question_text = str(raw.question).strip()
            answer_text = str(raw.correct_answer).strip()
            if not question_text or not answer_text:
                raise ValueError(f"question {question_id!r} is missing question/answer text")
            passage = assign_passage(question_text, answer_text, passages)
            candidates.append(
                Question(id=question_id, question=question_text, answer=answer_text, citation=passage)
            )
    except Exception as exc:
        return LLMQuizBuildResult(
            ok=False,
            error=f"Question generation failed or returned malformed output: {exc}",
            generated_count=0,
            kept_questions=[],
            dropped_questions=[],
        )

    if not candidates:
        return LLMQuizBuildResult(
            ok=False,
            error="The generator returned no usable questions.",
            generated_count=0,
            kept_questions=[],
            dropped_questions=[],
        )

    kept, dropped = filter_grounded(candidates, MockGroundingVerifier())
    return LLMQuizBuildResult(
        ok=True,
        error=None,
        generated_count=len(candidates),
        kept_questions=kept,
        dropped_questions=dropped,
    )


# ---------------------------------------------------------------------------
# Evidence view: locating a cited passage/sentence inside the original
# notes text, so the UI can highlight exactly what supports each question.
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _normalize_with_positions(text: str) -> tuple[str, list[int]]:
    """
    Collapses whitespace runs to a single space and strips the ends,
    like `" ".join(text.split())`, but also returns a parallel list where
    positions[k] is the index in the ORIGINAL text that normalized
    character k came from — so a match found in the normalized string can
    be mapped back to a span in the original string.
    """
    normalized_chars: list[str] = []
    positions: list[int] = []
    prev_was_space = True  # treat the start as "after a space" so leading whitespace is dropped, not collapsed into a leading " "

    for i, ch in enumerate(text):
        if ch.isspace():
            if not prev_was_space:
                normalized_chars.append(" ")
                positions.append(i)
                prev_was_space = True
        else:
            normalized_chars.append(ch)
            positions.append(i)
            prev_was_space = False

    while normalized_chars and normalized_chars[-1] == " ":
        normalized_chars.pop()
        positions.pop()

    return "".join(normalized_chars), positions


def locate_passage_span(notes: str, passage: str) -> tuple[int, int] | None:
    """
    Finds `passage` inside `notes` and returns its (start, end) character
    span in `notes`. Tries an exact substring match first; if that fails,
    falls back to a whitespace-normalized match (so differences in
    spacing/newlines between the stored passage and the live notes text
    don't block highlighting) mapped back to the original indices. Never
    guesses: returns None if neither match succeeds.
    """
    if not notes or not passage:
        return None

    exact_index = notes.find(passage)
    if exact_index != -1:
        return (exact_index, exact_index + len(passage))

    normalized_notes, notes_positions = _normalize_with_positions(notes)
    normalized_passage, _ = _normalize_with_positions(passage)
    if not normalized_passage:
        return None

    match_index = normalized_notes.find(normalized_passage)
    if match_index == -1:
        return None

    start = notes_positions[match_index]
    end = notes_positions[match_index + len(normalized_passage) - 1] + 1
    return (start, end)


def extract_supporting_sentence(question_text: str, answer_text: str, passage: str) -> str:
    """
    Splits `passage` into sentences and returns the single sentence with
    the highest keyword overlap against (question_text + answer_text) —
    the most specific unit of evidence to highlight/quote, rather than
    the whole (possibly multi-sentence) passage. Ties go to the earliest
    sentence. Falls back to the whole passage if it has no sentence
    boundaries or no sentence shares any keyword.
    """
    if not passage or not passage.strip():
        return passage

    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(passage.strip()) if s.strip()]
    if len(sentences) <= 1:
        return passage.strip()

    target_keywords = _keywords(question_text) | _keywords(answer_text)
    if not target_keywords:
        return sentences[0]

    best_sentence = sentences[0]
    best_score = -1
    for sentence in sentences:
        score = len(target_keywords & _keywords(sentence))
        if score > best_score:
            best_score = score
            best_sentence = sentence
    return best_sentence


@dataclass(frozen=True)
class Evidence:
    question_id: str
    sentence: str
    span: tuple[int, int] | None


def build_evidence(notes: str, questions: list[Question]) -> dict[str, Evidence]:
    """One Evidence entry per question: its best-supporting sentence
    (from its assigned passage) and that sentence's span in `notes`, or
    span=None if it couldn't be located (never guessed)."""
    evidence: dict[str, Evidence] = {}
    for question in questions:
        sentence = extract_supporting_sentence(question.question, question.answer, question.citation or "")
        span = locate_passage_span(notes, sentence) if sentence else None
        evidence[question.id] = Evidence(question_id=question.id, sentence=sentence, span=span)
    return evidence


def render_notes_html(notes: str, highlight_span: tuple[int, int] | None) -> str:
    """
    Renders `notes` as HTML with the character range `highlight_span`
    wrapped in a <mark>. The notes are untrusted user text: every piece
    of it is passed through html.escape() before being placed in the
    output, including the highlighted portion — only the <mark> wrapper
    itself is literal HTML that this function controls, so no markup
    from the notes can ever reach the page unescaped.
    """
    if not highlight_span:
        return f'<div class="aq-notes">{html.escape(notes)}</div>'

    start, end = highlight_span
    before = html.escape(notes[:start])
    highlighted = html.escape(notes[start:end])
    after = html.escape(notes[end:])
    return f'<div class="aq-notes">{before}<mark class="aq-highlight">{highlighted}</mark>{after}</div>'


def plain_language_reason(reason: str) -> str:
    """Translates engine.grounding's technical verifier reason strings
    into a short, plain-language explanation for display."""
    if "no citation" in reason:
        return "No matching passage was found in your notes."
    if "overlap" in reason:
        return "The question and the passage didn't share enough wording to confirm support."
    return reason
