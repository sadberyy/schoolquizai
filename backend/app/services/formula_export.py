"""Единый парсинг, масштаб и вёрстка формул для PDF / PPTX / DOCX."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from typing import Literal

from PIL import Image as PILImage

# PDF (pt) — единый размер текста и формул в теле документа
EXPORT_FONT_BODY_PT = 11.0
EXPORT_FONT_LINE_HEIGHT_PT = 14.0
EXPORT_LINE_GAP_PT = 3.0
EXPORT_BLOCK_GAP_PT = 7.0

# PPTX (pt) — соответствует ~11 pt в PDF; межстрочные отступы шире, чем в PDF
EXPORT_FONT_BODY_PPTX_PT = 14.0
EXPORT_FONT_NESTED_PPTX_PT = 12.0
EXPORT_LINE_GAP_PPTX_PT = 7.0
EXPORT_BLOCK_GAP_PPTX_PT = 10.0

_INLINE_LATEX_RE = re.compile(
    r"(\$\$.+?\$\$|\$.+?\$|\\\(.+?\\\)|\\\[.+?\\\])",
    re.DOTALL,
)

_TALL_LATEX_RE = re.compile(
    r"\\frac|\\sqrt|\\ce\b|\\cf\b|\\sum|\\int|\\prod|\\lim|\\binom|"
    r"\\matrix|\\pmatrix|\\bmatrix|\\begin\{",
    re.IGNORECASE,
)

_PX_PER_PT = 96.0 / 72.0


@dataclass(frozen=True)
class FormulaLayout:
    width_pt: float
    height_pt: float
    baseline_offset_pt: float


@dataclass
class LayoutSegment:
    kind: Literal["text", "math", "fallback"]
    content: str
    display: bool = False
    x_pt: float = 0.0
    width_pt: float = 0.0
    ascent_pt: float = 0.0
    descent_pt: float = 0.0
    png_bytes: bytes | None = None
    formula_layout: FormulaLayout | None = None


@dataclass
class LayoutLine:
    segments: list[LayoutSegment] = field(default_factory=list)
    height_pt: float = 0.0
    ascent_pt: float = 0.0
    descent_pt: float = 0.0


@dataclass
class RichTextLayout:
    lines: list[LayoutLine] = field(default_factory=list)

    @property
    def total_height_pt(self) -> float:
        if not self.lines:
            return EXPORT_FONT_LINE_HEIGHT_PT + EXPORT_BLOCK_GAP_PT
        inner = sum(
            line.height_pt + (EXPORT_LINE_GAP_PT if index else 0)
            for index, line in enumerate(self.lines)
        )
        return inner + EXPORT_BLOCK_GAP_PT


FormulaResolver = Callable[
    [str, bool],
    tuple[bytes | None, FormulaLayout | None, str | None],
]


def split_text_and_formulas(text: str) -> list[tuple[str, str, bool]]:
    """
    Разбивает строку на текст и LaTeX ($...$, $$...$$, \\(...\\), \\[...\\]).
    Возвращает [(kind, content, display)], kind = 'text' | 'math'.
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
                result.append(("math", raw[len(opener) : -len(closer)].strip(), display))
                break
        pos = m.end()
    if pos < len(text):
        result.append(("text", text[pos:], False))
    return result


def is_tall_formula(latex: str) -> bool:
    return bool(_TALL_LATEX_RE.search(latex or ""))


def pptx_font_size_pt(level: int) -> float:
    return EXPORT_FONT_BODY_PPTX_PT if level == 0 else EXPORT_FONT_NESTED_PPTX_PT


def estimate_text_width_pt(text: str, font_size_pt: float) -> float:
    """Оценка ширины текста; для точного layout PPTX/PDF используйте DejaVu measure."""
    return max(len(text), 1) * font_size_pt * 0.52


def next_baseline_after_block(
    start_baseline_y: float,
    layout: RichTextLayout,
) -> float:
    """Baseline Y для следующего блока (PDF-координаты, Y вниз)."""
    if not layout.lines:
        return start_baseline_y - EXPORT_FONT_LINE_HEIGHT_PT - EXPORT_BLOCK_GAP_PT
    baseline_y = start_baseline_y
    for line_index, line in enumerate(layout.lines):
        if line_index + 1 < len(layout.lines):
            baseline_y -= line.height_pt + EXPORT_LINE_GAP_PT
    last_line = layout.lines[-1]
    return baseline_y - last_line.height_pt - EXPORT_BLOCK_GAP_PT


def _target_height_pt(font_size_pt: float, *, display: bool, latex: str, img_h: int) -> float:
    if display:
        return font_size_pt * 1.65

    expected_px = font_size_pt * _PX_PER_PT
    if is_tall_formula(latex) or (img_h > 0 and img_h > expected_px * 1.35):
        ratio = img_h / expected_px if expected_px > 0 else 1.0
        return font_size_pt * min(2.3, max(1.45, ratio * 0.92))

    return font_size_pt * 1.15


