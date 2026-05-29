import math
import os
import re
import tempfile
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from lxml import etree
from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Pt
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import matplotlib
matplotlib.use('Agg')

from app.services.latex_renderer import render_latex_to_png
from app.db.database import get_db_session
from app.db.models import Question, Quiz

ExportFormat = Literal["pptx", "pdf"]
ExportMode = Literal["teacher", "student"]

_BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
_BUNDLED_FONT_BOLD = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans-Bold.ttf"
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

_FONT_REGISTERED = False

# Эмпирические константы под стандартный layout 1 (Title and Content) 16:9
_PPTX_BODY_WIDTH_CHARS = 60   # ~ сколько символов умещается в строку плейсхолдера при 18pt
_PPTX_BODY_MAX_LINES   = 12   # сколько визуальных строк помещается по высоте при 18pt
_PPTX_WRAP_CHARS = 78
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
    (r"\\cap", "∩"),
    (r"\\cup", "∪"),
    (r"\\subset", "⊂"),
    (r"\\supset", "⊃"),
    (r"\\subseteq", "⊆"),
    (r"\\supseteq", "⊇"),
    (r"\\in", "∈"),
    (r"\\notin", "∉"),
    (r"\\emptyset", "∅"),
    (r"\\forall", "∀"),
    (r"\\exists", "∃"),
)

_INLINE_LATEX_RE = re.compile(
    r"(\$\$.+?\$\$|\$.+?\$|\\\(.+?\\\)|\\\[.+?\\\])",
    re.DOTALL,
)

_A_NS   = "http://schemas.openxmlformats.org/drawingml/2006/main"
_MC_NS  = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"
_M_NS   = "http://schemas.openxmlformats.org/officeDocument/2006/math"

# mhchem / расширения LaTeX: latex2mathml -> OMML даёт невалидный для PowerPoint XML
# (например \ce и тело формулы разбиваются на отдельные <m:r>).
_MHCHEM_OR_UNSUPPORTED_OMML = re.compile(
    r"\\ce\b|\\cf\b|\\cee\b|\\pu\b|\\bond\b|"
    r"\\x(?:left|right)arrow\b|\\xrightleftharpoons\b|\\xleftrightarrow\b",
    re.IGNORECASE,
)


def _latex_skip_omml_use_plaintext(latex: str) -> bool:
    s = (latex or "").strip()
    return bool(s and _MHCHEM_OR_UNSUPPORTED_OMML.search(s))


def _latex_plaintext_for_slide(latex: str) -> str:
    """Формула для слайда без OMML: убрать обёртки mhchem, остальное упростить."""
    s = (latex or "").strip()
    s = re.sub(r"\\ce\{([^}]*)\}", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"\\cf\{([^}]*)\}", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"\\cee\{([^}]*)\}", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"\\pu\{([^}]*)\}", r"\1", s, flags=re.IGNORECASE)
    return _simplify_latex_for_export(s) or s


def _make_text_run(text: str, font_size_pt: int = 14) -> etree._Element:
    a_r = etree.Element(f"{{{_A_NS}}}r", nsmap={"a": _A_NS})
    rpr = etree.SubElement(a_r, f"{{{_A_NS}}}rPr")
    rpr.set("lang", "ru-RU")
    rpr.set("dirty", "0")
    rpr.set("sz", str(font_size_pt * 100))  # pptx хранит размер в сотых пункта
    a_t = etree.SubElement(a_r, f"{{{_A_NS}}}t")
    a_t.text = text
    return a_r


