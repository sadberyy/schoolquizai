from enum import Enum
from io import BytesIO
from typing import Literal
import re

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.deps import (
    CurrentUser,
    get_current_user,
    get_optional_current_user,
    require_quiz_owner,
)
from app.core.http_utils import content_disposition_attachment
from app.core.logger import logger
from app.db.database import get_db_session
from app.db.models import Quiz, Question, Result
from app.schemas.quiz import DifficultyLevel
from app.schemas.material import SourceFragment
from app.services.material_service import material_service
from app.services.gigachat_service import gigachat_service
from app.services.quiz_service import AI_RESPONSE_PARSE_ERROR, quiz_service
from app.services.presentation_export_service import export_quiz
from app.services.docx_export_service import export_quiz_docx
from app.services.results_export_service import export_results_pdf
from app.services.quiz_validation_service import quiz_validation_service
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

def enforce_points_rule(
    question_type: str,
    correct_answers: list | None,
    points: int | None,
) -> int:
    """
    Гарантирует правило из требований:
    - Для multiple_choice ни у одного correct-ответа не должно быть 0 баллов.
      В текущей логике фронта это достигается, если total points вопроса >= count(correct_answers),
      тогда каждый correct-option получит минимум 1.
    - Для single_choice достаточно, чтобы correct-ответ имел положительный балл (points >= 1).
    Если correct_answers пустой — правило про correct-ответы не применяется.
    """
    correct_count = len(correct_answers or [])
    if correct_count <= 0:
        return max(0, int(points or 0))

    # Для single_choice correct_count = 1, для multiple_choice correct_count = 2.
    min_total_points = max(1, correct_count)
    return max(min_total_points, max(0, int(points or 0)))


def _normalize_source_text(value: str | None) -> str:
    text = (value or "").strip()
    if text.lower() in PLACEHOLDER_TEXTS:
        return ""
    return text


def _quiz_public_meta(quiz: Quiz) -> dict:
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
        "questions": [],
    }


def _quiz_full_payload(quiz: Quiz, questions: list[Question]) -> dict:
    def format_source_for_display(value: str | None) -> str:
        if not value:
            return ""

        # Если это уже человекочитаемая подпись (например, пользователь отредактировал),
        # не трогаем. Форматируем только "технические" id.
        manual_match = re.fullmatch(r"manual_\d+", value)
        if manual_match:
            return "ручной ввод контекста"

        pdf_match = re.fullmatch(r"pdf_page_(\d+)_chunk_(\d+)", value)
        if pdf_match:
            page = int(pdf_match.group(1))
            return f"PDF файл, стр. {page}"

        pptx_match = re.fullmatch(r"pptx_slide_(\d+)", value)
        if pptx_match:
            slide = int(pptx_match.group(1))
            return f"PowerPoint файл, слайд {slide}"

        if re.fullmatch(r"docx_\d+", value):
            return "Word файл"

        if re.fullmatch(r"txt_\d+", value):
            return "TXT файл"

        return value

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
                "source_fragment": format_source_for_display(q.source_fragment),
                "points": enforce_points_rule(
                    q.question_type,
                    q.correct_answers,
                    q.points,
                ),
                "order_idx": q.order_idx,
            }
            for q in questions
        ],
    }


# список всех викторин для дашборда
@router.get("/list")
def list_quizzes(current_user: CurrentUser = Depends(get_current_user)):
    with get_db_session() as session:
        quizzes = (
            session.query(Quiz)
            .filter(Quiz.teacher_id == current_user.id)
            .order_by(Quiz.id.desc())
            .all()
        )
        
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
    max_attempts: int = Form(1),
    question_time_seconds: int = Form(0),
    full_time_seconds: int = Form(0),
    auto_fix: bool = Form(True),
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
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
    try:
        result = quiz_service.generate_quiz_from_fragments(
            subject=subject,
            grade=grade,
            topic=topic,
            question_count=question_count,
            question_types=parsed_question_types,
            difficulty=difficulty,
            fragments=merged_fragments,
        )

        result, validation_before, validation_after = quiz_validation_service.validate_and_fix(
            quiz=result,
            fragments=merged_fragments,
            subject=subject,
            grade=grade,
            topic=topic,
            difficulty=difficulty.value,
            auto_fix=auto_fix,
        )
    except ValueError as e:
        if str(e) == AI_RESPONSE_PARSE_ERROR:
            raise HTTPException(status_code=502, detail=AI_RESPONSE_PARSE_ERROR)
        raise
    was_fixed = validation_after is not None

    logger.info(
        f"VALIDATION_FINAL | was_fixed={was_fixed} | "
        f"score_before={validation_before.overall_score} | "
        f"score_after={validation_after.overall_score if validation_after else 'N/A'}"
    )

    fragments_by_id = {f.fragment_id: f for f in merged_fragments}

    def build_source_label(source_fragment_id: str | None) -> str:
        """
        Возвращает человекочитаемую подпись источника для UI.
        Если id не распознан/не найден — возвращает пустую строку.
        """
        if not source_fragment_id:
            return ""

        if re.fullmatch(r"manual_\d+", source_fragment_id):
            return "ручной ввод контекста"

        fragment = fragments_by_id.get(source_fragment_id)
        filename = fragment.source_name if fragment else ""

        pdf_match = re.fullmatch(r"pdf_page_(\d+)_chunk_(\d+)", source_fragment_id)
        if pdf_match:
            page = int(pdf_match.group(1))
            return f'PDF файл "{filename}", стр. {page}' if filename else ""

        pptx_match = re.fullmatch(r"pptx_slide_(\d+)", source_fragment_id)
        if pptx_match:
            slide = int(pptx_match.group(1))
            return f'PowerPoint файл "{filename}", слайд {slide}' if filename else ""

        if re.fullmatch(r"docx_\d+", source_fragment_id):
            return f'Word файл "{filename}"' if filename else ""

        if re.fullmatch(r"txt_\d+", source_fragment_id):
            return f'TXT файл "{filename}"' if filename else ""

        return ""

    # --- Сохранение в БД ---
    with get_db_session() as session:
        quiz = Quiz(
            title=result.quiz_title,
            subject=subject,
            grade=grade,
            difficulty=difficulty.value,
            max_attempts=max(1, int(max_attempts)),
            question_time_seconds=max(0, int(question_time_seconds)),
            full_time_seconds=max(0, int(full_time_seconds)),
            status="draft",
            teacher_id=current_user.id,
        )
        session.add(quiz)
        session.flush()  # получаем quiz.id внутри сессии

        # сохраняем id
        saved_quiz_id = quiz.id

        for idx, q in enumerate(result.questions):
            # Deterministic post-validation перед сохранением:
            # если по какой-то причине правильных ответов > 0, total points вопроса
            # гарантированно поднимаем до значения, при котором все correct-option получают > 0.
            normalized_points = enforce_points_rule(
                q.type,
                q.correct_answers,
                1,
            )
            if q.correct_answers and q.type == "multiple_choice":
                # strong condition: total points >= number of correct answers
                if normalized_points < len(q.correct_answers):
                    raise HTTPException(
                        status_code=500,
                        detail="Некорректные баллы: у correct-ответов не гарантируется > 0.",
                    )
            question = Question(
                quiz_id=saved_quiz_id,
                question_text=q.text,
                question_type=q.type,
                answers=q.options,
                correct_answers=q.correct_answers,
                explanation=q.explanation,
                source_fragment=build_source_label(q.source_fragment_id),
                points=normalized_points,
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
        "validation": {
            "was_fixed": was_fixed,
            "before_fix": validation_before.model_dump(),
            "after_fix": validation_after.model_dump() if validation_after else None,
        },
    }


