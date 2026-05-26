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



# ============================================================
# Схемы валидации викторины (LLM-as-a-judge)
# ============================================================

IssueSeverity = Literal["critical", "warning", "info"]
IssueCategory = Literal[
    "factual_error",          # фактическая ошибка по существу
    "not_in_source",          # ответа/факта нет в исходных фрагментах
    "wrong_correct_answer",   # неправильно помечен правильный ответ
    "ambiguous",              # двусмысленная или непонятная формулировка
    "duplicate_options",      # повторяющиеся варианты ответа
    "options_count_mismatch", # неверное количество вариантов для типа
    "difficulty_mismatch",    # сложность не соответствует заявленной
    "off_topic",              # вопрос не по теме
    "format_error",           # структурная ошибка (correct_answers не из options и т.п.)
]


class QuestionIssue(BaseModel):
    """Одна проблема, найденная в одном вопросе."""
    question_index: int = Field(..., ge=0, description="Индекс вопроса (с 0)")
    severity: IssueSeverity
    category: IssueCategory
    description: str = Field(..., description="Что именно не так")
    suggested_fix: Optional[str] = Field(default=None, description="Как починить")


class QuizValidationReport(BaseModel):
    """Отчёт о проверке викторины."""
    is_valid: bool = Field(..., description="True, если нет critical-проблем")
    overall_score: float = Field(..., ge=0, le=10, description="Общая оценка качества от 0 до 10")
    issues: List[QuestionIssue] = Field(default_factory=list)
    summary: str = Field(..., description="Краткое резюме проверки на русском")

    @property
    def has_critical_issues(self) -> bool:
        return any(issue.severity == "critical" for issue in self.issues)

    @property
    def critical_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "critical")


# ============================================================
# Схема для ответа API с историей валидации
# ============================================================

class QuizWithValidation(BaseModel):
    """
    Результат генерации с историей валидаций.

    validation_before_fix — отчёт сразу после генерации (всегда есть).
    validation_after_fix — отчёт после авто-фикса (None, если фикс не делался).
    """
    quiz: GenerateQuizResponse
    validation_before_fix: QuizValidationReport
    validation_after_fix: Optional[QuizValidationReport] = None
    was_fixed: bool = Field(default=False, description="True, если авто-фикс применялся")