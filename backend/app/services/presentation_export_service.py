import re
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import HTTPException
from pptx import Presentation
from pptx.util import Pt
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from app.db.database import get_db_session
from app.db.models import Question, Quiz

ExportFormat = Literal["pptx", "pdf"]
ExportMode = Literal["teacher", "student"]

_DIFFICULTY_LABELS = {"easy": "Лёгкая", "medium": "Средняя", "hard": "Сложная"}
_TYPE_LABELS = {
    "single_choice": "Один вариант",
    "multiple_choice": "Несколько вариантов",
    "true_false": "Верно / Неверно",
}

# путь к шрифту с поддержкой кириллицы
_BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
_FONT_CANDIDATES = [
    _BUNDLED_FONT,
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]

_FONT_PATH = None
for candidate in _FONT_CANDIDATES:
    if candidate.is_file():
        _FONT_PATH = str(candidate)
        pdfmetrics.registerFont(TTFont('DejaVu', _FONT_PATH))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', _FONT_PATH))  # жирный тот же файл
        break

if not _FONT_PATH:
    raise RuntimeError("Не найден шрифт DejaVuSans для PDF")


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


def _safe_filename(title: str, extension: str) -> str:
    """Создаёт имя файла"""
    base = re.sub(r'[<>:"/\\|?*]', '', title).strip() or "quiz"
    base = base[:80].strip()
    return f"{base}.{extension}"


def _replace_latex_with_parts(text: str) -> list[dict]:
    """Разбирает текст на части: обычный текст и latex-формулы."""
    parts = []
    last_end = 0
    for match in re.finditer(r'\$(.+?)\$', text):
        if match.start() > last_end:
            parts.append({"type": "text", "content": text[last_end:match.start()]})
        parts.append({"type": "latex", "content": match.group(1)})
        last_end = match.end()
    if last_end < len(text):
        parts.append({"type": "text", "content": text[last_end:]})
    if not parts:
        parts = [{"type": "text", "content": text}]
    return parts


# Рендеринг LaTeX в формат PNG
def _render_latex_matplotlib(latex: str) -> bytes | None:
    """Рендерит LaTeX через matplotlib mathtext."""
    clean = latex.strip()
    
    # замена неподдерживаемых команд
    replacements = {
        '\\le': '\\leq',
        '\\ge': '\\geq',
        '\\rightarrow': '\\to',
        '\\left': '',
        '\\right': '',
    }
    for old, new in replacements.items():
        clean = clean.replace(old, new)
    
    clean = f'${clean}$'
    
    try:
        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        ax.axis('off')
        ax.text(0, 0, clean, fontsize=12, ha='left', va='bottom')
        fig.canvas.draw()
        
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        plt.close('all')
        return None


# Загрузка викторины
def load_quiz_with_questions(quiz_id: str) -> tuple[Quiz, list[Question]]:
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")
        questions = (
            session.query(Question)
            .filter(Question.quiz_id == quiz_id)
            .order_by(Question.order_idx).all()
        )
        if not questions:
            raise HTTPException(status_code=400, detail="Викторина не содержит вопросов")
        session.expunge(quiz)
        for q in questions:
            session.expunge(q)
        return quiz, questions


