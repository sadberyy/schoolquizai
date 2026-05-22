from datetime import datetime, timezone

from app.db.database import get_db_session
from app.db.models import Quiz, Question, Result


def _utcnow():
    return datetime.now(timezone.utc)


def _check_answer(student_answer, correct_answers) -> bool:
    """
    Сравнивает ответ ученика с правильными ответами.
    
    Поддерживает:
    - одиночный выбор: student_answer = "a", correct_answers = ["a"]
    - множественный выбор: student_answer = ["a", "c"], correct_answers = ["a", "c"]
    - true_false: student_answer = "Верно", correct_answers = ["Верно"]
    """
    if correct_answers is None:
        return False

    # Приводим к списку для единообразного сравнения
    correct_list = (
        correct_answers if isinstance(correct_answers, list) else [correct_answers]
    )
    student_list = (
        student_answer if isinstance(student_answer, list) else [student_answer]
    )

    return sorted(str(item) for item in student_list) == sorted(
        str(item) for item in correct_list
    )


def start_quiz(quiz_id: str, student_name: str) -> str:
    """
    Начинает новую попытку прохождения викторины.
    
    Возвращает ID созданной записи в таблице results (attempt_id).
    """
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()

        if quiz is None:
            raise ValueError("Викторина не найдена")

        # Считаем максимальный балл за викторину
        max_score = sum(q.points for q in quiz.questions)

        # Определяем номер попытки
        existing_attempts = (
            session.query(Result)
            .filter(Result.quiz_id == quiz_id, Result.student_name == student_name)
            .count()
        )
        attempt_number = existing_attempts + 1

        # Проверяем, не превышен ли лимит попыток
        if quiz.max_attempts and attempt_number > quiz.max_attempts:
            raise ValueError(f"Превышено количество попыток (максимум {quiz.max_attempts})")

        result = Result(
            quiz_id=quiz_id,
            student_name=student_name,
            score=0,
            max_score=max_score,
            attempt_number=attempt_number,
        )

        session.add(result)
        session.commit()
        session.refresh(result)

        return result.id


def get_quiz_questions(quiz_id: str) -> list[dict]:
    """
    Возвращает список вопросов викторины (без правильных ответов!) для показа ученику.
    """
    with get_db_session() as session:
        questions = (
            session.query(Question)
            .filter(Question.quiz_id == quiz_id)
            .order_by(Question.order_idx)
            .all()
        )

        return [
            {
                "id": q.id,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "answers": q.answers,
                "points": q.points,
                "order_idx": q.order_idx,
            }
            for q in questions
        ]


def submit_answer(attempt_id: str, question_id: str, answer) -> dict:
    """
    Проверяет ответ ученика на один вопрос и обновляет счёт.
    
    Возвращает:
    - is_correct: правильно ли ответил
    - points_received: сколько баллов получено
    """
    with get_db_session() as session:
        question = session.query(Question).filter(Question.id == question_id).first()
        if question is None:
            raise ValueError("Вопрос не найден")

        result = session.query(Result).filter(Result.id == attempt_id).first()
        if result is None:
            raise ValueError("Попытка не найдена")

        is_correct = _check_answer(answer, question.correct_answers)
        points_received = question.points if is_correct else 0

        # Обновляем общий счёт
        result.score = (result.score or 0) + points_received

        session.commit()

        return {
            "is_correct": is_correct,
            "points_received": points_received,
            "total_score": result.score,
            "explanation": question.explanation if is_correct else None,
        }


def finish_quiz(attempt_id: str) -> dict:
    """
    Завершает попытку и возвращает финальный результат.
    """
    with get_db_session() as session:
        result = session.query(Result).filter(Result.id == attempt_id).first()
        if result is None:
            raise ValueError("Попытка не найдена")

        result.duration_seconds = 0  # TODO: передавать реальное время с фронтенда

        session.commit()

        return {
            "attempt_id": result.id,
            "student_name": result.student_name,
            "score": result.score,
            "max_score": result.max_score,
            "attempt_number": result.attempt_number,
        }


def get_quiz_results(quiz_id: str) -> list[dict]:
    """
    Возвращает все результаты по викторине (для учителя).
    """
    with get_db_session() as session:
        results = (
            session.query(Result)
            .filter(Result.quiz_id == quiz_id)
            .order_by(Result.student_name, Result.attempt_number)
            .all()
        )

        return [
            {
                "student_name": r.student_name,
                "score": r.score,
                "max_score": r.max_score,
                "attempt_number": r.attempt_number,
                "duration_seconds": r.duration_seconds,
            }
            for r in results
        ]