"""
Extracts a list of concepts (candidate terms) from uploaded document text,
along with the source passages that mention each one.

Deterministic, no LLM call: a "concept" here is a capitalized term or
phrase that recurs at least twice in the document. This is a coarse proxy
for "important term" that works reasonably well on lecture notes and
textbook chapters (which tend to introduce and then repeat key terms), and
it costs nothing to run — no API key, no network call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Capitalized sentence-starters that shouldn't be treated as concepts on
# their own (e.g. "The" at the start of "The mitochondria..." isn't a term).
_LEADING_STOPWORDS = {
    "the", "this", "that", "these", "those", "it", "a", "an", "in", "on",
    "at", "for", "with", "as", "if", "when", "while", "because", "however",
    "therefore", "thus", "so", "but", "and", "or", "unlike", "during",
    "after", "before", "since", "although", "though",
}

_CANDIDATE_RE = re.compile(r"\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,3}\b")


@dataclass
class Concept:
    id: str
    name: str
    passages: list[str] = field(default_factory=list)


def split_passages(text: str) -> list[str]:
    """Paragraph-based split — one passage per blank-line-separated block."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "concept"


def _normalize_candidate(raw: str) -> str | None:
    """Drops a leading generic word (e.g. "The Cell" -> "Cell"); returns
    None if nothing meaningful is left or the whole candidate is generic."""
    words = raw.split()
    while words and words[0].lower() in _LEADING_STOPWORDS:
        words = words[1:]
    if not words:
        return None
    return " ".join(words)


def extract_concepts(text: str, max_concepts: int = 20, min_occurrences: int = 2) -> list[Concept]:
    """
    Finds candidate terms (capitalized words/phrases) that occur at least
    `min_occurrences` times in `text`, and attaches the passages that
    mention each one.
    """
    passages = split_passages(text)

    first_seen_casing: dict[str, str] = {}
    counts: dict[str, int] = {}

    for match in _CANDIDATE_RE.finditer(text):
        candidate = _normalize_candidate(match.group())
        if not candidate:
            continue
        key = candidate.lower()
        counts[key] = counts.get(key, 0) + 1
        first_seen_casing.setdefault(key, candidate)

    kept_keys = [k for k, c in counts.items() if c >= min_occurrences]
    kept_keys.sort(key=lambda k: (-counts[k], k))
    kept_keys = kept_keys[:max_concepts]

    concepts: list[Concept] = []
    for key in kept_keys:
        name = first_seen_casing[key]
        pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        matching_passages = [p for p in passages if pattern.search(p)]
        concepts.append(Concept(id=_slugify(name), name=name, passages=matching_passages))

    return concepts
