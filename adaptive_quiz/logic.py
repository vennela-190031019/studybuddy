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

Question generation is a deterministic, free template (one question per
concept, citing its source passage verbatim) — never an LLM call. This
page never spends API credits, whether or not OPENAI_API_KEY is set; the
key's only effect here is choosing demo vs. your-own-document mode. A
real LLM-based generator would be natural future work, following the
same "adapter behind the same interface, explicitly untested until run"
pattern used for engine/grounding.py's LLMGroundingVerifier.
"""
from __future__ import annotations

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
