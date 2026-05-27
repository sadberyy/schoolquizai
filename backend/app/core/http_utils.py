import re
from urllib.parse import quote


def content_disposition_attachment(filename: str) -> dict[str, str]:
    """Заголовок Content-Disposition с UTF-8 именем и ASCII fallback."""
    if "." in filename:
        stem, ext = filename.rsplit(".", 1)
    else:
        stem, ext = filename, ""

    ascii_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", stem)
    ascii_stem = re.sub(r"[^\x20-\x7e]", "_", ascii_stem).strip(" ._")
    if not ascii_stem:
        ascii_stem = "quiz"
    ascii_stem = ascii_stem[:80]
    ascii_fallback = f"{ascii_stem}.{ext}" if ext else ascii_stem

    disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    return {"Content-Disposition": disposition}
