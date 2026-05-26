from io import BytesIO
from typing import Literal

from fastapi import HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.db.database import get_db_session
from app.services.attempts_service import get_quiz_results
from app.services.pdf_common import format_duration_seconds, safe_filename

SortBy = Literal["name", "score", "time", "attempt"]
SortDir = Literal["asc", "desc"]

_TABLE_HEADERS = (
    "Имя и фамилия / Команда",
    "Баллы",
    "Затраченное время",
    "Номер попытки",
)
_EMPTY_ROW = "Пока нет результатов"


def _sort_results(
    results: list[dict], sort_by: SortBy, sort_dir: SortDir
) -> list[dict]:
    reverse = sort_dir == "desc"

    def key_name(row: dict) -> str:
        return (row.get("student_name") or "").casefold()

    def key_score(row: dict) -> int:
        return int(row.get("score") or 0)

    def key_time(row: dict) -> int:
        return int(row.get("duration_seconds") or 0)

    def key_attempt(row: dict) -> int:
        return int(row.get("attempt_number") or 0)

    key_map = {
        "name": key_name,
        "score": key_score,
        "time": key_time,
        "attempt": key_attempt,
    }
    key_fn = key_map.get(sort_by, key_score)
    return sorted(results, key=key_fn, reverse=reverse)


def _resolve_max_score(results: list[dict], fallback_max: int) -> int:
    for row in results:
        max_score = row.get("max_score")
        if max_score:
            return int(max_score)
    return fallback_max or 1


def _average_score(results: list[dict]) -> float:
    if not results:
        return 0.0
    total = sum(int(r.get("score") or 0) for r in results)
    return round(total / len(results), 1)


def _truncate_text(text: str, max_chars: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1] + "…"


def export_results_pdf(
    quiz_id: str,
    sort_by: SortBy = "score",
    sort_dir: SortDir = "desc",
) -> tuple[bytes, str, str]:
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")
        quiz_title = quiz.title
        quiz_max_fallback = sum(int(q.points or 0) for q in quiz.questions)

    raw_results = get_quiz_results(quiz_id)
    sorted_results = _sort_results(raw_results, sort_by, sort_dir)
    max_score = _resolve_max_score(sorted_results, quiz_max_fallback)
    average = _average_score(sorted_results)
    students_count = len(sorted_results)

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    pdf.setFont("DejaVu-Bold", 18)
    pdf.drawString(margin, y, quiz_title)
    y -= 28

    pdf.setFont("DejaVu", 12)
    pdf.drawString(
        margin,
        y,
        f"Средний балл: {average} из {max_score}",
    )
    y -= 18
    pdf.drawString(margin, y, f"Всего учеников: {students_count}")
    y -= 28

    col_widths = [70 * mm, 28 * mm, 42 * mm, 32 * mm]
    row_height = 8 * mm
    x_cols = [margin]
    for w in col_widths[:-1]:
        x_cols.append(x_cols[-1] + w)

    pdf.setFont("DejaVu-Bold", 10)
    for header, x, w in zip(_TABLE_HEADERS, x_cols, col_widths):
        pdf.drawString(x + 2 * mm, y, _truncate_text(header, 42))
    y -= row_height

    pdf.setFont("DejaVu", 10)
    if not sorted_results:
        pdf.drawString(margin + 2 * mm, y, _EMPTY_ROW)
    else:
        for row in sorted_results:
            if y < margin + row_height:
                pdf.showPage()
                y = height - margin
                pdf.setFont("DejaVu", 10)

            max_row = int(row.get("max_score") or max_score)
            cells = [
                row.get("student_name") or "",
                f"{int(row.get('score') or 0)}/{max_row}",
                format_duration_seconds(row.get("duration_seconds")),
                str(int(row.get("attempt_number") or 0)),
            ]
            limits = [36, 12, 18, 8]
            for value, x, limit in zip(cells, x_cols, limits):
                pdf.drawString(x + 2 * mm, y, _truncate_text(str(value), limit))
            y -= row_height

    pdf.save()
    buf.seek(0)
    filename = safe_filename(f"{quiz_title}_результаты", "pdf")
    return buf.getvalue(), filename, "application/pdf"
