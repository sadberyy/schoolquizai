"""
Сервис валидации (проверки) уже сгенерированных викторин.

Архитектура:
1. Дешёвые структурные проверки (count of options, correct_answers ⊆ options, валидные source_fragment_id)
   выполняются в коде — без вызова LLM.
2. Семантические проверки (фактические ошибки, привязка к источникам, двусмысленность)
   выполняются второй прогонкой LLM с другим промптом (LLM-as-a-judge).
3. Результаты обоих этапов объединяются в единый QuizValidationReport.
"""

from app.schemas.quiz import (
    GenerateQuizResponse,
    QuizQuestion,
    QuizValidationReport,
    QuestionIssue,
)
from app.schemas.material import SourceFragment
from app.services.gigachat_service import gigachat_service
from app.services.prompt_service import build_quiz_validation_prompt
from app.services.quiz_service import quiz_service  # для повторного использования _extract_json
from app.core.logger import logger
from app.core.quiz_rules import (
    OPTIONS_COUNT_BY_TYPE,
    CORRECT_ANSWERS_COUNT_BY_TYPE,
    TRUE_FALSE_OPTIONS,
)


class QuizValidationService:
    """Сервис проверки сгенерированной викторины на качество."""

    def _structural_check(
        self,
        quiz: GenerateQuizResponse,
        fragments: list[SourceFragment],
    ) -> list[QuestionIssue]:
        """
        Структурные проверки без LLM.

        Это дешёвый, быстрый и детерминированный фильтр, который ловит
        явные ошибки модели (неправильное количество опций, битые ссылки и т.п.).
        """
        issues: list[QuestionIssue] = []
        valid_fragment_ids = {fragment.fragment_id for fragment in fragments}

        for idx, question in enumerate(quiz.questions):
            issues.extend(self._check_options_count(idx, question))
            issues.extend(self._check_correct_answers(idx, question))
            issues.extend(self._check_duplicate_options(idx, question))
            issues.extend(self._check_fragment_id(idx, question, valid_fragment_ids, has_fragments=bool(fragments)))

        return issues

    def _check_options_count(self, idx: int, question: QuizQuestion) -> list[QuestionIssue]:
        """Проверка количества options и correct_answers по типу вопроса."""
        issues = []
        expected_opts = OPTIONS_COUNT_BY_TYPE.get(question.type)
        expected_correct = CORRECT_ANSWERS_COUNT_BY_TYPE.get(question.type)

        if expected_opts is not None and len(question.options) != expected_opts:
            issues.append(QuestionIssue(
                question_index=idx,
                severity="critical",
                category="options_count_mismatch",
                description=f"Тип '{question.type}' требует {expected_opts} вариантов, а получено {len(question.options)}.",
                suggested_fix=f"Сделать ровно {expected_opts} вариантов ответа.",
            ))

        if expected_correct is not None and len(question.correct_answers) != expected_correct:
            issues.append(QuestionIssue(
                question_index=idx,
                severity="critical",
                category="options_count_mismatch",
                description=f"Тип '{question.type}' требует {expected_correct} правильных ответов, а получено {len(question.correct_answers)}.",
                suggested_fix=f"Указать ровно {expected_correct} правильных ответов.",
            ))

        # Доп. проверка true_false
        if question.type == "true_false" and set(question.options) != set(TRUE_FALSE_OPTIONS):
            issues.append(QuestionIssue(
                question_index=idx,
                severity="critical",
                category="format_error",
                description=f"Для true_false варианты должны быть ровно {TRUE_FALSE_OPTIONS}.",
                suggested_fix=f"Заменить варианты на {TRUE_FALSE_OPTIONS}.",
            ))

        return issues

    def _check_correct_answers(self, idx: int, question: QuizQuestion) -> list[QuestionIssue]:
        """Проверка, что все correct_answers есть в options."""
        issues = []
        options_set = set(question.options)
        for answer in question.correct_answers:
            if answer not in options_set:
                issues.append(QuestionIssue(
                    question_index=idx,
                    severity="critical",
                    category="format_error",
                    description=f"Правильный ответ '{answer}' отсутствует в списке options.",
                    suggested_fix="Привести correct_answers в соответствие с options.",
                ))
        return issues

    def _check_duplicate_options(self, idx: int, question: QuizQuestion) -> list[QuestionIssue]:
        """Проверка дублей в options (точное совпадение)."""
        if len(question.options) != len(set(question.options)):
            return [QuestionIssue(
                question_index=idx,
                severity="warning",
                category="duplicate_options",
                description="В options есть дублирующиеся варианты ответа.",
                suggested_fix="Заменить дубли на уникальные варианты.",
            )]
        return []

    def _check_fragment_id(
        self,
        idx: int,
        question: QuizQuestion,
        valid_ids: set[str],
        has_fragments: bool,
    ) -> list[QuestionIssue]:
        """Проверка корректности source_fragment_id."""
        # Если фрагментов нет — source_fragment_id может быть None, это норма
        if not has_fragments:
            return []

        if not question.source_fragment_id:
            return [QuestionIssue(
                question_index=idx,
                severity="critical",
                category="format_error",
                description="Не указан source_fragment_id, хотя викторина строится на материалах.",
                suggested_fix="Указать корректный source_fragment_id из списка допустимых.",
            )]

        if question.source_fragment_id not in valid_ids:
            return [QuestionIssue(
                question_index=idx,
                severity="critical",
                category="format_error",
                description=f"source_fragment_id='{question.source_fragment_id}' не входит в список допустимых.",
                suggested_fix=f"Использовать один из: {', '.join(sorted(valid_ids))}.",
            )]

        return []

    def _semantic_check(
        self,
        quiz: GenerateQuizResponse,
        fragments: list[SourceFragment],
        subject: str,
        grade: str,
        topic: str,
        difficulty: str,
    ) -> QuizValidationReport:
        """
        Семантическая проверка через LLM.
        """
        prompt = build_quiz_validation_prompt(
            quiz=quiz,
            fragments=fragments,
            subject=subject,
            grade=grade,
            topic=topic,
            difficulty=difficulty
        )

        raw = gigachat_service.chat(
            messages=[
                {"role": "system", "content": "Ты — строгий методист-эксперт. Возвращай только валидный JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,  # Низкая температура: судья должен быть стабильным и детерминированным
        )

        logger.info(f"RAW_VALIDATION_RESPONSE: {raw[:2000]}")

        # Переиспользуем чистильщик JSON из quiz_service
        data = quiz_service._extract_json(raw)
        return QuizValidationReport(**data)

    def _merge_reports(
        self,
        structural_issues: list[QuestionIssue],
        semantic_report: QuizValidationReport
    ) -> QuizValidationReport:
        """
        Объединяет структурные проблемы и семантический отчёт в единый отчёт.

        Логика overall_score после объединения:
        - если есть structural critical — score не выше 5;
        - если есть structural warning — score не выше 8;
        - иначе берём оценку семантического судьи.
        """
        all_issues = structural_issues + semantic_report.issues

        has_critical = any(i.severity == "critical" for i in all_issues)

        score = semantic_report.overall_score
        if any(i.severity == "critical" for i in structural_issues):
            score = min(score, 5.0)
        elif any(i.severity == "warning" for i in structural_issues):
            score = min(score, 8.0)

        # Если структурных проблем не было — берём summary судьи как есть.
        # Иначе обогащаем его упоминанием структурных проблем.
        summary = semantic_report.summary
        if structural_issues:
            summary = (
                f"Структурных проблем: {len(structural_issues)}. "
                f"Семантический разбор: {semantic_report.summary}"
            )

        return QuizValidationReport(
            is_valid=not has_critical,
            overall_score=round(score, 2),
            issues=all_issues,
            summary=summary,
        )

    def validate(
        self,
        quiz: GenerateQuizResponse,
        fragments: list[SourceFragment],
        subject: str,
        grade: str,
        topic: str,
        difficulty: str,
    ) -> QuizValidationReport:
        """
        Полная валидация викторины: структурная + семантическая.

        Args:
            quiz: сгенерированная викторина.
            fragments: исходные фрагменты (могут быть пустыми, если генерация была без источника).
            subject, grade, topic, difficulty: параметры исходного запроса.

        Returns:
            Единый отчёт о проверке.

        Raises:
            Exception: если LLM-судья вернул невалидный JSON.
        """
        logger.info(
            f"START validate_quiz | title={quiz.quiz_title} | questions={len(quiz.questions)} | "
            f"fragments={len(fragments)} | difficulty={difficulty}"
        )

        # 1. Дешёвые структурные проверки в коде
        structural_issues = self._structural_check(quiz, fragments)
        logger.info(f"STRUCTURAL_CHECK | issues_count={len(structural_issues)}")

        # 2. Семантическая проверка через LLM
        try:
            semantic_report = self._semantic_check(
                quiz=quiz,
                fragments=fragments,
                subject=subject,
                grade=grade,
                topic=topic,
                difficulty=difficulty,
            )
        except Exception as exc:
            # Если судья сломался — не валим весь процесс.
            # Возвращаем отчёт только со структурными проблемами и пометкой в summary.
            logger.error(f"SEMANTIC_CHECK_FAILED: {exc}")
            return QuizValidationReport(
                is_valid=not any(i.severity == "critical" for i in structural_issues),
                overall_score=5.0 if structural_issues else 7.0,
                issues=structural_issues,
                summary=(
                    "Семантическая проверка через LLM не удалась. "
                    "Отчёт содержит только результаты структурных проверок."
                ),
            )

        # 3. Объединяем
        final_report = self._merge_reports(
            structural_issues=structural_issues,
            semantic_report=semantic_report
        )

        logger.info(
            f"SUCCESS validate_quiz | is_valid={final_report.is_valid} | "
            f"score={final_report.overall_score} | total_issues={len(final_report.issues)} | "
            f"critical={final_report.critical_count}"
        )
        return final_report

    def validate_and_fix(
            self,
            quiz: GenerateQuizResponse,
            fragments: list[SourceFragment],
            subject: str,
            grade: str,
            topic: str,
            difficulty: str,
            auto_fix: bool = True,
    ) -> tuple[GenerateQuizResponse, QuizValidationReport, QuizValidationReport | None]:
        """
        Полный пайплайн: валидация → (опционально) исправление → повторная валидация.

        Args:
            quiz: сгенерированная викторина.
            fragments: исходные фрагменты.
            subject, grade, topic, difficulty: параметры исходного запроса.
            auto_fix: если True — пытается починить critical/warning issues.

        Returns:
            Кортеж (итоговая_викторина, отчёт_до_фикса, отчёт_после_фикса_или_None).
        """
        # Ленивый импорт, чтобы избежать кольцевых зависимостей
        from app.services.quiz_service import quiz_service

        # 1. Первая валидация
        report_before = self.validate(
            quiz=quiz,
            fragments=fragments,
            subject=subject,
            grade=grade,
            topic=topic,
            difficulty=difficulty,
        )

        # 2. Решаем, нужен ли фикс
        needs_fix = auto_fix and any(
            iss.severity in ("critical", "warning") for iss in report_before.issues
        )

        if not needs_fix:
            logger.info(
                f"VALIDATE_AND_FIX | no fix needed | auto_fix={auto_fix} | "
                f"is_valid={report_before.is_valid} | score={report_before.overall_score}"
            )
            return quiz, report_before, None

        logger.info(
            f"VALIDATE_AND_FIX | starting fix | issues_to_fix="
            f"{sum(1 for i in report_before.issues if i.severity in ('critical', 'warning'))}"
        )

        # 3. Чиним
        try:
            fixed_quiz = quiz_service.fix_quiz_questions(
                quiz=quiz,
                issues=report_before.issues,
                fragments=fragments,
                subject=subject,
                grade=grade,
                topic=topic,
                difficulty=difficulty,
            )
        except Exception as exc:
            logger.error(f"FIX_FAILED: {exc}")
            return quiz, report_before, None

        # 4. Повторная валидация — убеждаемся, что стало лучше (или хотя бы не хуже)
        try:
            report_after = self.validate(
                quiz=fixed_quiz,
                fragments=fragments,
                subject=subject,
                grade=grade,
                topic=topic,
                difficulty=difficulty,
            )
        except Exception as exc:
            logger.error(f"RE_VALIDATION_FAILED: {exc}")
            # Если повторная валидация упала — отдаём fixed_quiz без отчёта
            return fixed_quiz, report_before, None

        # 5. Если после фикса стало ХУЖЕ — откатываемся к исходной версии
        if report_after.overall_score < report_before.overall_score:
            logger.warning(
                f"FIX_DEGRADED_QUALITY | before={report_before.overall_score} | "
                f"after={report_after.overall_score} | reverting to original"
            )
            return quiz, report_before, report_after

        logger.info(
            f"VALIDATE_AND_FIX | success | "
            f"score_before={report_before.overall_score} | "
            f"score_after={report_after.overall_score}"
        )
        return fixed_quiz, report_before, report_after


# Глобальный экземпляр
quiz_validation_service = QuizValidationService()