class _PptxFormulaLayout:
    """Размещает PNG-формулы на слайде через add_picture (не wp:inline из Word)."""

    _TEXT_LINE_PT = 20
    _LEVEL_INDENT_PT = 18
    _TOP_PADDING_PT = 6
    _FORMULA_GAP_PT = 4

    def __init__(self, slide) -> None:
        placeholder = slide.shapes.placeholders[1]
        self.slide = slide
        self.body_left = placeholder.left
        self.body_top = placeholder.top

    def _level_indent(self, level: int) -> int:
        return Pt(level * self._LEVEL_INDENT_PT)

    @staticmethod
    def _formula_height_pt(png_bytes: bytes, font_size_pt: int) -> float:
        """Высота PNG в пунктах — та же формула, что в PDF (_draw_inline_text)."""
        img = PILImage.open(BytesIO(png_bytes))
        img_h = img.size[1]
        if img_h <= 0:
            return float(font_size_pt)
        scale = (font_size_pt * 1.5) / img_h
        return img_h * scale * 0.75

    def add_formula_picture(
        self,
        png_bytes: bytes,
        top_offset,
        level: int,
        font_size_pt: int,
    ) -> None:
        img = PILImage.open(BytesIO(png_bytes))
        img_w, img_h = img.size
        if img_h <= 0:
            return

        scale = (font_size_pt * 1.5) / img_h
        height = Pt(img_h * scale * 0.75)
        left = self.body_left + self._level_indent(level)
        top = self.body_top + top_offset + Pt(2)
        self.slide.shapes.add_picture(BytesIO(png_bytes), left, top, height=height)


def _expand_pptx_body_lines(
    lines: list[tuple[str, int]],
) -> list[tuple[str, int, str | None]]:
    """Текст и каждая формула — отдельная строка слайда (без inline-позиционирования)."""
    expanded: list[tuple[str, int, str | None]] = []
    for text, level in lines:
        parts = _split_text_and_formulas(text or "")
        if not parts:
            expanded.append(("", level, None))
            continue
        for kind, content, _display in parts:
            if kind == "text":
                if content.strip():
                    expanded.append((content, level, None))
            elif content.strip():
                expanded.append(("", level, content.strip()))
    return expanded


def _prepare_paragraph(paragraph, level: int, font_size_pt: int) -> None:
    p_elem = paragraph._p
    for child in list(p_elem):
        tag = child.tag
        if tag == qn("a:r") or tag == qn("a:br") or tag.endswith("}AlternateContent"):
            p_elem.remove(child)

    p_pr = p_elem.find(qn("a:pPr"))
    if p_pr is None:
        p_pr = etree.SubElement(p_elem, qn("a:pPr"))
        p_elem.insert(0, p_pr)
    p_pr.set("lvl", str(level))

    ln_spc = p_pr.find(qn("a:lnSpc"))
    if ln_spc is None:
        ln_spc = etree.SubElement(p_pr, qn("a:lnSpc"))
    for old in list(ln_spc):
        ln_spc.remove(old)
    spc_pts = etree.SubElement(ln_spc, qn("a:spcPts"))
    spc_pts.set("val", str(int(_PptxFormulaLayout._TEXT_LINE_PT * 100)))


def _fill_pptx_body(
    text_frame,
    expanded: list[tuple[str, int, str | None]],
    slide,
) -> None:
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    layout = _PptxFormulaLayout(slide)
    y_offset = Pt(layout._TOP_PADDING_PT)

    for index, (text, level, latex) in enumerate(expanded):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        font_size = 14 if level == 0 else 12
        _prepare_paragraph(paragraph, level, font_size)
        p_elem = paragraph._p

        if latex:
            png = render_latex_to_png(latex)
            if png:
                p_elem.append(_make_text_run(" ", font_size))
                layout.add_formula_picture(png, y_offset, level, font_size)
                row_height = layout._formula_height_pt(png, font_size) + layout._FORMULA_GAP_PT
            else:
                fallback = _latex_plaintext_for_slide(latex)
                p_elem.append(_make_text_run(fallback, font_size))
                row_height = layout._TEXT_LINE_PT * _visual_line_count(fallback, level)
        else:
            p_elem.append(_make_text_run(text, font_size))
            row_height = layout._TEXT_LINE_PT * _visual_line_count(text, level)

        y_offset += Pt(row_height)


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


