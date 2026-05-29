"""Экспорт викторины в DOCX."""
from io import BytesIO
from typing import Literal

from docx import Document
from docx.shared import Pt

from app.db.models import Question, Quiz
from app.services.latex_renderer import render_latex_to_png, latex_render_batch
from app.services.presentation_export_service import (
    _question_body_paragraphs,
    _safe_filename,
    _split_text_and_formulas,
    load_quiz_with_questions,
)

ExportMode = Literal["teacher", "student"]

_DIFFICULTY_LABELS = {"easy": "Лёгкая", "medium": "Средняя", "hard": "Сложная"}


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


def _fill_paragraph_with_content(paragraph, text: str) -> None:
    parts = _split_text_and_formulas(text or "")
    if not parts:
        return

    for kind, content, display in parts:
        if kind == "text":
            if content:
                paragraph.add_run(content)
            continue

        png = render_latex_to_png(content)
        if png:
            run = paragraph.add_run()
            try:
                run.add_picture(BytesIO(png), height=Pt(18 if display else 14))
            except Exception:
                paragraph.add_run(content)
        else:
            paragraph.add_run(content)


def build_quiz_docx(
    quiz: Quiz,
    questions: list[Question],
    mode: ExportMode,
) -> tuple[bytes, str, str]:
    doc = Document()
    doc.add_heading(quiz.title or "Викторина", 0)

    subtitle = _quiz_subtitle(quiz)
    if subtitle:
        doc.add_paragraph(subtitle)

    for index, question in enumerate(questions, start=1):
        doc.add_heading(f"Вопрос {index}", level=1)
        for text, level in _question_body_paragraphs(question, mode):
            paragraph = doc.add_paragraph(style="List Bullet" if level > 0 else None)
            _fill_paragraph_with_content(paragraph, text)

    buffer = BytesIO()
    doc.save(buffer)
    filename = _safe_filename(quiz.title, "docx")
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return buffer.getvalue(), filename, media_type


def export_quiz_docx(
    quiz_id: str,
    mode: ExportMode = "teacher",
) -> tuple[bytes, str, str]:
    quiz, questions = load_quiz_with_questions(quiz_id)
    with latex_render_batch():
        return build_quiz_docx(quiz, questions, mode)
