import unittest
from types import SimpleNamespace

from pptx import Presentation

from app.services.presentation_export_service import (
    _paginate_body_lines,
    _question_body_lines,
    _simplify_latex_for_export,
    _build_pptx,
)


class TestLatexSimplify(unittest.TestCase):
    def test_frac_and_dollars(self):
        raw = r"Найдите $\frac{1}{b-a}$ при $x>0$"
        simplified = _simplify_latex_for_export(raw)
        self.assertIn("(1)/(b-a)", simplified)
        self.assertNotIn("\\frac", simplified)
        self.assertNotIn("$", simplified)


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
        lines = _question_body_lines(self._long_question(), "teacher")
        pages = _paginate_body_lines(lines)
        self.assertGreater(len(pages), 1)
        for page in pages:
            self.assertLessEqual(len(page), 10)

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


if __name__ == "__main__":
    unittest.main()