def compute_formula_layout(
    png_bytes: bytes,
    font_size_pt: float,
    *,
    display: bool = False,
    latex: str = "",
) -> FormulaLayout:
    """
    Единая формула масштаба PNG-формулы для PDF, PPTX и DOCX.
    Сохраняет пропорции; «высокие» формулы (дроби, корни, mhchem) получают больше места.
    """
    img = PILImage.open(BytesIO(png_bytes))
    img_w, img_h = img.size
    if img_h <= 0:
        h = _target_height_pt(font_size_pt, display=display, latex=latex, img_h=0)
        return FormulaLayout(h, h, font_size_pt * 0.85)

    target_h = _target_height_pt(font_size_pt, display=display, latex=latex, img_h=img_h)
    scale = target_h / img_h
    width_pt = img_w * scale
    height_pt = target_h
    baseline_offset_pt = min(font_size_pt * 0.88, height_pt * 0.82)
    return FormulaLayout(width_pt, height_pt, baseline_offset_pt)


def _text_metrics(font_size_pt: float) -> tuple[float, float]:
    ascent = font_size_pt * 0.72
    descent = font_size_pt * 0.28
    return ascent, descent


def _finalize_line(segments: list[LayoutSegment], font_size_pt: float) -> LayoutLine:
    text_ascent, text_descent = _text_metrics(font_size_pt)
    ascent = text_ascent
    descent = text_descent
    for seg in segments:
        ascent = max(ascent, seg.ascent_pt)
        descent = max(descent, seg.descent_pt)
    height = ascent + descent
    return LayoutLine(segments=segments, height_pt=height, ascent_pt=ascent, descent_pt=descent)


def _layout_items(
    text: str,
    max_width_pt: float,
    font_size_pt: float,
    measure_text: Callable[[str], float],
    resolve_formula: FormulaResolver,
) -> RichTextLayout:
    parts = split_text_and_formulas(text)
    if not parts:
        parts = [("text", text or "", False)]

    lines: list[LayoutLine] = []
    current_segments: list[LayoutSegment] = []
    current_x = 0.0

    def flush_line() -> None:
        nonlocal current_segments, current_x
        if current_segments:
            lines.append(_finalize_line(current_segments, font_size_pt))
        current_segments = []
        current_x = 0.0

    def append_segment(segment: LayoutSegment) -> None:
        nonlocal current_x
        if (
            segment.width_pt > 0
            and current_segments
            and current_x + segment.width_pt > max_width_pt
        ):
            flush_line()
        segment.x_pt = current_x
        current_segments.append(segment)
        current_x += segment.width_pt

    for kind, content, display in parts:
        if kind == "text":
            if not content:
                continue
            words = content.split(" ")
            for index, word in enumerate(words):
                token = word if index == 0 else f" {word}"
                if not token:
                    continue
                width = measure_text(token)
                append_segment(
                    LayoutSegment(
                        kind="text",
                        content=token,
                        width_pt=width,
                        ascent_pt=_text_metrics(font_size_pt)[0],
                        descent_pt=_text_metrics(font_size_pt)[1],
                    )
                )
            continue

        if display and current_segments:
            flush_line()

        png_bytes, formula_layout, fallback = resolve_formula(content, display)
        if formula_layout is not None and png_bytes is not None:
            append_segment(
                LayoutSegment(
                    kind="math",
                    content=content,
                    display=display,
                    width_pt=formula_layout.width_pt + 2,
                    ascent_pt=formula_layout.baseline_offset_pt,
                    descent_pt=formula_layout.height_pt - formula_layout.baseline_offset_pt,
                    png_bytes=png_bytes,
                    formula_layout=formula_layout,
                )
            )
        else:
            fb = fallback or content or "?"
            width = measure_text(fb)
            append_segment(
                LayoutSegment(
                    kind="fallback",
                    content=fb,
                    display=display,
                    width_pt=width + 2,
                    ascent_pt=_text_metrics(font_size_pt)[0],
                    descent_pt=_text_metrics(font_size_pt)[1],
                )
            )

        if display:
            flush_line()

    flush_line()
    return RichTextLayout(lines=lines)


def layout_rich_text(
    text: str,
    max_width_pt: float,
    font_size_pt: float,
    *,
    measure_text: Callable[[str], float],
    resolve_formula: FormulaResolver,
) -> RichTextLayout:
    """
    Разбивает текст+формулы на визуальные строки с корректной высотой.
    Текст и inline-формулы остаются на одной строке, пока влезают по ширине.
    """
    return _layout_items(text, max_width_pt, font_size_pt, measure_text, resolve_formula)
