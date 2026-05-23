import json

from app.schemas.quiz import GenerateQuizRequest, GenerateQuizResponse, DifficultyLevel
from app.schemas.material import SourceFragment
from app.services.gigachat_service import gigachat_service
from app.services.prompt_service import build_quiz_prompt
from app.services.material_service import material_service
from app.core.logger import logger


class QuizService:
    def _extract_json(self, raw_text: str) -> dict:
        raw_text = raw_text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        return json.loads(raw_text)

    def _enrich_questions_with_source_fragments(
        self,
        result: GenerateQuizResponse,
        fragments: list[SourceFragment]
    ) -> GenerateQuizResponse:
        return result

    def _normalize_difficulty_value(self, value: str) -> str:
        if not isinstance(value, str):
            return "easy"

        value = value.strip()

        if "." in value:
            value = value.split(".")[-1]

        value = value.lower()

        if value in {"easy", "medium", "hard"}:
            return value

        return "easy"

    def _normalize_question_dict(self, question: dict, fallback_difficulty: str) -> dict:
        normalized = dict(question)

        if "correct answers" in normalized and "correct_answers" not in normalized:
            normalized["correct_answers"] = normalized.pop("correct answers")

        if "correctAnswers" in normalized and "correct_answers" not in normalized:
            normalized["correct_answers"] = normalized.pop("correctAnswers")

        if "source fragment id" in normalized and "source_fragment_id" not in normalized:
            normalized["source_fragment_id"] = normalized.pop("source fragment id")

        normalized["difficulty"] = self._normalize_difficulty_value(
            normalized.get("difficulty", fallback_difficulty)
        )

        if "correct_answers" not in normalized:
            normalized["correct_answers"] = []

        return normalized

    def _normalize_quiz_response_data(self, data: dict, fallback_difficulty: str) -> dict:
        normalized = dict(data)
        questions = normalized.get("questions", [])

        normalized["questions"] = [
            self._normalize_question_dict(question, fallback_difficulty)
            for question in questions
            if isinstance(question, dict)
        ]

        return normalized

    def _apply_difficulty_to_all_questions(
        self,
        result: GenerateQuizResponse,
        difficulty: str
    ) -> GenerateQuizResponse:
        difficulty_enum = DifficultyLevel(difficulty)

        updated_questions = [
            question.model_copy(update={"difficulty": difficulty_enum})
            for question in result.questions
        ]

        return result.model_copy(update={"questions": updated_questions})

    def generate_quiz(self, payload: GenerateQuizRequest) -> GenerateQuizResponse:
        logger.info(
            f"START generate_quiz | subject={payload.subject} | grade={payload.grade} | "
            f"topic={payload.topic} | question_count={payload.question_count} | "
            f"question_types={payload.question_types} | difficulty={payload.difficulty} | "
            f"source_text_len={len(payload.source_text) if payload.source_text else 0}"
        )

        manual_fragments = []

        cleaned_source_text = (payload.source_text or "").strip()
        if cleaned_source_text.lower() in {"string", "source_text", "null", "none"}:
            cleaned_source_text = ""

        if cleaned_source_text:
            manual_fragments = [
                SourceFragment(
                    fragment_id="manual_1",
                    source_type="manual_text",
                    source_name="teacher_input",
                    text=cleaned_source_text
                )
            ]

        combined_context = material_service.build_combined_context(manual_fragments, max_chars=4000)

        prompt = build_quiz_prompt(
            subject=payload.subject,
            grade=payload.grade,
            topic=payload.topic,
            question_count=payload.question_count,
            question_types=payload.question_types,
            difficulty=payload.difficulty.value,
            combined_context=combined_context,
            fragments=manual_fragments
        )

        raw = gigachat_service.chat(
            messages=[
                {"role": "system", "content": "Ты возвращаешь только валидный JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        logger.info(f"RAW_MODEL_RESPONSE: {raw[:2000]}")

        try:
            data = self._extract_json(raw)
            data = self._normalize_quiz_response_data(data, payload.difficulty.value)
            result = GenerateQuizResponse(**data)
            result = self._enrich_questions_with_source_fragments(result, manual_fragments)
            result = self._apply_difficulty_to_all_questions(result, payload.difficulty.value)

            logger.info(
                f"SUCCESS generate_quiz | title={result.quiz_title} | questions_count={len(result.questions)}"
            )
            return result

        except Exception as e:
            logger.error(f"JSON_PARSE_ERROR: {str(e)}")
            logger.error(f"BROKEN_RAW_RESPONSE: {raw[:2000]}")
            raise

    def generate_quiz_from_fragments(
        self,
        subject: str,
        grade: str,
        topic: str,
        question_count: int,
        question_types: list[str],
        difficulty: str,
        fragments: list[SourceFragment]
    ) -> GenerateQuizResponse:
        logger.info(
            f"START generate_quiz_from_fragments | subject={subject} | grade={grade} | "
            f"topic={topic} | question_count={question_count} | difficulty={difficulty} | "
            f"fragments_count={len(fragments)}"
        )

        combined_context = material_service.build_combined_context(fragments, max_chars=6000)

        prompt = build_quiz_prompt(
            subject=subject,
            grade=grade,
            topic=topic,
            question_count=question_count,
            question_types=question_types,
            difficulty=difficulty,
            combined_context=combined_context,
            fragments=fragments
        )

        raw = gigachat_service.chat(
            messages=[
                {"role": "system", "content": "Ты возвращаешь только валидный JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        logger.info(f"RAW_MODEL_RESPONSE_FROM_FRAGMENTS: {raw[:2000]}")

        try:
            data = self._extract_json(raw)
            data = self._normalize_quiz_response_data(data, difficulty)
            result = GenerateQuizResponse(**data)
            result = self._enrich_questions_with_source_fragments(result, fragments)
            result = self._apply_difficulty_to_all_questions(result, difficulty)

            logger.info(
                f"SUCCESS generate_quiz_from_fragments | title={result.quiz_title} | questions_count={len(result.questions)}"
            )
            return result

        except Exception as e:
            logger.error(f"JSON_PARSE_ERROR_FROM_FRAGMENTS: {str(e)}")
            logger.error(f"BROKEN_RAW_RESPONSE_FROM_FRAGMENTS: {raw[:2000]}")
            raise


quiz_service = QuizService()