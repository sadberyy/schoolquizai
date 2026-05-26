import re
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
_FONT_CANDIDATES = [
    _BUNDLED_FONT,
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]

_FONT_PATH: str | None = None
for candidate in _FONT_CANDIDATES:
    if candidate.is_file():
        _FONT_PATH = str(candidate)
        pdfmetrics.registerFont(TTFont("DejaVu", _FONT_PATH))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", _FONT_PATH))
        break

if not _FONT_PATH:
    raise RuntimeError("Не найден шрифт DejaVuSans для PDF")


def safe_filename(title: str, extension: str) -> str:
    base = re.sub(r'[<>:"/\\|?*]', "", title).strip() or "quiz"
    base = base[:80].strip()
    return f"{base}.{extension}"


def format_duration_seconds(seconds: int | None) -> str:
    total = max(0, int(seconds or 0))
    minutes = total // 60
    secs = total % 60
    return f"{minutes} мин {secs} сек"