def _split_text_and_formulas(text: str) -> list[tuple[str, str, bool]]:
    """
    Возвращает список [(kind, content, display_mode)], где kind = 'text' | 'math'.
    """
    if not text:
        return []
    result: list[tuple[str, str, bool]] = []
    pos = 0
    for m in _INLINE_LATEX_RE.finditer(text):
        if m.start() > pos:
            result.append(("text", text[pos:m.start()], False))
        raw = m.group(0)
        for opener, closer, display in (
            ("$$", "$$", True),
            ("$", "$", False),
            (r"\(", r"\)", False),
            (r"\[", r"\]", True),
        ):
            if raw.startswith(opener) and raw.endswith(closer):
                result.append(("math", raw[len(opener):-len(closer)].strip(), display))
                break
        pos = m.end()
    if pos < len(text):
        result.append(("text", text[pos:], False))
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


def _format_option_raw(option) -> str:
    if isinstance(option, str):
        return option
    if isinstance(option, dict):
        return str(
            (option or {}).get("text") or (option or {}).get("label") or (option or {}).get("id") or ""
        )
    return str(option)


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


def _ensure_pdf_fonts() -> None:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    font_path = _resolve_pdf_font_path()
    pdfmetrics.registerFont(TTFont("DejaVu", str(font_path)))

    bold_path = _BUNDLED_FONT_BOLD if _BUNDLED_FONT_BOLD.is_file() and _is_valid_ttf(_BUNDLED_FONT_BOLD) else font_path
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold_path)))
    _FONT_REGISTERED = True


def _safe_filename(title: str, extension: str) -> str:
    """Создаёт имя файла"""
    base = re.sub(r'[<>:"/\\|?*]', "", title).strip() or "quiz"
    base = base[:80]
    return f"{base}.{extension}"


# Загрузка викторины
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


def _visual_line_count(text: str, level: int) -> int:
    # с поправкой на отступ для уровня
    width = _PPTX_BODY_WIDTH_CHARS - (4 if level > 0 else 0)
    if not text:
        return 1
    return max(1, math.ceil(len(text) / width))


def _expanded_visual_line_count(text: str, level: int, latex: str | None) -> int:
    if latex:
        font_size = 14 if level == 0 else 12
        est_h = font_size * 1.5 * 0.75 + _PptxFormulaLayout._FORMULA_GAP_PT
        return max(2, math.ceil(est_h / _PptxFormulaLayout._TEXT_LINE_PT))
    return _visual_line_count(text, level)


def _paginate_expanded_lines(
    lines: list[tuple[str, int, str | None]],
    max_lines: int = _PPTX_BODY_MAX_LINES,
) -> list[list[tuple[str, int, str | None]]]:
    if not lines:
        return [[]]

    pages: list[list[tuple[str, int, str | None]]] = []
    current: list[tuple[str, int, str | None]] = []
    current_visual = 0

    for text, level, latex in lines:
        needed = _expanded_visual_line_count(text, level, latex)
        if needed >= max_lines and current:
            pages.append(current)
            current, current_visual = [], 0
        if current_visual + needed > max_lines and current:
            pages.append(current)
            current, current_visual = [], 0
        current.append((text, level, latex))
        current_visual += needed

    if current:
        pages.append(current)
    return pages


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
    paragraphs.append((question.question_text or "", 0))

    type_label = _TYPE_LABELS.get(question.question_type, question.question_type)
    paragraphs.append((f"Тип: {type_label}", 0))

    for option in question.answers or []:
        opt_raw = _format_option_raw(option)
        paragraphs.append((opt_raw, 1))

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
        expanded = _expand_pptx_body_lines(paragraphs)
        pages = _paginate_expanded_lines(expanded)
        for part_idx, page in enumerate(pages):
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = (
                f"Вопрос {index}" if part_idx == 0 else f"Вопрос {index} (продолжение)"
            )
            _fill_pptx_body(slide.shapes.placeholders[1].text_frame, page, slide)

    buffer = BytesIO()
    prs.save(buffer)
    filename = _safe_filename(quiz.title, "pptx")
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return buffer.getvalue(), filename, media_type


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


