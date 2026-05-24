import re
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Pt

from app.db.database import get_db_session
from app.db.models import Question, Quiz

ExportFormat = Literal["pptx", "pdf"]
ExportMode = Literal["teacher", "student"]

_BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
_FONT_CANDIDATES = [
    _BUNDLED_FONT,
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]
_DIFFICULTY_LABELS = {"easy": "Лёгкая", "medium": "Средняя", "hard": "Сложная"}
_TYPE_LABELS = {
    "single_choice": "Один вариант",
    "multiple_choice": "Несколько вариантов",
    "true_false": "Верно / Неверно",
}


def _format_option(option) -> str:
    if isinstance(option, str):
        return option
    if isinstance(option, dict):
        return str(option.get("text") or option.get("label") or option.get("id", ""))
    return str(option)


def _format_answers(correct_answers) -> str:
    if correct_answers is None:
        return ""
    if isinstance(correct_answers, list):
        return "\n".join(str(item) for item in correct_answers)
    return str(correct_answers)


def _is_valid_ttf(path: Path) -> bool:
    try:
        signature = path.read_bytes()[:4]
    except OSError:
        return False
    return signature in {b"\x00\x01\x00\x00", b"OTTO", b"ttcf"}


def _resolve_pdf_font_path() -> Path:
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file() and _is_valid_ttf(candidate):
            return candidate
    raise HTTPException(
        status_code=500,
        detail=(
            "Не найден шрифт для PDF. Положите DejaVuSans.ttf в app/assets/fonts "
            "или установите системный шрифт (Arial / DejaVu)."
        ),
    )


def _safe_filename(title: str, extension: str) -> str:
    base = re.sub(r'[<>:"/\\|?*]', "", title).strip() or "quiz"
    base = base[:80]
    return f"{base}.{extension}"


def load_quiz_with_questions(quiz_id: str) -> tuple[Quiz, list[Question]]:
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

        if not questions:
            raise HTTPException(status_code=400, detail="Викторина не содержит вопросов")

        session.expunge(quiz)
        for question in questions:
            session.expunge(question)

        return quiz, questions


def export_quiz(
    quiz_id: str,
    export_format: ExportFormat = "pptx",
    mode: ExportMode = "teacher",
) -> tuple[bytes, str, str]:
    quiz, questions = load_quiz_with_questions(quiz_id)

    if export_format == "pptx":
        return _build_pptx(quiz, questions, mode)
    if export_format == "pdf":
        return _build_pdf(quiz, questions, mode)

    raise HTTPException(status_code=400, detail="Формат должен быть pptx или pdf")


def _quiz_subtitle(quiz: Quiz) -> str:
    parts = []
    if quiz.subject:
        parts.append(f"Предмет: {quiz.subject}")
    if quiz.grade:
        parts.append(f"Класс: {quiz.grade}")
    if quiz.difficulty:
        label = _DIFFICULTY_LABELS.get(quiz.difficulty, quiz.difficulty)
        parts.append(f"Сложность: {label}")
    return " · ".join(parts)


def _build_pptx(
    quiz: Quiz,
    questions: list[Question],
    mode: ExportMode,
) -> tuple[bytes, str, str]:
    prs = Presentation()

    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = quiz.title
    subtitle = _quiz_subtitle(quiz)
    if subtitle and len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = subtitle

    for index, question in enumerate(questions, start=1):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = f"Вопрос {index}"

        body = slide.shapes.placeholders[1].text_frame
        body.text = question.question_text

        type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
        type_paragraph = body.add_paragraph()
        type_paragraph.text = f"Тип: {type_label}"
        type_paragraph.level = 0
        type_paragraph.font.size = Pt(14)

        for option in question.answers or []:
            option_paragraph = body.add_paragraph()
            option_paragraph.text = f"• {_format_option(option)}"
            option_paragraph.level = 1

        if mode == "teacher":
            answer_paragraph = body.add_paragraph()
            answer_paragraph.text = f"Правильный ответ: {_format_answers(question.correct_answers)}"
            answer_paragraph.level = 0

            if question.explanation:
                explanation_paragraph = body.add_paragraph()
                explanation_paragraph.text = f"Пояснение: {question.explanation}"
                explanation_paragraph.level = 0

    buffer = BytesIO()
    prs.save(buffer)
    filename = _safe_filename(quiz.title, "pptx")
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return buffer.getvalue(), filename, media_type


def _build_pdf(
    quiz: Quiz,
    questions: list[Question],
    mode: ExportMode,
) -> tuple[bytes, str, str]:
    font_path = _resolve_pdf_font_path()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_font("DejaVu", "", str(font_path))
    pdf.add_font("DejaVu", "B", str(font_path))
    pdf.set_font("DejaVu", size=12)
    line_width = pdf.epw

    # Титульник
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(line_width, 10, quiz.title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    subtitle = _quiz_subtitle(quiz)
    if subtitle:
        pdf.set_font("DejaVu", size=12)
        pdf.cell(line_width, 8, subtitle, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

    # Вопросы
    for index, question in enumerate(questions, start=1):
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 14)
        pdf.cell(line_width, 8, f"Вопрос {index}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Текст вопроса
        pdf.set_font("DejaVu", size=12)
        pdf.multi_cell(line_width, 7, question.question_text)
        pdf.ln(2)

        # Тип вопроса
        type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
        pdf.set_font("DejaVu", size=11)
        pdf.cell(line_width, 6, f"Тип: {type_label}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Варианты ответов
        pdf.set_font("DejaVu", size=12)
        for option in question.answers or []:
            option_text = f"- {_format_option(option)}"
            pdf.cell(line_width, 7, option_text, new_x="LMARGIN", new_y="NEXT")

        # Правильные ответы и пояснение (только для учителя)
        if mode == "teacher":
            pdf.ln(4)
            pdf.set_font("DejaVu", "B", size=11)
            pdf.cell(line_width, 7, "Правильный ответ:", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("DejaVu", size=11)
            if isinstance(question.correct_answers, list):
                for answer in question.correct_answers:
                    pdf.cell(line_width, 7, str(answer), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.cell(line_width, 7, str(question.correct_answers or ""), new_x="LMARGIN", new_y="NEXT")
            
            if question.explanation:
                pdf.ln(4)
                pdf.set_font("DejaVu", "B", size=11)
                pdf.cell(line_width, 7, "Пояснение:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("DejaVu", size=11)
                pdf.multi_cell(line_width, 7, question.explanation)

    filename = _safe_filename(quiz.title, "pdf")
    media_type = "application/pdf"
    return pdf.output(), filename, media_type