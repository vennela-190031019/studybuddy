"""
Generates a quiz (mix of multiple-choice and short-answer questions) from
a block of notes text, using structured JSON output validated by Pydantic.
"""
from src.llm_client import call_llm_json
from src.schemas import Quiz, QuizQuestion

SYSTEM_PROMPT = """You are a study coach that writes quiz questions from a \
student's notes. Write clear, specific questions that test understanding, \
not just memorized wording. Mix multiple-choice and short-answer questions. \
Always respond with valid JSON only, matching the exact schema you're given. \
No markdown, no commentary outside the JSON."""

USER_PROMPT_TEMPLATE = """Notes:
---
{notes}
---

Write {num_questions} quiz questions based on these notes.

Respond with JSON in exactly this shape:
{{
  "questions": [
    {{
      "id": 1,
      "type": "multiple_choice",
      "question": "...",
      "options": ["A ...", "B ...", "C ...", "D ..."],
      "correct_answer": "the exact text of the correct option",
      "key_points": [],
      "topic": "short topic label",
      "difficulty": "easy" | "medium" | "hard"
    }},
    {{
      "id": 2,
      "type": "short_answer",
      "question": "...",
      "options": null,
      "correct_answer": "a model answer, 1-2 sentences",
      "key_points": ["point graders should look for", "..."],
      "topic": "short topic label",
      "difficulty": "easy" | "medium" | "hard"
    }}
  ]
}}

Roughly half multiple_choice, half short_answer. Number ids sequentially \
starting at 1."""


def generate_quiz(notes: str, num_questions: int = 6) -> Quiz:
    user_prompt = USER_PROMPT_TEMPLATE.format(notes=notes, num_questions=num_questions)
    data = call_llm_json(SYSTEM_PROMPT, user_prompt)
    return Quiz.model_validate(data)
