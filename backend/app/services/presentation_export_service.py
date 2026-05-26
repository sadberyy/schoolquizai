import math
import re
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from fpdf import FPDF
from lxml import etree
from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn

from app.db.database import get_db_session
from app.db.models import Question, Quiz
from app.services.latex_to_omml import latex_to_omml

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
# Эмпирические константы под стандартный layout 1 (Title and Content) 16:9
_PPTX_BODY_WIDTH_CHARS = 60   # ~ сколько символов умещается в строку плейсхолдера при 18pt
_PPTX_BODY_MAX_LINES   = 12   # сколько визуальных строк помещается по высоте при 18pt
# _PPTX_MAX_BODY_LINES = 10
_PPTX_WRAP_CHARS = 78
_LATEX_EXPORT_NOTE = "Формулы в экспорте показаны упрощённо (без LaTeX-рендеринга)."
_LATEX_MARKER_RE = re.compile(
    r"\\frac|\\sqrt|\$\$?|\\\[|\\\]|\\[a-zA-Z]{2,}"
)
_FRAC_RE = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_LATEX_SYMBOLS = (
    (r"\\cdot", "·"),
    (r"\\times", "×"),
    (r"\\pm", "±"),
    (r"\\leq", "≤"),
    (r"\\geq", "≥"),
    (r"\\neq", "≠"),
    (r"\\infty", "∞"),
    (r"\\pi", "π"),
    (r"\\alpha", "α"),
    (r"\\beta", "β"),
    (r"\\gamma", "γ"),
    (r"\\delta", "δ"),
    (r"\\theta", "θ"),
    (r"\\lambda", "λ"),
    (r"\\sigma", "σ"),
    (r"\\rightarrow", "→"),
    (r"\\leftarrow", "←"),
)

_INLINE_LATEX_RE = re.compile(
    r"(\$\$.+?\$\$|\$.+?\$|\\\(.+?\\\)|\\\[.+?\\\])",
    re.DOTALL,
)

_A_NS   = "http://schemas.openxmlformats.org/drawingml/2006/main"
_MC_NS  = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"
_M_NS   = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _make_text_run(text: str, font_size_pt: int = 14) -> etree._Element:
    a_r = etree.Element(f"{{{_A_NS}}}r", nsmap={"a": _A_NS})
    rpr = etree.SubElement(a_r, f"{{{_A_NS}}}rPr")
    rpr.set("lang", "ru-RU")
    rpr.set("dirty", "0")
    rpr.set("sz", str(font_size_pt * 100))  # pptx хранит размер в сотых пункта
    a_t = etree.SubElement(a_r, f"{{{_A_NS}}}t")
    a_t.text = text
    return a_r


def _set_paragraph_with_math(paragraph, text: str, level: int, font_size_pt: int) -> None:
    p_elem = paragraph._p
    # очистить старые runs
    for child in list(p_elem):
        tag = child.tag
        if tag == qn("a:r") or tag == qn("a:br") or tag.endswith("}AlternateContent"):
            p_elem.remove(child)

    # выставить level
    pPr = p_elem.find(qn("a:pPr"))
    if pPr is None:
        pPr = etree.SubElement(p_elem, qn("a:pPr"))
        p_elem.insert(0, pPr)
    pPr.set("lvl", str(level))

    parts = _split_text_and_formulas(text)
    if not parts:
        p_elem.append(_make_text_run("", font_size_pt))
        return

    for kind, content in parts:
        if kind == "text":
            if content:
                p_elem.append(_make_text_run(content, font_size_pt))
        else:  # math
            omml = latex_to_omml(content)
            if omml is not None:
                p_elem.append(_make_math_run(omml, fallback_text=content))
            else:
                # парсинг не удался — вставляем исходник как текст
                p_elem.append(_make_text_run(content, font_size_pt))


def _fill_pptx_body(text_frame, lines: list[tuple[str, int]]) -> None:
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    for index, (text, level) in enumerate(lines):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        font_size = 14 if level == 0 else 12
        _set_paragraph_with_math(paragraph, text, level, font_size)


