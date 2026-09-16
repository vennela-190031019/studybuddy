"""
Data models for StudyBuddy.

Using Pydantic here means every LLM response gets validated into a known
shape instead of trusting raw text. This is the "structured output" pattern
that's worth understanding well — it's one of the most practical LLM
engineering skills, and it's what makes the grading logic downstream
reliable instead of fragile string-matching.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    id: int
    type: Literal["multiple_choice", "short_answer"]
    question: str
    # Only populated for multiple_choice questions
    options: Optional[list[str]] = None
    correct_answer: str
    # Used by the grader as a rubric for short-answer questions
    key_points: list[str] = Field(default_factory=list)
    topic: str = ""
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class Quiz(BaseModel):
    questions: list[QuizQuestion]


class GradeResult(BaseModel):
    question_id: int
    correct: bool
    score: int  # 0-100
    feedback: str