def export_quiz(
    quiz_id: str, export_format: ExportFormat = "pptx", mode: ExportMode = "teacher",
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



# PPTX
def _build_pptx(quiz: Quiz, questions: list[Question], mode: ExportMode) -> tuple[bytes, str, str]:
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
        body.text = re.sub(r'\$(.+?)\$', r'[\1]', question.question_text)

        type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
        tp = body.add_paragraph()
        tp.text = f"Тип: {type_label}"
        tp.level = 0
        tp.font.size = Pt(14)

        for option in question.answers or []:
            opt_text = re.sub(r'\$(.+?)\$', r'[\1]', _format_option(option))
            op = body.add_paragraph()
            op.text = f"• {opt_text}"
            op.level = 1

        if mode == "teacher":
            ans_text = re.sub(r'\$(.+?)\$', r'[\1]', _format_answers(question.correct_answers))
            ap = body.add_paragraph()
            ap.text = f"Правильный ответ: {ans_text}"
            ap.level = 0
            if question.explanation:
                expl = re.sub(r'\$(.+?)\$', r'[\1]', question.explanation)
                ep = body.add_paragraph()
                ep.text = f"Пояснение: {expl}"
                ep.level = 0

    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue(), _safe_filename(quiz.title, "pptx"), \
           "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# PDF экспорт
def _clean_latex_text(text: str) -> str:
    """
    Очищает текст от артефактов:
    - Заменяем двойные скобки [[]] на []
    - Заменяет \\ на \
    - Убирает [ ] вокруг LaTeX-формул
    """
    text = text.replace('\\\\', '\\')
    text = text.replace('[[', '[').replace(']]', ']')
    text = re.sub(r'\[\s*(\$.+?\$)\s*\]', r'\1', text)
    
    return text


def _draw_inline_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float,
                      font_name: str = "DejaVu", font_size: int = 11, line_height: int = 14) -> float:
    """
    Рисует текст с inline LaTeX-формулами.
    Сначала рендерит все LaTeX-формулы как изображения,
    затем выводит оставшийся текст БЕЗ формул.
    """
    text = _clean_latex_text(text)
    
    latex_parts = re.findall(r'\$(.+?)\$', text)
    
    # удаляем все latex-формулы из текста
    clean_text = re.sub(r'\$.+?\$', '<<<LATEX_PLACEHOLDER>>>', text)
    text_parts = clean_text.split('<<<LATEX_PLACEHOLDER>>>')
    
    current_x = x
    current_y = y
    latex_index = 0
    
    for i, text_part in enumerate(text_parts):
        # текстовая часть
        if text_part:
            words = text_part.split(' ')
            for j, word in enumerate(words):
                if j > 0:
                    word = ' ' + word
                
                c.setFont(font_name, font_size)
                width = c.stringWidth(word, font_name, font_size)
                
                if current_x + width > x + max_width and current_x > x:
                    current_y -= line_height
                    current_x = x
                    word = word.lstrip()
                    width = c.stringWidth(word, font_name, font_size)
                
                c.drawString(current_x, current_y, word)
                current_x += width
        
        # latex-формула
        if i < len(text_parts) - 1 and latex_index < len(latex_parts):
            latex = latex_parts[latex_index]
            latex_index += 1
            
            img_bytes = _render_latex_matplotlib(latex)
            if img_bytes:
                try:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp.write(img_bytes)
                        tmp_path = tmp.name
                    
                    img = PILImage.open(tmp_path)
                    img_w, img_h = img.size
                    
                    scale = (font_size * 1.5) / img_h
                    w = img_w * scale * 0.75
                    h = img_h * scale * 0.75
                    
                    if current_x + w > x + max_width and current_x > x:
                        current_y -= line_height
                        current_x = x
                    
                    c.drawImage(tmp_path, current_x, current_y - h + (font_size * 0.9), width=w, height=h)
                    current_x += w + 2
                    
                    os.unlink(tmp_path)
                except Exception:
                    pass
    
    return current_y - line_height


def _build_pdf(quiz: Quiz, questions: list[Question], mode: ExportMode) -> tuple[bytes, str, str]:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    
    margin = 20 * mm
    max_text_width = width - 2 * margin
    
    x = margin
    y = height - margin
    
    # титульник
    c.setFont("DejaVu-Bold", 18)
    c.drawString(x, y, quiz.title)
    y -= 25
    
    subtitle = _quiz_subtitle(quiz)
    if subtitle:
        c.setFont("DejaVu", 12)
        c.drawString(x, y, subtitle)
        y -= 30
    
    for index, question in enumerate(questions, start=1):
        # проверка места на странице
        if y < 80:
            c.showPage()
            y = height - margin
        
        # номер вопроса
        c.setFont("DejaVu-Bold", 14)
        c.drawString(x, y, f"Вопрос {index}")
        y -= 22
        
        # текст вопроса
        y = _draw_inline_text(c, question.question_text, x, y, max_text_width, "DejaVu", 11, 14)
        y -= 8
        
        # тип вопроса
        type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
        c.setFont("DejaVu", 10)
        c.drawString(x, y, f"Тип: {type_label}")
        y -= 18
        
        # варианты ответов
        for option in question.answers or []:
            if y < 30:
                c.showPage()
                y = height - margin
            y = _draw_inline_text(c, f"- {_format_option(option)}", x, y, max_text_width, "DejaVu", 11, 14)
        
        # правильные ответы и пояснение
        if mode == "teacher":
            y -= 8
            if y < 40:
                c.showPage()
                y = height - margin
            
            c.setFont("DejaVu-Bold", 10)
            c.drawString(x, y, "Правильный ответ:")
            y -= 16
            
            if isinstance(question.correct_answers, list):
                for answer in question.correct_answers:
                    if y < 20:
                        c.showPage()
                        y = height - margin
                    y = _draw_inline_text(c, str(answer), x, y, max_text_width, "DejaVu", 10, 13)
            else:
                y = _draw_inline_text(c, str(question.correct_answers or ""), x, y, max_text_width, "DejaVu", 10, 13)
            
            if question.explanation:
                y -= 8
                if y < 40:
                    c.showPage()
                    y = height - margin
                c.setFont("DejaVu-Bold", 10)
                c.drawString(x, y, "Пояснение:")
                y -= 16
                y = _draw_inline_text(c, question.explanation, x, y, max_text_width, "DejaVu", 10, 13)
        
        # отступ меж вопросами
        y -= 20
        
        # новая страница для след вопроса
        if index < len(questions):
            c.showPage()
            y = height - margin
    
    c.save()
    buf.seek(0)
    return buf.getvalue(), _safe_filename(quiz.title, "pdf"), "application/pdf"