def _make_math_run(omml_element: etree._Element, fallback_text: str) -> etree._Element:
    """
    Оборачивает OMML в AlternateContent: PowerPoint покажет формулу,
    старые вьюверы — fallback-текст.
    """
    alt = etree.Element(
        f"{{{_MC_NS}}}AlternateContent",
        nsmap={"mc": _MC_NS, "a14": _A14_NS, "m": _M_NS, "a": _A_NS},
    )
    choice = etree.SubElement(alt, f"{{{_MC_NS}}}Choice", Requires="a14")
    a_r = etree.SubElement(choice, f"{{{_A_NS}}}r")
    rpr = etree.SubElement(a_r, f"{{{_A_NS}}}rPr")
    rpr.set("lang", "ru-RU")
    a14_m = etree.SubElement(a_r, f"{{{_A14_NS}}}m")
    a14_m.append(deepcopy(omml_element))

    fallback = etree.SubElement(alt, f"{{{_MC_NS}}}Fallback")
    fallback.append(_make_text_run(fallback_text))
    return alt


def _split_text_and_formulas(text: str) -> list[tuple[str, str]]:
    """
    Возвращает список [(kind, content)], где kind = 'text' | 'math'.
    """
    if not text:
        return []
    result: list[tuple[str, str]] = []
    pos = 0
    for m in _INLINE_LATEX_RE.finditer(text):
        if m.start() > pos:
            result.append(("text", text[pos:m.start()]))
        raw = m.group(0)
        for opener, closer in (("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")):
            if raw.startswith(opener) and raw.endswith(closer):
                result.append(("math", raw[len(opener):-len(closer)].strip()))
                break
        pos = m.end()
    if pos < len(text):
        result.append(("text", text[pos:]))
    return result


def _contains_latex_markers(text: str | None) -> bool:
    return bool(text and _LATEX_MARKER_RE.search(text))


