import json
import re
from app.schemas.quiz import (GenerateQuizRequest,
                              GenerateQuizResponse,
                              DifficultyLevel,
                              QuizQuestion,
                              QuestionIssue
                              )
from app.schemas.material import SourceFragment
from app.services.gigachat_service import gigachat_service
from app.services.prompt_service import build_quiz_prompt, build_quiz_fix_prompt
from app.services.material_service import material_service
from app.core.logger import logger

AI_RESPONSE_PARSE_ERROR = "Ошибка разбора ответа ИИ, попробуйте снова"


class QuizService:
    """
    Сервис генерации викторин.

    Отвечает за полный процесс создания викторины с помощью языковой модели:
    - подготовку входного текста и фрагментов источников;
    - сборку промпта для модели;
    - отправку запроса в GigaChat;
    - извлечение JSON из ответа модели;
    - нормализацию данных;
    - преобразование ответа модели в GenerateQuizResponse.

    Основная идея:
    модель должна вернуть строго валидный JSON, который затем превращается
    в Pydantic-схему GenerateQuizResponse.
    """

    def _extract_json(self, raw_text: str) -> dict:
        """Извлекает JSON между [JSON_START] и [JSON_END]."""
        raw_text = raw_text.strip()
    
        # json между тегами
        start = raw_text.find('[JSON_START]')
        end = raw_text.find('[JSON_END]')
    
        if start != -1 and end != -1:
            raw_text = raw_text[start + len('[JSON_START]'):end].strip()
        elif start != -1:
            raw_text = raw_text[start + len('[JSON_START]'):].strip()
    
        # удаляем markdown-обёртку
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    
        # обрезка до последней }
        last_brace = raw_text.rfind('}')
        if last_brace > 0:
            raw_text = raw_text[:last_brace + 1]
    
        # закрываем незакрытые структуры
        open_braces = raw_text.count('{')
        close_braces = raw_text.count('}')
        open_brackets = raw_text.count('[')
        close_brackets = raw_text.count(']')
    
        raw_text += '}' * (open_braces - close_braces)
        raw_text += ']' * (open_brackets - close_brackets)
        
        raw_text = raw_text.replace('"correct answers"', '"correct_answers"')
        raw_text = raw_text.replace('"correctAnswers"', '"correct_answers"')
        # замена \ перед буквами на \\ (Latex)
        raw_text = re.sub(r'(?<!\\)\\([a-zA-Z]+)', r'\\\\\1', raw_text)

        raw_text = raw_text.replace('\n', ' ').replace('\r', '')
    
        raw_text = raw_text.strip()
    
        if not raw_text:
            raise ValueError(AI_RESPONSE_PARSE_ERROR)

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(AI_RESPONSE_PARSE_ERROR) from e


    def _enrich_questions_with_source_fragments(
        self,
        result: GenerateQuizResponse,
        fragments: list[SourceFragment]
    ) -> GenerateQuizResponse:
        """
        Дополняет вопросы информацией об исходных фрагментах.

        Сейчас метод является заглушкой и просто возвращает result без изменений.

        В будущем здесь можно реализовать логику:
        - сопоставлять question.source_fragment_id с реальным SourceFragment;
        - добавлять в вопрос текст исходного фрагмента;
        - проверять, что вопрос действительно основан на переданном материале;
        - сохранять ссылки на страницы, слайды или блоки документа.

        Args:
            result: сгенерированная викторина.
            fragments: список исходных фрагментов, на основе которых строилась викторина.

        Returns:
            Викторина с обогащёнными вопросами.
        """

        return result

    def _normalize_difficulty_value(self, value: str) -> str:
        """
        Нормализует значение сложности вопроса.

        Модель может вернуть сложность в разных форматах, например:
        - "easy"
        - "Easy"
        - "DifficultyLevel.EASY"
        - "difficulty.easy"
        - некорректное значение

        Метод приводит значение к одному из допустимых вариантов:
        - "easy"
        - "medium"
        - "hard"

        Если значение некорректное, возвращается "easy".

        Args:
            value: значение сложности из ответа модели.

        Returns:
            Нормализованная строка сложности.
        """

        # Если модель вернула не строку, используем безопасное значение по умолчанию
        if not isinstance(value, str):
            return "easy"

        value = value.strip()

        # Если пришло что-то вроде "DifficultyLevel.easy", берём последнюю часть
        if "." in value:
            value = value.split(".")[-1]

        value = value.lower()

        if value in {"easy", "medium", "hard"}:
            return value

        return "easy"

    def _normalize_question_dict(self, question: dict, fallback_difficulty: str) -> dict:
        """
        Нормализует один вопрос из ответа модели.

        Языковая модель может вернуть поля с разными названиями:
        - "correct answers" вместо "correct_answers"
        - "correctAnswers" вместо "correct_answers"
        - "source fragment id" вместо "source_fragment_id"

        Этот метод приводит названия полей к формату, который ожидают Pydantic-схемы.

        Также метод:
        - нормализует difficulty;
        - добавляет пустой список correct_answers, если модель его не вернула.

        Args:
            question: словарь с данными одного вопроса.
            fallback_difficulty: сложность по умолчанию, если у вопроса нет своей сложности.

        Returns:
            Нормализованный словарь вопроса.
        """

        # Создаём копию, чтобы не изменять исходный словарь напрямую
        normalized = dict(question)

        # Приводим разные варианты названия поля правильных ответов к correct_answers
        if "correct answers" in normalized and "correct_answers" not in normalized:
            normalized["correct_answers"] = normalized.pop("correct answers")

        if "correctAnswers" in normalized and "correct_answers" not in normalized:
            normalized["correct_answers"] = normalized.pop("correctAnswers")

        # Приводим название поля source_fragment_id к единому snake_case-формату
        if "source fragment id" in normalized and "source_fragment_id" not in normalized:
            normalized["source_fragment_id"] = normalized.pop("source fragment id")

        # Нормализуем сложность вопроса.
        # Если модель не вернула difficulty, используем fallback_difficulty.
        normalized["difficulty"] = self._normalize_difficulty_value(
            normalized.get("difficulty", fallback_difficulty)
        )

        # Если модель забыла вернуть правильные ответы, подставляем пустой список,
        # чтобы Pydantic-схема не упала на отсутствующем поле.
        if "correct_answers" not in normalized:
            normalized["correct_answers"] = []

        return normalized

    def _normalize_quiz_response_data(self, data: dict, fallback_difficulty: str) -> dict:
        """
        Нормализует весь JSON-ответ модели перед созданием GenerateQuizResponse.

        Основная задача — пройтись по списку questions и привести каждый вопрос
        к ожидаемому формату.

        Args:
            data: исходный JSON-ответ модели в виде словаря.
            fallback_difficulty: сложность по умолчанию для вопросов.

        Returns:
            Нормализованный словарь викторины.
        """

        # Копируем данные, чтобы не менять исходный объект
        normalized = dict(data)

        # Забираем список вопросов. Если его нет, используем пустой список.
        questions = normalized.get("questions", [])

        # Нормализуем только те элементы, которые действительно являются dict.
        # Это защищает от случаев, когда модель вернула мусор в списке questions.
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
        """
        Принудительно выставляет одну сложность всем вопросам викторины.

        Это нужно, чтобы итоговая сложность вопросов точно совпадала
        со сложностью, которую выбрал пользователь.

        Например, если учитель выбрал "medium", но модель вернула часть вопросов
        как "easy", этот метод перезапишет difficulty у всех вопросов на "medium".

        Args:
            result: сгенерированная викторина.
            difficulty: выбранная сложность в строковом виде.

        Returns:
            Обновлённая викторина с единой сложностью у всех вопросов.
        """

        difficulty_enum = DifficultyLevel(difficulty)

        # Pydantic-модели обычно иммутабельны или их лучше не менять напрямую,
        # поэтому создаём копии вопросов с обновлённым difficulty.
        updated_questions = [
            question.model_copy(update={"difficulty": difficulty_enum})
            for question in result.questions
        ]

        # Возвращаем копию результата с обновлённым списком вопросов
        return result.model_copy(update={"questions": updated_questions})

    def generate_quiz(self, payload: GenerateQuizRequest) -> GenerateQuizResponse:
        """
        Генерирует викторину на основе пользовательского запроса.

        Этот метод используется, когда учитель передаёт параметры викторины:
        предмет, класс, тему, количество вопросов, типы вопросов, сложность
        и, опционально, исходный текст.

        Общий алгоритм:
        1. Логируем начало генерации.
        2. Очищаем source_text от технических заглушек.
        3. Если учитель передал текст вручную, создаём SourceFragment.
        4. Собираем контекст для модели.
        5. Строим промпт.
        6. Отправляем запрос в GigaChat.
        7. Извлекаем JSON из ответа.
        8. Нормализуем данные.
        9. Валидируем через GenerateQuizResponse.
        10. Возвращаем готовую викторину.

        Args:
            payload: запрос на генерацию викторины.

        Returns:
            Сгенерированная викторина в формате GenerateQuizResponse.

        Raises:
            Exception: если модель вернула невалидный JSON или данные не прошли валидацию.
        """

        logger.info(
            f"START generate_quiz | subject={payload.subject} | grade={payload.grade} | "
            f"topic={payload.topic} | question_count={payload.question_count} | "
            f"question_types={payload.question_types} | difficulty={payload.difficulty} | "
            f"source_text_len={len(payload.source_text) if payload.source_text else 0}"
        )

        # Список фрагментов, полученных из ручного текста учителя.
        # Пока здесь максимум один фрагмент.
        manual_fragments = []

        # Очищаем исходный текст от пробелов и None.
        cleaned_source_text = (payload.source_text or "").strip()

        # Swagger/OpenAPI или фронтенд иногда могут отправлять технические заглушки.
        # Такие значения не должны восприниматься как реальный учебный текст.
        if cleaned_source_text.lower() in {"string", "source_text", "null", "none"}:
            cleaned_source_text = ""

        # Если учитель действительно передал текст, превращаем его в SourceFragment.
        # Это позволяет дальше работать с ручным текстом так же, как с фрагментами документов.
        if cleaned_source_text:
            manual_fragments = [
                SourceFragment(
                    fragment_id="manual_1",
                    source_type="manual_text",
                    source_name="teacher_input",
                    text=cleaned_source_text
                )
            ]

        # Собираем общий контекст для модели из фрагментов.
        # max_chars ограничивает размер контекста, чтобы не перегрузить промпт.
        combined_context = material_service.build_combined_context(
            manual_fragments,
            max_chars=4000
        )

        # Формируем промпт, в котором описываем модели:
        # какую викторину нужно создать и какой JSON она должна вернуть.
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

        # Отправляем запрос в GigaChat.
        # system-сообщение жёстко просит модель вернуть только валидный JSON.
        raw = gigachat_service.chat(
            messages=[
                {"role": "system", "content": "Ты возвращаешь только валидный JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        # Логируем первые 2000 символов ответа для отладки.
        # Полный ответ лучше не логировать, если он может быть большим.
        logger.info(f"RAW_MODEL_RESPONSE: {raw[:2000]}")

        try:
            # Парсим JSON из ответа модели
            data = self._extract_json(raw)

            # Нормализуем поля, которые модель могла назвать по-разному
            data = self._normalize_quiz_response_data(data, payload.difficulty.value)

            # Валидируем данные через Pydantic-схему ответа
            result = GenerateQuizResponse(**data)

            # Пока метод ничего не меняет, но в будущем может связать вопросы с фрагментами
            result = self._enrich_questions_with_source_fragments(
                result,
                manual_fragments
            )

            # Принудительно выставляем выбранную сложность всем вопросам
            result = self._apply_difficulty_to_all_questions(
                result,
                payload.difficulty.value
            )

            logger.info(
                f"SUCCESS generate_quiz | title={result.quiz_title} | questions_count={len(result.questions)}"
            )

            return result

        except Exception as e:
            # Если модель вернула невалидный JSON или данные не прошли валидацию,
            # логируем ошибку и часть сырого ответа для диагностики.
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
        """
        Генерирует викторину на основе готовых фрагментов материалов.

        Этот метод подходит для сценария, когда материалы уже были загружены,
        распарсены и разбиты на SourceFragment.

        Например:
        - учитель загрузил PDF;
        - система извлекла из него текст;
        - текст был разбит на фрагменты;
        - выбранные фрагменты передаются в этот метод для генерации вопросов.

        Отличие от generate_quiz:
        - generate_quiz работает в основном с ручным source_text из payload;
        - generate_quiz_from_fragments работает с уже подготовленными фрагментами.

        Args:
            subject: предмет, например "История".
            grade: класс, например "7".
            topic: тема викторины.
            question_count: количество вопросов.
            question_types: список типов вопросов.
            difficulty: сложность: "easy", "medium" или "hard".
            fragments: фрагменты учебного материала.

        Returns:
            Сгенерированная викторина в формате GenerateQuizResponse.

        Raises:
            Exception: если модель вернула невалидный JSON или данные не прошли валидацию.
        """

        logger.info(
            f"START generate_quiz_from_fragments | subject={subject} | grade={grade} | "
            f"topic={topic} | question_count={question_count} | difficulty={difficulty} | "
            f"fragments_count={len(fragments)}"
        )

        # Собираем единый текстовый контекст из переданных фрагментов.
        # Для фрагментов лимит чуть больше, потому что обычно они уже отобраны
        # как релевантные куски материала.
        combined_context = material_service.build_combined_context(
            fragments,
            max_chars=6000
        )

        # Собираем промпт для генерации викторины.
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

        # Отправляем промпт в GigaChat и просим вернуть только валидный JSON.
        raw = gigachat_service.chat(
            messages=[
                {"role": "system", "content": "Ты возвращаешь только валидный JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        # Логируем часть ответа модели для отладки.
        logger.info(f"RAW_MODEL_RESPONSE_FROM_FRAGMENTS: {raw[:2000]}")

        try:
            # Извлекаем JSON из ответа модели
            data = self._extract_json(raw)

            # Нормализуем формат ответа модели
            data = self._normalize_quiz_response_data(data, difficulty)

            # Валидируем и превращаем dict в Pydantic-модель
            result = GenerateQuizResponse(**data)

            # В будущем здесь можно добавить реальные source_fragment_id/source_fragment_text
            result = self._enrich_questions_with_source_fragments(result, fragments)

            # Принудительно выставляем выбранную сложность всем вопросам
            result = self._apply_difficulty_to_all_questions(result, difficulty)

            logger.info(
                f"SUCCESS generate_quiz_from_fragments | title={result.quiz_title} | questions_count={len(result.questions)}"
            )

            return result

        except Exception as e:
            # Логируем ошибку парсинга/валидации и часть сырого ответа модели.
            logger.error(f"JSON_PARSE_ERROR_FROM_FRAGMENTS: {str(e)}")
            logger.error(f"BROKEN_RAW_RESPONSE_FROM_FRAGMENTS: {raw[:2000]}")
            raise

    def fix_quiz_questions(
            self,
            quiz: GenerateQuizResponse,
            issues: list[QuestionIssue],
            fragments: list[SourceFragment],
            subject: str,
            grade: str,
            topic: str,
            difficulty: str,
    ) -> GenerateQuizResponse:
        """
        Точечно чинит проблемные вопросы в викторине.

        Берёт только те вопросы, у которых есть critical/warning issues,
        отправляет их в LLM с подробным описанием проблем, получает
        исправленные версии и сшивает обратно в исходную викторину.

        Args:
            quiz: исходная викторина с проблемами.
            issues: список всех найденных проблем.
            fragments: исходные фрагменты материала.
            subject, grade, topic, difficulty: параметры исходного запроса.

        Returns:
            Новая викторина с исправленными вопросами на тех же позициях.
            Если что-то пошло не так — возвращает исходную викторину.
        """
        # 1. Группируем проблемы по индексу вопроса
        issues_by_idx: dict[int, list[QuestionIssue]] = {}
        for issue in issues:
            # Чиним только critical и warning, info — игнорируем
            if issue.severity in ("critical", "warning"):
                issues_by_idx.setdefault(issue.question_index, []).append(issue)

        if not issues_by_idx:
            logger.info("FIX_QUIZ | nothing to fix (only info-level issues)")
            return quiz

        # 2. Собираем проблемные вопросы для отправки в LLM
        problematic = []
        for idx, idx_issues in issues_by_idx.items():
            if idx < 0 or idx >= len(quiz.questions):
                logger.warning(f"FIX_QUIZ | invalid question_index={idx}, skipping")
                continue
            problematic.append({
                "original_index": idx,
                "question": quiz.questions[idx].model_dump(),
                "issues": [iss.model_dump() for iss in idx_issues],
            })

        if not problematic:
            return quiz

        logger.info(f"FIX_QUIZ | sending {len(problematic)} problematic questions to LLM")

        # 3. Строим промпт и зовём LLM
        prompt = build_quiz_fix_prompt(
            problematic_questions=problematic,
            fragments=fragments,
            subject=subject,
            grade=grade,
            topic=topic,
            difficulty=difficulty,
        )

        raw = gigachat_service.chat(
            messages=[
                {"role": "system",
                 "content": "Ты — методист, исправляющий ошибки в школьных викторинах. Возвращай только валидный JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # низкая, чтобы не «творил» новые ошибки
        )

        logger.info(f"RAW_FIX_RESPONSE: {raw[:2000]}")

        # 4. Парсим ответ
        try:
            data = self._extract_json(raw)
            fixed_questions = data.get("fixed_questions", [])
        except Exception as exc:
            logger.error(f"FIX_QUIZ_PARSE_FAILED: {exc}")
            return quiz  # graceful fallback — отдаём исходную

        # 5. Сшиваем: берём исходную викторину и заменяем починенные вопросы
        new_questions = list(quiz.questions)  # копия
        fixed_count = 0
        for item in fixed_questions:
            idx = item.get("original_index")
            q_data = item.get("question")
            if idx is None or q_data is None:
                continue
            if idx < 0 or idx >= len(new_questions):
                logger.warning(f"FIX_QUIZ | bad original_index from LLM: {idx}")
                continue
            try:
                new_questions[idx] = QuizQuestion(**q_data)
                fixed_count += 1
            except Exception as exc:
                logger.warning(f"FIX_QUIZ | failed to parse fixed question at idx={idx}: {exc}")

        logger.info(f"FIX_QUIZ | applied {fixed_count} fixes out of {len(problematic)} requested")

        return GenerateQuizResponse(
            quiz_title=quiz.quiz_title,
            subject=quiz.subject,
            grade=quiz.grade,
            topic=quiz.topic,
            questions=new_questions,
        )


# Глобальный экземпляр сервиса.
# Его можно импортировать в роутерах или других сервисах:
# from app.services.quiz_service import quiz_service
quiz_service = QuizService()