def _draw_inline_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    font_name: str = "DejaVu",
    font_size: int = 11,
    line_height: int = 14,
) -> float:
    """
    Рисует текст с inline LaTeX-формулами ($...$).
    Логика масштабирования и вставки PNG — как в рабочем export-варианте.
    """
    text = _clean_latex_text(text or "")

    latex_parts = re.findall(r"\$(.+?)\$", text)
    clean_text = re.sub(r"\$.+?\$", "<<<LATEX_PLACEHOLDER>>>", text)
    text_parts = clean_text.split("<<<LATEX_PLACEHOLDER>>>")

    current_x = x
    current_y = y
    latex_index = 0

    for i, text_part in enumerate(text_parts):
        if text_part:
            words = text_part.split(" ")
            for j, word in enumerate(words):
                if j > 0:
                    word = " " + word

                c.setFont(font_name, font_size)
                width = c.stringWidth(word, font_name, font_size)

                if current_x + width > x + max_width and current_x > x:
                    current_y -= line_height
                    current_x = x
                    word = word.lstrip()
                    width = c.stringWidth(word, font_name, font_size)

                c.drawString(current_x, current_y, word)
                current_x += width

        if i < len(text_parts) - 1 and latex_index < len(latex_parts):
            latex = latex_parts[latex_index]
            latex_index += 1

            img_bytes = render_latex_to_png(latex)
            if not img_bytes:
                fb = _latex_plaintext_for_slide(latex) or latex or "?"
                c.setFont(font_name, font_size)
                w_fb = c.stringWidth(fb, font_name, font_size)
                if current_x + w_fb > x + max_width and current_x > x:
                    current_y -= line_height
                    current_x = x
                c.drawString(current_x, current_y, fb)
                current_x += w_fb + 2
                continue

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
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

                c.drawImage(
                    tmp_path,
                    current_x,
                    current_y - h + (font_size * 0.9),
                    width=w,
                    height=h,
                )
                current_x += w + 2
            except Exception as e:
                import logging

                logging.warning("Failed to render LaTeX %r: %s", latex, e)
                fb2 = _latex_plaintext_for_slide(latex) or latex or "?"
                c.setFont(font_name, font_size)
                w_fb2 = c.stringWidth(fb2, font_name, font_size)
                if current_x + w_fb2 > x + max_width and current_x > x:
                    current_y -= line_height
                    current_x = x
                c.drawString(current_x, current_y, fb2)
                current_x += w_fb2 + 2
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

    return current_y - line_height


def _build_pdf(quiz: Quiz, questions: list[Question], mode: ExportMode) -> tuple[bytes, str, str]:
    _ensure_pdf_fonts()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin = 20 * mm
    max_text_width = width - 2 * margin

    x = margin
    y = height - margin

    # титульник
    c.setFont("DejaVu-Bold", 18)
    c.drawString(x, y, quiz.title or "Викторина")
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
        y = _draw_inline_text(
            c, question.question_text or "", x, y, max_text_width, "DejaVu", 11, 14,
        )
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
            y = _draw_inline_text(
                c, f"- {_format_option_raw(option)}", x, y, max_text_width, "DejaVu", 11, 14,
            )

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
                y = _draw_inline_text(
                    c, str(question.correct_answers or ""), x, y, max_text_width, "DejaVu", 10, 13,
                )

            if question.explanation:
                y -= 8
                if y < 40:
                    c.showPage()
                    y = height - margin
                c.setFont("DejaVu-Bold", 10)
                c.drawString(x, y, "Пояснение:")
                y -= 16
                y = _draw_inline_text(
                    c, question.explanation or "", x, y, max_text_width, "DejaVu", 10, 13,
                )

        # отступ меж вопросами
        y -= 20

        # новая страница для след вопроса
        if index < len(questions):
            c.showPage()
            y = height - margin

    c.save()
    buf.seek(0)
    return buf.getvalue(), _safe_filename(quiz.title, "pdf"), "application/pdf"
