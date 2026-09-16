"""
Grades a student's answer to a quiz question.

Multiple-choice is graded instantly by string comparison — no need to call
an LLM for that. Short-answer questions go to the LLM with the question's
key_points as a rubric, and come back as a structured score + feedback.
This split matters: it's cheaper, faster, and it shows you know *when*
an LLM call is actually needed versus when plain code is enough.
"""
from src.llm_client import call_llm_json
from src.schemas import GradeResult, QuizQuestion

SYSTEM_PROMPT = """You are a fair, encouraging grader. Score the student's \
answer against the key points provided. Give credit for correct ideas even \
if the wording differs from the model answer. Be specific in feedback: say \
what was right, what was missing, and one concrete way to improve. Always \
respond with valid JSON only, no markdown."""

USER_PROMPT_TEMPLATE = """Question: {question}
Model answer / key points the answer should cover: {key_points}
Student's answer: {answer}

Respond with JSON in exactly this shape:
{{
  "correct": true | false,
  "score": 0-100,
  "feedback": "2-3 sentences, specific and constructive"
}}

Score 70+ counts as "correct": true. An empty or "I don't know" answer \
should score 0 with encouraging feedback pointing at the key points."""


def grade_answer(question: QuizQuestion, user_answer: str) -> GradeResult:
    if question.type == "multiple_choice":
        correct = _normalize(user_answer) == _normalize(question.correct_answer)
        return GradeResult(
            question_id=question.id,
            correct=correct,
            score=100 if correct else 0,
            feedback=(
                "Correct!" if correct
                else f"Not quite — the correct answer was: {question.correct_answer}"
            ),
        )

    # short_answer: ask the LLM to grade against the rubric
    user_prompt = USER_PROMPT_TEMPLATE.format(
        question=question.question,
        key_points="; ".join(question.key_points) or question.correct_answer,
        answer=user_answer or "(no answer given)",
    )
    data = call_llm_json(SYSTEM_PROMPT, user_prompt)
    return GradeResult(question_id=question.id, **data)


def _normalize(s: str) -> str:
    return s.strip().lower().rstrip(".")