def _simplify_latex_for_export(text: str | None) -> str:
    if not text:
        return ""
    s = str(text)
    while _FRAC_RE.search(s):
        s = _FRAC_RE.sub(lambda m: f"({m.group(1)})/({m.group(2)})", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√\1", s)
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\left|\\right", "", s)
    for pattern, replacement in _LATEX_SYMBOLS:
        s = re.sub(pattern, replacement, s)
    s = re.sub(r"\$\$?", "", s)
    s = re.sub(r"\\\[|\\\]", "", s)
    s = re.sub(r"\\([a-zA-Z]+)", r" \1 ", s)
    while re.search(r"\{[^{}]*\}", s):
        s = re.sub(r"\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _wrap_text_lines(text: str, max_chars: int = _PPTX_WRAP_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word)
        extra = word_len if not current else word_len + 1
        if current and current_len + extra > max_chars:
            lines.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len += extra

    if current:
        lines.append(" ".join(current))
    return lines


def _format_option(option) -> str:
    if isinstance(option, str):
        return _simplify_latex_for_export(option)
    if isinstance(option, dict):
        for key in ("text", "label", "id"):
            val = option.get(key)
            if val is not None and val != "":
                return _simplify_latex_for_export(str(val))
        return ""
    return _simplify_latex_for_export(str(option))


def _format_answers(correct_answers) -> str:
    if correct_answers is None:
        return ""
    if isinstance(correct_answers, list):
        return ", ".join(str(item) for item in correct_answers)
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


def _quiz_has_latex_content(questions: list[Question]) -> bool:
    for question in questions:
        if _contains_latex_markers(question.question_text):
            return True
        if _contains_latex_markers(question.explanation):
            return True
        for option in question.answers or []:
            if isinstance(option, str) and _contains_latex_markers(option):
                return True
            if isinstance(option, dict):
                for key in ("text", "label"):
                    if _contains_latex_markers(option.get(key)):
                        return True
    return False


def _question_body_lines(question: Question, mode: ExportMode) -> list[tuple[str, int]]:
    lines: list[tuple[str, int]] = []
    for part in _wrap_text_lines(_simplify_latex_for_export(question.question_text)):
        lines.append((part, 0))

    type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
    lines.append((f"Тип: {type_label}", 0))

    for option in question.answers or []:
        for part in _wrap_text_lines(f"• {_format_option(option)}"):
            lines.append((part, 1))

    if mode == "teacher":
        answer_text = _simplify_latex_for_export(_format_answers(question.correct_answers))
        for part in _wrap_text_lines(f"Правильный ответ: {answer_text}"):
            lines.append((part, 0))
        if question.explanation:
            for part in _wrap_text_lines(
                f"Пояснение: {_simplify_latex_for_export(question.explanation)}"
            ):
                lines.append((part, 0))

    return lines


# def _paginate_body_lines(lines: list[tuple[str, int]]) -> list[list[tuple[str, int]]]:
#     if not lines:
#         return [[]]
#
#     pages: list[list[tuple[str, int]]] = []
#     current: list[tuple[str, int]] = []
#
#     for line in lines:
#         if len(current) >= _PPTX_MAX_BODY_LINES:
#             pages.append(current)
#             current = []
#         current.append(line)
#
#     if current:
#         pages.append(current)
#     return pages
def _visual_line_count(text: str, level: int) -> int:
    # с поправкой на отступ для уровня
    width = _PPTX_BODY_WIDTH_CHARS - (4 if level > 0 else 0)
    if not text:
        return 1
    return max(1, math.ceil(len(text) / width))


def _paginate_body_lines(
    lines: list[tuple[str, int]],
    max_lines: int = _PPTX_BODY_MAX_LINES,
) -> list[list[tuple[str, int]]]:
    if not lines:
        return [[]]

    pages: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    current_visual = 0

    for text, level in lines:
        needed = _visual_line_count(text, level)
        # если одна «строка» сама по себе больше страницы — кладём её отдельно
        if needed >= max_lines and current:
            pages.append(current)
            current, current_visual = [], 0
        if current_visual + needed > max_lines and current:
            pages.append(current)
            current, current_visual = [], 0
        current.append((text, level))
        current_visual += needed

    if current:
        pages.append(current)
    return pages



def _question_body_paragraphs(question: Question, mode: ExportMode) -> list[tuple[str, int]]:
    paragraphs: list[tuple[str, int]] = []
    paragraphs.append((question.question_text or "", 0))   # ← без _simplify_latex_for_export

    type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
    paragraphs.append((f"Тип: {type_label}", 0))

    for option in question.answers or []:
        # отдаём «сырой» текст с возможным LaTeX
        opt_raw = option if isinstance(option, str) else str(
            (option or {}).get("text") or (option or {}).get("label") or ""
        )
        paragraphs.append((f"• {opt_raw}", 1))

    if mode == "teacher":
        answer = _format_answers(question.correct_answers)
        paragraphs.append((f"Правильный ответ: {answer}", 0))
        if question.explanation:
            paragraphs.append((f"Пояснение: {question.explanation}", 0))
    return paragraphs





def _build_pptx(
    quiz: Quiz,
    questions: list[Question],
    mode: ExportMode,
) -> tuple[bytes, str, str]:
    prs = Presentation()

    # Титульный слайд
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = quiz.title or "Викторина"

    subtitle_parts = [_quiz_subtitle(quiz)]
    subtitle = " · ".join(part for part in subtitle_parts if part)
    if subtitle and len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = subtitle

    # Слайды вопросов
    for index, question in enumerate(questions, start=1):
        paragraphs = _question_body_paragraphs(question, mode)
        pages = _paginate_body_lines(paragraphs)
        for part_idx, page in enumerate(pages):
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = (
                f"Вопрос {index}" if part_idx == 0 else f"Вопрос {index} (продолжение)"
            )
            _fill_pptx_body(slide.shapes.placeholders[1].text_frame, page)

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

    pdf.add_page()
    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(line_width, 10, quiz.title)
    pdf.ln(4)

    subtitle_parts = [_quiz_subtitle(quiz)]
    if _quiz_has_latex_content(questions):
        subtitle_parts.append(_LATEX_EXPORT_NOTE)
    subtitle = " · ".join(part for part in subtitle_parts if part)
    if subtitle:
        pdf.set_font("DejaVu", size=12)
        pdf.multi_cell(line_width, 8, subtitle)
        pdf.ln(6)

    for index, question in enumerate(questions, start=1):
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 14)
        pdf.multi_cell(line_width, 8, f"Вопрос {index}")
        pdf.ln(2)

        pdf.set_font("DejaVu", size=12)
        pdf.multi_cell(
            line_width,
            7,
            _simplify_latex_for_export(question.question_text),
        )
        pdf.ln(2)

        type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
        pdf.set_font("DejaVu", size=11)
        pdf.multi_cell(line_width, 6, f"Тип: {type_label}")
        pdf.ln(1)

        for option in question.answers or []:
            pdf.multi_cell(line_width, 6, f"- {_format_option(option)}")

        if mode == "teacher":
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", size=11)
            pdf.multi_cell(
                line_width,
                6,
                "Правильный ответ: "
                + _simplify_latex_for_export(_format_answers(question.correct_answers)),
            )
            if question.explanation:
                pdf.set_font("DejaVu", size=11)
                pdf.multi_cell(
                    line_width,
                    6,
                    "Пояснение: " + _simplify_latex_for_export(question.explanation),
                )

    filename = _safe_filename(quiz.title, "pdf")
    media_type = "application/pdf"
    return pdf.output(), filename, media_type
