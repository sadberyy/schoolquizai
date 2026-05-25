from enum import Enum
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from urllib.parse import quote

from app.core.logger import logger
from app.db.database import get_db_session
from app.db.models import Quiz, Question, Result
from app.schemas.quiz import DifficultyLevel
from app.schemas.material import SourceFragment
from app.services.material_service import material_service
from app.services.gigachat_service import gigachat_service
from app.services.quiz_service import quiz_service
from app.services.presentation_export_service import export_quiz
from app.services.attempts_service import (
    start_quiz,
    get_quiz_questions,
    submit_answer,
    finish_quiz,
    get_quiz_results,
)


router = APIRouter(prefix="/quiz", tags=["Quiz"])


class QuestionType(str, Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"


PLACEHOLDER_TEXTS = {"string", "source_text", "null", "none"}


def _normalize_source_text(value: str | None) -> str:
    text = (value or "").strip()
    if text.lower() in PLACEHOLDER_TEXTS:
        return ""
    return text

# список всех викторин для дашборда
@router.get("/list")
def list_quizzes():
    with get_db_session() as session:
        quizzes = session.query(Quiz).order_by(Quiz.id.desc()).all()
        
        return {
            "quizzes": [
                {
                    "id": q.id,
                    "title": q.title,
                    "subject": q.subject,
                    "grade": q.grade,
                    "difficulty": q.difficulty,
                    "status": q.status,
                    "questions_count": len(q.questions),
                    "created_at": str(q.id),  # временно, пока нет поля created_at
                }
                for q in quizzes
            ]
        }

# Генерация викторины (с сохранением в БД)
@router.post("/generate-from-materials")
async def generate_quiz_from_materials(
    subject: str = Form(...),
    grade: str = Form(...),
    topic: str = Form(...),
    question_count: int = Form(...),
    question_types: list[QuestionType] = Form(...),
    difficulty: DifficultyLevel = Form(...),
    source_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
):
    logger.info(
        f"START /quiz/generate-from-materials | subject={subject} | grade={grade} | "
        f"topic={topic} | question_count={question_count} | difficulty={difficulty}"
    )

    cleaned_source_text = _normalize_source_text(source_text)

    if not cleaned_source_text and file is None and image is None:
        raise HTTPException(
            status_code=400,
            detail="Укажите хотя бы один источник: текст, файл или изображение."
        )

    parsed_question_types = [item.value for item in question_types]
    all_fragments: list[SourceFragment] = []

    # обработка текста
    if cleaned_source_text:
        all_fragments.append(
            SourceFragment(
                fragment_id="manual_1",
                source_type="manual_text",
                source_name="teacher_input",
                text=cleaned_source_text
            )
        )

    # обработка файла
    if file is not None:
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Загруженный файл пуст.")

        try:
            file_type, file_fragments = material_service.extract_fragments(file.filename, file_content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if file_type in {"pdf", "pptx", "docx", "doc"} and material_service.has_too_little_text(file_fragments):
            extracted_text = gigachat_service.extract_text_from_file(file.filename, file_content)
            if extracted_text and extracted_text.strip():
                file_fragments = [
                    SourceFragment(
                        fragment_id=f"{file_type}_fallback_1",
                        source_type=file_type,
                        source_name=file.filename,
                        text=extracted_text.strip()
                    )
                ]

        all_fragments.extend(file_fragments)

    # обработка изображения
    if image is not None:
        image_content = await image.read()
        if not image_content:
            raise HTTPException(status_code=400, detail="Загруженное изображение пусто.")

        image_text = gigachat_service.extract_text_from_image(image.filename, image_content)
        if image_text and image_text.strip():
            all_fragments.append(
                SourceFragment(
                    fragment_id="image_1",
                    source_type="image",
                    source_name=image.filename,
                    text=image_text.strip()
                )
            )

    # объединение фрагментов
    merged_fragments = material_service.merge_fragments(None, all_fragments)
    if not merged_fragments:
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из источников.")

    # генерация через GigaChat
    result = quiz_service.generate_quiz_from_fragments(
        subject=subject,
        grade=grade,
        topic=topic,
        question_count=question_count,
        question_types=parsed_question_types,
        difficulty=difficulty,
        fragments=merged_fragments
    )

    # сохранение в БД
    with get_db_session() as session:
        quiz = Quiz(
            title=result.quiz_title,
            subject=subject,
            grade=grade,
            difficulty=difficulty.value,
            status="draft",
        )
        session.add(quiz)
        session.flush()  # получаем quiz.id внутри сессии

        # сохраняем id
        saved_quiz_id = quiz.id

        for idx, q in enumerate(result.questions):
            question = Question(
                quiz_id=saved_quiz_id,
                question_text=q.text,
                question_type=q.type,
                answers=q.options,
                correct_answers=q.correct_answers,
                explanation=q.explanation,
                source_fragment=q.source_fragment_id or "",
                points=1,
                order_idx=idx,
            )
            session.add(question)

        session.commit()

        logger.info(f"SAVED TO DB | quiz_id={saved_quiz_id} | questions_count={len(result.questions)}")

    # возвращаем ответ, используя сохранённый id
    return {
        "quiz_id": saved_quiz_id,
        "title": result.quiz_title,
        "subject": result.subject,
        "grade": result.grade,
        "topic": result.topic,
        "questions": [
            {
                "type": q.type,
                "text": q.text,
                "options": q.options,
                "correct_answers": q.correct_answers,
                "explanation": q.explanation,
                "source_fragment_id": q.source_fragment_id,
            }
            for q in result.questions
        ],
    }


# экспорт викторины в презентацию / PDF
@router.get("/{quiz_id}/export")
def export_quiz_route(
    quiz_id: str,
    format: Literal["pptx", "pdf"] = "pptx",
    mode: Literal["teacher", "student"] = "teacher",
):
    file_bytes, filename, media_type = export_quiz(quiz_id, format, mode)
    ascii_fallback = "quiz." + filename.rsplit(".", 1)[-1] if "." in filename else "quiz"
    disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


# получение викторины по ID (для редактирования)
@router.get("/{quiz_id}")
def get_quiz(quiz_id: str):
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")

        questions = (
            session.query(Question)
            .filter(Question.quiz_id == quiz_id)
            .order_by(Question.order_idx)
            .all()
        )

        return {
            "quiz_id": quiz.id,
            "title": quiz.title,
            "subject": quiz.subject,
            "grade": quiz.grade,
            "difficulty": quiz.difficulty,
            "full_time_seconds": quiz.full_time_seconds,
            "question_time_seconds": quiz.question_time_seconds,
            "max_attempts": quiz.max_attempts,
            "status": quiz.status,
            "questions": [
                {
                    "id": q.id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "answers": q.answers,
                    "correct_answers": q.correct_answers,
                    "explanation": q.explanation,
                    "source_fragment": q.source_fragment,
                    "points": q.points,
                    "order_idx": q.order_idx,
                }
                for q in questions
            ],
        }


# сохранение отредактированной викторины
class UpdateQuizRequest(BaseModel):
    title: str | None = None
    difficulty: str | None = None
    full_time_seconds: int | None = None
    question_time_seconds: int | None = None
    max_attempts: int | None = None
    status: str | None = None


class CreateQuestionRequest(BaseModel):
    question_text: str
    question_type: str
    answers: list | None = None
    correct_answers: list | None = None
    explanation: str | None = None
    source_fragment: str | None = None
    points: int = 1


class UpdateQuestionRequest(BaseModel):
    question_text: str | None = None
    question_type: str | None = None
    answers: list | None = None
    correct_answers: list | None = None
    explanation: str | None = None
    source_fragment: str | None = None
    points: int | None = None
    order_idx: int | None = None


@router.put("/{quiz_id}")
def update_quiz(quiz_id: str, data: UpdateQuizRequest):
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")

        if data.title is not None:
            quiz.title = data.title
        if data.difficulty is not None:
            quiz.difficulty = data.difficulty
        if data.full_time_seconds is not None:
            quiz.full_time_seconds = data.full_time_seconds
        if data.question_time_seconds is not None:
            quiz.question_time_seconds = data.question_time_seconds
        if data.max_attempts is not None:
            quiz.max_attempts = data.max_attempts
        if data.status is not None:
            quiz.status = data.status

        session.commit()

    return {"ok": True, "quiz_id": quiz_id}


@router.put("/{quiz_id}/questions/{question_id}")
def update_question(quiz_id: str, question_id: str, data: UpdateQuestionRequest):
    with get_db_session() as session:
        question = session.query(Question).filter(
            Question.id == question_id,
            Question.quiz_id == quiz_id
        ).first()

        if not question:
            raise HTTPException(status_code=404, detail="Вопрос не найден")

        if data.question_text is not None:
            question.question_text = data.question_text
        if data.question_type is not None:
            question.question_type = data.question_type
        if data.answers is not None:
            question.answers = data.answers
        if data.correct_answers is not None:
            question.correct_answers = data.correct_answers
        if data.explanation is not None:
            question.explanation = data.explanation
        if data.source_fragment is not None:
            question.source_fragment = data.source_fragment
        if data.points is not None:
            question.points = data.points
        if data.order_idx is not None:
            question.order_idx = data.order_idx

        session.commit()

    return {"ok": True, "question_id": question_id}


@router.post("/{quiz_id}/questions")
def add_question(quiz_id: str, data: CreateQuestionRequest):
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")
        
        # Определяем следующий порядковый номер
        max_order = session.query(Question).filter(
            Question.quiz_id == quiz_id
        ).count()
        
        question = Question(
            quiz_id=quiz_id,
            question_text=data.question_text,
            question_type=data.question_type,
            answers=data.answers or [],
            correct_answers=data.correct_answers or [],
            explanation=data.explanation or "",
            source_fragment=data.source_fragment or "",
            points=data.points,
            order_idx=max_order,
        )
        session.add(question)
        session.flush()
        saved_question_id = question.id
        saved_order_idx = question.order_idx
        session.commit()
    
    return {
        "ok": True,
        "question_id": saved_question_id,
        "order_idx": saved_order_idx
    }

@router.delete("/{quiz_id}/questions/{question_id}")
def delete_question(quiz_id: str, question_id: str):
    """Удаляет один вопрос из викторины (со страницы редактирования)"""
    with get_db_session() as session:
        question = session.query(Question).filter(
            Question.id == question_id,
            Question.quiz_id == quiz_id
        ).first()
        
        if not question:
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        session.delete(question)
        session.commit()
    
    return {"ok": True, "deleted_question_id": question_id}

@router.delete("/{quiz_id}")
def delete_quiz(quiz_id: str):
    """Удаляет викторину и все связанные вопросы, результаты"""
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")
        
        # Удаляем связанные результаты
        session.query(Result).filter(Result.quiz_id == quiz_id).delete()
        # Удаляем связанные вопросы
        session.query(Question).filter(Question.quiz_id == quiz_id).delete()
        # Удаляем саму викторину
        session.delete(quiz)
        session.commit()
    
    return {"ok": True, "deleted_quiz_id": quiz_id}
    

# роуты для ученика
class StartQuizRequest(BaseModel):
    student_name: str


@router.post("/{quiz_id}/start")
def start_quiz_route(quiz_id: str, data: StartQuizRequest):
    try:
        attempt_id = start_quiz(quiz_id=quiz_id, student_name=data.student_name)
        return {"attempt_id": attempt_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{quiz_id}/questions")
def get_questions_route(quiz_id: str):
    """Возвращает вопросы БЕЗ правильных ответов (для ученика)"""
    questions = get_quiz_questions(quiz_id)
    if not questions:
        raise HTTPException(status_code=404, detail="Викторина не найдена или не содержит вопросов")
    return {"questions": questions}


class SubmitAnswerRequest(BaseModel):
    question_id: str
    answer: str | list[str]


@router.post("/attempt/{attempt_id}/answer")
def submit_answer_route(attempt_id: str, data: SubmitAnswerRequest):
    try:
        result = submit_answer(
            attempt_id=attempt_id,
            question_id=data.question_id,
            answer=data.answer
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/attempt/{attempt_id}/finish")
def finish_quiz_route(attempt_id: str):
    try:
        result = finish_quiz(attempt_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# результаты для учителя
@router.get("/{quiz_id}/results")
def get_results_route(quiz_id: str):
    results = get_quiz_results(quiz_id)
    if not results:
        raise HTTPException(status_code=404, detail="Результаты не найдены")
    return {"results": results}