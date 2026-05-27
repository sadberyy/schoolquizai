import unittest
from types import SimpleNamespace

from pptx import Presentation

from app.services.latex_renderer import render_latex_to_png
from app.services.presentation_export_service import (
    _PPTX_BODY_MAX_LINES,
    _paginate_body_lines,
    _question_body_paragraphs,
    _simplify_latex_for_export,
    _split_text_and_formulas,
    _visual_line_count,
    _build_pdf,
    _build_pptx,
    _latex_skip_omml_use_plaintext,
)


class TestLatexSimplify(unittest.TestCase):
    def test_cap_symbol_in_simplify_fallback(self):
        self.assertIn("∩", _simplify_latex_for_export(r"A \cap B"))

    def test_split_display_and_inline(self):
        parts = _split_text_and_formulas(r"inline $a$ and $$b=c$$")
        kinds = [(k, d) for k, _c, d in parts]
        self.assertIn(("math", False), kinds)
        self.assertIn(("math", True), kinds)

    def test_frac_and_dollars(self):
        raw = r"Найдите $\frac{1}{b-a}$ при $x>0$"
        simplified = _simplify_latex_for_export(raw)
        self.assertIn("(1)/(b-a)", simplified)
        self.assertNotIn("\\frac", simplified)
        self.assertNotIn("$", simplified)

    def test_mhchem_skips_omml(self):
        self.assertTrue(_latex_skip_omml_use_plaintext(r"\ce{C6H5Br}"))
        self.assertFalse(_latex_skip_omml_use_plaintext(r"x^2+1"))


class TestPptxPagination(unittest.TestCase):
    def _long_question(self):
        return SimpleNamespace(
            question_text=" ".join(["длинный текст вопроса"] * 40),
            question_type="single_choice",
            answers=[f"вариант {i}" for i in range(12)],
            correct_answers=["вариант 1"],
            explanation=" ".join(["пояснение"] * 30),
        )

    def test_many_lines_split_into_pages(self):
        lines = _question_body_paragraphs(self._long_question(), "teacher")
        pages = _paginate_body_lines(lines)
        self.assertGreater(len(pages), 1)
        for page in pages:
            visual_lines = sum(_visual_line_count(text, level) for text, level in page)
            max_single = max(_visual_line_count(text, level) for text, level in page)
            # одна очень длинная строка может занять целый слайд и превысить лимит
            if max_single <= _PPTX_BODY_MAX_LINES:
                self.assertLessEqual(visual_lines, _PPTX_BODY_MAX_LINES)

    def test_build_pptx_creates_continuation_slides(self):
        quiz = SimpleNamespace(
            title="Тест",
            subject="Математика",
            grade="9",
            difficulty="medium",
        )
        questions = [self._long_question()]
        data, _, _ = _build_pptx(quiz, questions, "teacher")
        prs = Presentation(__import__("io").BytesIO(data))
        titles = [slide.shapes.title.text for slide in prs.slides]
        self.assertIn("Вопрос 1 (продолжение)", titles)

    def test_build_pptx_with_mhchem_opens(self):
        """mhchem (\\ce) не должен давать битый OMML — слайд читается python-pptx."""
        quiz = SimpleNamespace(
            title="Химия",
            subject="Химия",
            grade="10",
            difficulty="hard",
        )
        q = SimpleNamespace(
            question_text="Бромирование бензола?",
            question_type="single_choice",
            answers=[r"$\ce{C6H5Br}$", r"$\ce{C6H6}$", r"$\ce{C6H5CH3}$"],
            correct_answers=[r"$\ce{C6H5Br}$"],
            explanation=r"Продукт $\ce{C6H5Br}$.",
        )
        data, _, _ = _build_pptx(quiz, [q], "teacher")
        prs = Presentation(__import__("io").BytesIO(data))
        self.assertGreaterEqual(len(prs.slides), 2)
        body = prs.slides[-1].shapes.placeholders[1].text_frame.text
        self.assertIn("C6H5Br", body.replace(" ", ""))


class TestPdfLatex(unittest.TestCase):
    def test_render_cap_png(self):
        png = render_latex_to_png(r"A \cap B")
        self.assertIsNotNone(png)
        self.assertGreater(len(png or b""), 200)

    def test_build_pdf_with_inline_latex(self):
        quiz = SimpleNamespace(
            title="Математика",
            subject="Алгебра",
            grade="9",
            difficulty="medium",
        )
        q = SimpleNamespace(
            question_text=r"Чему равно $A \cap B$?",
            question_type="single_choice",
            answers=[r"$A \cap B$", r"$A \cup B$", "текст без формул"],
            correct_answers=[r"$A \cap B$"],
            explanation=r"Пересечение: $A \cap B$.",
        )
        data, _, media_type = _build_pdf(quiz, [q], "teacher")
        self.assertEqual(media_type, "application/pdf")
        self.assertGreater(len(data), 500)
        self.assertTrue(data.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
