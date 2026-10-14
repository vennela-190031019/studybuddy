"""
Grounding for generated questions: every question should cite the source
passage it was generated from, and a verifier checks that the question is
actually answerable from that passage alone before it's allowed into a quiz.

Two verifiers share one interface (`GroundingVerifier`):

- `MockGroundingVerifier` — deterministic, free, no network call. Used by
  tests, CI, and evals/grounding_cases.yaml. The rule is keyword overlap
  between (question + answer) and the cited passage: it's a coarse proxy
  for "answerable from the passage alone," not real entailment checking,
  so it will have real false positives/negatives (see the eval report).
- `LLMGroundingVerifier` — adapter that asks a real LLM the same question.
  UNTESTED: this has not been run against a live API key in this session.
  Exercise it yourself before relying on it.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "of", "in", "on", "at", "for", "with", "as",
    "to", "from", "by", "that", "this", "these", "those", "it", "its",
    "what", "which", "who", "when", "where", "how", "why", "do", "does",
    "did", "has", "have", "had", "can", "could", "would", "should", "will",
    "main", "used", "into", "than", "also", "their", "they", "them",
}


@dataclass
class Question:
    id: str
    question: str
    answer: str
    citation: str | None = None


@dataclass
class VerificationResult:
    grounded: bool
    reason: str


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


class GroundingVerifier(ABC):
    @abstractmethod
    def verify(self, question: Question) -> VerificationResult: ...


class MockGroundingVerifier(GroundingVerifier):
    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold

    def verify(self, question: Question) -> VerificationResult:
        if not question.citation or not question.citation.strip():
            return VerificationResult(False, "no citation provided")

        qa_keywords = _keywords(question.question) | _keywords(question.answer)
        if not qa_keywords:
            return VerificationResult(False, "question/answer had no extractable keywords")

        citation_keywords = _keywords(question.citation)
        overlap = qa_keywords & citation_keywords
        ratio = len(overlap) / len(qa_keywords)

        if ratio >= self.threshold:
            return VerificationResult(True, f"keyword overlap {ratio:.2f} >= {self.threshold}")
        return VerificationResult(False, f"keyword overlap {ratio:.2f} < {self.threshold}")


class LLMGroundingVerifier(GroundingVerifier):
    """
    UNTESTED (not run against a live API key in this session). Review and
    exercise this yourself before relying on it — it has the same
    interface as MockGroundingVerifier so it's a drop-in swap once verified.
    """

    def __init__(self, model: str | None = None):
        self.model = model

    def verify(self, question: Question) -> VerificationResult:
        from src.llm_client import call_llm_json  # local import: optional, paid dependency

        if not question.citation or not question.citation.strip():
            return VerificationResult(False, "no citation provided")

        system_prompt = (
            "You verify whether a quiz question is answerable using ONLY the "
            "provided passage, with no outside knowledge. Respond with JSON only."
        )
        user_prompt = (
            f"Passage:\n{question.citation}\n\n"
            f"Question: {question.question}\n"
            f"Answer: {question.answer}\n\n"
            'Respond with JSON in exactly this shape: '
            '{"grounded": true|false, "reason": "one sentence"}'
        )
        data = call_llm_json(system_prompt, user_prompt, model=self.model)
        return VerificationResult(bool(data.get("grounded")), data.get("reason", ""))


def filter_grounded(
    questions: list[Question], verifier: GroundingVerifier
) -> tuple[list[Question], list[tuple[Question, str]]]:
    """Returns (kept, dropped) where dropped pairs each question with the
    reason its citation didn't verify."""
    kept: list[Question] = []
    dropped: list[tuple[Question, str]] = []
    for q in questions:
        result = verifier.verify(q)
        if result.grounded:
            kept.append(q)
        else:
            dropped.append((q, result.reason))
    return kept, dropped
