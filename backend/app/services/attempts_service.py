from datetime import datetime

from app.db.database import get_db_session
from app.db.models import Quiz, QuizAttempt, StudentAnswer, Question


def _is_answer_correct(student_answer, correct_answers) -> bool:
    """Сравнивает ответ ученика с correct_answers (строка или JSON-список)."""
    if correct_answers is None:
        return False

    correct_list = (
        correct_answers if isinstance(correct_answers, list) else [correct_answers]
    )
    student_list = (
        student_answer if isinstance(student_answer, list) else [student_answer]
    )

    return sorted(str(item) for item in student_list) == sorted(
        str(item) for item in correct_list
    )


def start_quiz_attempt(
    access_token: str,
    student_name: str,
    student_surname: str | None = None,
):
    with get_db_session() as session:
        quiz = (
            session.query(Quiz)
            .filter(Quiz.access_token == access_token)
            .filter(Quiz.status == "published")
            .first()
        )

        if quiz is None:
            raise ValueError("Викторина не найдена или не опубликована")

        max_score = sum(question.points for question in quiz.questions)

        attempt = QuizAttempt(
            quiz_id=quiz.id,
            student_name=student_name,
            student_surname=student_surname,
            max_score=max_score,
            started_at=datetime.utcnow(),
        )

        session.add(attempt)
        session.flush()
        session.refresh(attempt)

        return attempt.id


def save_student_answer(
    attempt_id: str,
    question_id: str,
    answer,
):
    with get_db_session() as session:
        question = session.query(Question).filter(Question.id == question_id).first()

        if question is None:
            raise ValueError("Вопрос не найден")

        is_correct = _is_answer_correct(answer, question.correct_answers)
        points_received = question.points if is_correct else 0

        student_answer = StudentAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            answer=answer,
            is_correct=is_correct,
            points_received=points_received,
        )

        session.add(student_answer)

        attempt = session.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()

        if attempt is None:
            raise ValueError("Попытка не найдена")

        attempt.score = (attempt.score or 0) + points_received

        session.flush()
        session.refresh(student_answer)

        return student_answer.id


def finish_quiz_attempt(attempt_id: str):
    with get_db_session() as session:
        attempt = session.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()

        if attempt is None:
            raise ValueError("Попытка не найдена")

        now = datetime.utcnow()
        attempt.finished_at = now

        if attempt.started_at:
            attempt.duration_seconds = int((now - attempt.started_at).total_seconds())

        return {
            "attempt_id": attempt.id,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "duration_seconds": attempt.duration_seconds,
        }