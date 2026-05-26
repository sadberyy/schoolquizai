"""LaTeX → OMML конвертер. Используется в экспорте PPTX."""
from functools import lru_cache
from pathlib import Path

from lxml import etree
import latex2mathml.converter

_XSL_PATH = Path(__file__).resolve().parent.parent / "assets" / "xsl" / "MML2OMML.XSL"


@lru_cache(maxsize=1)
def _get_transform() -> etree.XSLT:
    if not _XSL_PATH.is_file():
        raise FileNotFoundError(f"Не найден XSLT MathML→OMML: {_XSL_PATH}")
    xslt_doc = etree.parse(str(_XSL_PATH))
    return etree.XSLT(xslt_doc)


def latex_to_omml(latex: str) -> etree._Element | None:
    """
    Преобразует LaTeX-формулу в OMML-элемент <m:oMath>.
    Возвращает None, если конвертация невозможна.
    """
    latex = (latex or "").strip()
    if not latex:
        return None
    try:
        mathml_str = latex2mathml.converter.convert(latex)
        mathml_tree = etree.fromstring(mathml_str.encode("utf-8"))
        omml_doc = _get_transform()(mathml_tree)
        return omml_doc.getroot()
    except Exception:
        return None