# экспорт викторины в презентацию / PDF
@router.get("/{quiz_id}/export")
def export_quiz_route(
    quiz_id: str,
    format: Literal["pptx", "pdf", "docx"] = "pptx",
    mode: Literal["teacher", "student"] = "teacher",
    current_user: CurrentUser = Depends(get_current_user),
):
    require_quiz_owner(quiz_id, current_user.id)
    if format == "docx":
        file_bytes, filename, media_type = export_quiz_docx(quiz_id, mode)
    else:
        file_bytes, filename, media_type = export_quiz(quiz_id, format, mode)
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers=content_disposition_attachment(filename),
    )


# получение викторины по ID (для редактирования / публичных настроек для ученика)
@router.get("/{quiz_id}")
def get_quiz(
    quiz_id: str,
    current_user: CurrentUser | None = Depends(get_optional_current_user),
):
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")

        if current_user is None:
            return _quiz_public_meta(quiz)

        if quiz.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой викторине")

        questions = (
            session.query(Question)
            .filter(Question.quiz_id == quiz_id)
            .order_by(Question.order_idx)
            .all()
        )

        return _quiz_full_payload(quiz, questions)


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
def update_quiz(
    quiz_id: str,
    data: UpdateQuizRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_quiz_owner(quiz_id, current_user.id)
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
def update_question(
    quiz_id: str,
    question_id: str,
    data: UpdateQuestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_quiz_owner(quiz_id, current_user.id)
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

        # Дет-валидация и авто-fix: не сохраняем вопрос, где у correct-answer будет 0 баллов.
        question.points = enforce_points_rule(
            question.question_type,
            question.correct_answers,
            question.points,
        )

        session.commit()

    return {"ok": True, "question_id": question_id}


@router.post("/{quiz_id}/questions")
def add_question(
    quiz_id: str,
    data: CreateQuestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_quiz_owner(quiz_id, current_user.id)
    with get_db_session() as session:
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
            points=enforce_points_rule(
                data.question_type,
                data.correct_answers,
                data.points,
            ),
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
def delete_question(
    quiz_id: str,
    question_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Удаляет один вопрос из викторины (со страницы редактирования)"""
    require_quiz_owner(quiz_id, current_user.id)
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
def delete_quiz(quiz_id: str, current_user: CurrentUser = Depends(get_current_user)):
    """Удаляет викторину и все связанные вопросы, результаты"""
    require_quiz_owner(quiz_id, current_user.id)
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


class FinishQuizRequest(BaseModel):
    duration_seconds: int | None = None


@router.post("/attempt/{attempt_id}/finish")
def finish_quiz_route(attempt_id: str, data: FinishQuizRequest | None = None):
    try:
        duration = data.duration_seconds if data else None
        result = finish_quiz(attempt_id, duration_seconds=duration)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# результаты для учителя
@router.get("/{quiz_id}/results")
def get_results_route(quiz_id: str, current_user: CurrentUser = Depends(get_current_user)):
    require_quiz_owner(quiz_id, current_user.id)
    return {"results": get_quiz_results(quiz_id)}


@router.get("/{quiz_id}/results/export")
def export_results_route(
    quiz_id: str,
    sort_by: Literal["name", "score", "time", "attempt"] = "score",
    sort_dir: Literal["asc", "desc"] = "desc",
    current_user: CurrentUser = Depends(get_current_user),
):
    require_quiz_owner(quiz_id, current_user.id)
    file_bytes, filename, media_type = export_results_pdf(
        quiz_id, sort_by=sort_by, sort_dir=sort_dir
    )
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers=content_disposition_attachment(filename),
    )