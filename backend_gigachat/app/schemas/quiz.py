from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


QuestionType = Literal["single_choice", "multiple_choice", "true_false"]


class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class GenerateQuizRequest(BaseModel):
    subject: str = Field(..., min_length=2, max_length=100)
    grade: str = Field(..., min_length=1, max_length=20)
    topic: str = Field(..., min_length=2, max_length=200)
    question_count: int = Field(default=5, ge=1, le=15)
    question_types: List[QuestionType] = Field(
        default=["single_choice", "multiple_choice", "true_false"],
        min_length=1,
        max_length=3
    )
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.easy)
    source_text: Optional[str] = Field(default=None, max_length=4000)


class QuizQuestion(BaseModel):
    type: QuestionType
    text: str
    options: List[str]
    correct_answers: List[str]
    explanation: str
    difficulty: DifficultyLevel
    source_fragment_id: Optional[str] = None


class GenerateQuizResponse(BaseModel):
    quiz_title: str
    subject: str
    grade: str
    topic: str
    questions: List[QuizQuestion]