from app.schemas.material import SourceFragment
from app.schemas.quiz import GenerateQuizResponse
from app.core.quiz_rules import (
    OPTIONS_COUNT_BY_TYPE,
    CORRECT_ANSWERS_COUNT_BY_TYPE,
    TRUE_FALSE_OPTIONS,
)


def _build_type_rules_block() -> str:
    """
    Собирает текстовый блок правил по типам вопросов из quiz_rules.
    Используется и в build_quiz_prompt, и в build_quiz_validation_prompt,
    чтобы правила лежали в одном месте.
    """
    lines = []
    for q_type, opts_count in OPTIONS_COUNT_BY_TYPE.items():
        correct_count = CORRECT_ANSWERS_COUNT_BY_TYPE.get(q_type, 1)
        if q_type == "true_false":
            tf_str = str(TRUE_FALSE_OPTIONS).replace("'", '"')
            lines.append(
                f"- Для {q_type} варианты должны быть ровно: {tf_str}, "
                f"ровно {correct_count} правильный(ых) ответ(ов)."
            )
        else:
            lines.append(
                f"- Для {q_type} должно быть ровно {opts_count} вариантов "
                f"и ровно {correct_count} правильных ответа."
            )
    return "- \n".join(lines)


def build_quiz_prompt(
    subject: str,
    grade: str,
    topic: str,
    question_count: int,
    question_types: list,
    difficulty: str,
    combined_context: str,
    fragments: list[SourceFragment]
) -> str:
    if not fragments:
        return f"""
Ты — методист и автор школьных викторин.
Верни только валидный JSON, без markdown, без комментариев и пояснений.

Параметры:
- Предмет: {subject}
- Класс: {grade}
- Тема: {topic}
- Количество вопросов: {question_count}
- Типы вопросов: {", ".join(question_types)}
- Уровень сложности всех вопросов: {difficulty}

Нужно вернуть JSON строго такого вида:
{{
  "quiz_title": "string",
  "subject": "{subject}",
  "grade": "{grade}",
  "topic": "{topic}",
  "questions": [
    {{
      "type": "single_choice|multiple_choice|true_false",
      "text": "string",
      "options": ["string", "string"],
      "correct_answers": ["string"],
      "explanation": "string",
      "difficulty": "easy|medium|hard",
      "source_fragment_id": null
    }}
  ]
}}

Требования:
- Сгенерируй викторину по теме, предмету и классу.
- Можно использовать школьный контекст и общеизвестные факты по теме.
- Все вопросы должны быть строго одного уровня сложности: {difficulty}.
- Не смешивай easy, medium и hard в одном тесте.
- У каждого вопроса поле difficulty должно быть равно "{difficulty}".
- Если difficulty = easy, делай простые вопросы на базовые факты, термины, определения и узнавание.
- Если difficulty = medium, делай вопросы на понимание, сравнение, классификацию и простое применение знаний.
- Если difficulty = hard, делай вопросы на анализ, причинно-следственные связи, сопоставление и выводы.
{_build_type_rules_block()}
- Не пиши ничего вне JSON.
"""

    fragments_info = "\n".join(
        [f"- {fragment.fragment_id}: {fragment.source_name} ({fragment.source_type})" for fragment in fragments]
    )

    valid_fragment_ids = ", ".join([fragment.fragment_id for fragment in fragments])

    return f"""
Ты — методист и автор школьных викторин.
Верни только валидный JSON, без markdown, без комментариев и пояснений.

Параметры:
- Предмет: {subject}
- Класс: {grade}
- Тема: {topic}
- Количество вопросов: {question_count}
- Типы вопросов: {", ".join(question_types)}
- Уровень сложности всех вопросов: {difficulty}

Доступные фрагменты источника:
{fragments_info}

Допустимые source_fragment_id:
{valid_fragment_ids}

Объединенный контекст:
{combined_context}

Нужно вернуть JSON строго такого вида:
{{
  "quiz_title": "string",
  "subject": "{subject}",
  "grade": "{grade}",
  "topic": "{topic}",
  "questions": [
    {{
      "type": "single_choice|multiple_choice|true_false",
      "text": "string",
      "options": ["string", "string"],
      "correct_answers": ["string"],
      "explanation": "string",
      "difficulty": "easy|medium|hard",
      "source_fragment_id": "string"
    }}
  ]
}}

Строгие требования:
- Используй только информацию из переданных материалов и фрагментов.
- Не используй внешние знания, даже если тема тебе знакома.
- Не придумывай факты, термины, определения, цифры или детали, которых нет в переданных материалах.
- Каждый вопрос должен быть основан на одном конкретном фрагменте из списка.
- Для каждого вопроса обязательно укажи source_fragment_id.
- source_fragment_id должен быть только одним из допустимых значений из списка выше.
- explanation должен опираться только на тот же фрагмент, который указан в source_fragment_id.
- Все вопросы должны быть строго одного уровня сложности: {difficulty}.
- Не смешивай easy, medium и hard в одном тесте.
- У каждого вопроса поле difficulty должно быть равно "{difficulty}".
- Если difficulty = easy, делай простые вопросы на базовые факты, термины, определения и узнавание.
- Если difficulty = medium, делай вопросы на понимание, сравнение, классификацию и простое применение знаний.
- Если difficulty = hard, делай вопросы на анализ, причинно-следственные связи, сопоставление и выводы.
- Если в материалах недостаточно информации для сложного вопроса, не выдумывай детали; задай более простой по формулировке, но все равно в рамках выбранного уровня сложности и строго по тексту.
- Все математические формулы записывай в LaTeX-нотации внутри $...$ для строчных формул. Пример: "Функция плотности: $f(x) = \\frac{{1}}{{x\\sigma\\sqrt{{2\\pi}}}} e^{{-\\frac{{(\\ln x - \\mu)^2}}{{2\\sigma^2}}}}$". Не используй plain-text нотацию вида "(1/(xσ√(2π))) * exp(...)".
- Используй ключ строго "correct_answers", не "correct answers" и не "correctAnswers".
- Используй ключ строго "source_fragment_id", не "source fragment id" и не другие варианты.
- Для difficulty используй только одно из значений: "easy", "medium", "hard".
- Никогда не пиши "DifficultyLevel.easy", "DifficultyLevel.medium", "DifficultyLevel.hard".
- Верни только JSON-объект, который точно соответствует указанной схеме.

Правила по типам вопросов:
{_build_type_rules_block()}
- correct_answers должен содержать только варианты из options.
- Вопросы должны быть разнообразными и не дублировать друг друга.
- Формулировки должны быть понятными для школьника указанного класса.
- explanation должен быть кратким (желательно не более 150 символов).
- Баллы в итоговой викторине распределяются так, чтобы каждый correct_answer имел положительный score:
  - для single_choice (и true_false) должно быть ровно 1 correct_answer, и он должен получить > 0 баллов;
  - для multiple_choice должно быть ровно 2 correct_answer, и все correct_answer должны получить > 0 баллов.
  Если при таком распределении хотя бы один correct_answer получил бы 0 баллов — это ошибка (format_error, critical) и вопрос нужно исправить.

- В начале ответа напиши ровно [JSON_START] и сразу после него верни JSON.
- Сразу после JSON напиши ровно [JSON_END].
- Между [JSON_START] и [JSON_END] не должно быть ничего, кроме валидного JSON.
- Убедись, что все строки в JSON закрыты кавычками и дописаны.
- Не пиши ничего вне [JSON_START] и [JSON_END].
"""




def build_quiz_validation_prompt(
    quiz: GenerateQuizResponse,
    fragments: list[SourceFragment],
    subject: str,
    grade: str,
    topic: str,
    difficulty: str
) -> str:
    """
    Промпт для валидации (проверки) сгенерированной викторины.

    Args:
        quiz: сгенерированная викторина для проверки.
        fragments: исходные фрагменты материала (могут быть пустыми, если генерация была без источника).
        subject, grade, topic, difficulty: параметры исходного запроса.
    """

    # Сериализуем викторину для проверки. exclude_none=False — пусть валидатор видит null.
    quiz_json = quiz.model_dump_json(indent=2)

    # Готовим блок источников
    if fragments:
        sources_block = "\n\n".join(
            [f"[{fragment.fragment_id}] (источник: {fragment.source_name}, тип: {fragment.source_type})\n{fragment.text}"
             for fragment in fragments]
        )
        valid_ids = ", ".join([fragment.fragment_id for fragment in fragments])
        grounded_block = f"""
ИСТОЧНИКИ (это единственный источник истины — все факты должны браться только отсюда):

{sources_block}

Допустимые source_fragment_id: {valid_ids}
"""
    else:
        grounded_block = "ИСТОЧНИКИ: не предоставлены. Викторина строилась на общих знаниях по теме."

    # Дополнительные правила для grounded-режима
    grounded_rules = """
- Каждый факт в вопросе и в explanation должен подтверждаться текстом фрагмента, указанного в source_fragment_id.
- Если факт нельзя проверить по фрагменту — это категория "not_in_source".
- Если source_fragment_id не входит в список допустимых — это категория "format_error" (critical).
""" if fragments else """
- Раз источников нет, проверяй вопросы на соответствие общеизвестным школьным знаниям по предмету и теме.
- Категорию "not_in_source" не используй.
"""

    return f"""
Ты — строгий методист-эксперт. Твоя задача — проверить уже сгенерированную школьную викторину и найти в ней проблемы.

Параметры исходного запроса:
- Предмет: {subject}
- Класс: {grade}
- Тема: {topic}
- Заявленная сложность: {difficulty}

{grounded_block}

ВИКТОРИНА ДЛЯ ПРОВЕРКИ (JSON):
{quiz_json}

Для КАЖДОГО вопроса (нумерация с 0) проверь:
1. **factual_error** — фактическая ошибка по существу (неверное определение, цифра, факт).
2. **wrong_correct_answer** — в correct_answers указан не тот вариант, который реально является правильным.
3. **ambiguous** — формулировка вопроса двусмысленна, непонятна или допускает несколько трактовок.
4. **duplicate_options** — среди options есть дубликаты или почти идентичные варианты.
5. **options_count_mismatch** — нарушено количество вариантов:
{_build_type_rules_block()}
6. **difficulty_mismatch** — фактическая сложность вопроса явно не соответствует "{difficulty}".
7. **off_topic** — вопрос не относится к теме "{topic}" или предмету "{subject}".
8. **format_error** — correct_answers содержит значения, которых нет в options; или другая структурная проблема.
{grounded_rules}

Уровни критичности:
- **critical**: вопрос нельзя использовать без правки (factual_error, wrong_correct_answer, format_error, not_in_source).
- **warning**: вопрос можно использовать, но желательно поправить (ambiguous, duplicate_options, difficulty_mismatch).
- **info**: косметическое замечание (стилистика, длина explanation).

Оценка overall_score от 0 до 10:
- 10 — идеальная викторина, ни одного замечания;
- 7-9 — есть мелкие warning/info, но critical нет;
- 4-6 — есть один-два critical;
- 0-3 — много critical, викторину почти всю надо переделывать.

is_valid = true, если НЕТ ни одного critical-замечания.

Верни JSON строго такого вида:
{{
  "is_valid": true,
  "overall_score": 8.5,
  "issues": [
    {{
      "question_index": 0,
      "severity": "warning",
      "category": "ambiguous",
      "description": "Формулировка вопроса допускает две трактовки: ...",
      "suggested_fix": "Переформулировать как: ..."
    }}
  ],
  "summary": "Краткое резюме на русском (1-3 предложения)."
}}

Строгие требования к формату ответа:
- В начале ответа напиши ровно [JSON_START] и сразу после него верни JSON.
- Сразу после JSON напиши ровно [JSON_END].
- Между [JSON_START] и [JSON_END] не должно быть ничего, кроме валидного JSON.
- Не используй markdown, комментарии, пояснения вне JSON.
- Используй только указанные значения для severity и category.
- question_index — целое число, начиная с 0.
- Если проблем нет вообще — issues должен быть пустым массивом [], а is_valid = true, overall_score = 9.5-10.
- Не выдумывай проблемы там, где их нет. Лучше пропустить, чем добавить ложноположительное замечание.
"""


def build_quiz_fix_prompt(
    problematic_questions: list[dict],
    fragments: list[SourceFragment],
    subject: str,
    grade: str,
    topic: str,
    difficulty: str,
) -> str:
    """
    Промпт для точечной починки проблемных вопросов.

    Args:
        problematic_questions: список словарей вида:
            {
                "original_index": int,      # индекс в исходной викторине
                "question": dict,            # сам вопрос (QuizQuestion.model_dump())
                "issues": list[dict],        # его проблемы (QuestionIssue.model_dump())
            }
        fragments: исходные фрагменты (для grounded-режима).
        subject, grade, topic, difficulty: параметры исходного запроса.
    """
    import json as _json  # локальный импорт, чтобы не зависеть от глобального

    # Готовим блок источников
    if fragments:
        sources_block = "\n\n".join(
            [f"[{fragment.fragment_id}] (источник: {fragment.source_name}, тип: {fragment.source_type})\n{fragment.text}"
             for fragment in fragments]
        )
        valid_ids = ", ".join([fragment.fragment_id for fragment in fragments])
        sources_section = f"""
ИСТОЧНИКИ (только из них можно брать факты):

{sources_block}

Допустимые source_fragment_id: {valid_ids}
"""
    else:
        sources_section = "ИСТОЧНИКИ: не предоставлены. Используй общеизвестные школьные знания по теме."

    # Сериализуем проблемные вопросы и их issues
    problems_block = ""
    for item in problematic_questions:
        idx = item["original_index"]
        q_json = _json.dumps(item["question"], ensure_ascii=False, indent=2)
        issues_text = "\n".join(
            [f"  - [{iss['severity']}] {iss['category']}: {iss['description']}"
             + (f"\n    Подсказка: {iss['suggested_fix']}" if iss.get('suggested_fix') else "")
             for iss in item["issues"]]
        )
        problems_block += f"\n=== Вопрос #{idx} ===\nТекущая версия:\n{q_json}\n\nПроблемы:\n{issues_text}\n"
    
    if fragments:
        fragment_id_example = '"string"'
    else:
        fragment_id_example = "null"

    return f"""
Ты — методист и автор школьных викторин. Тебе дана викторина с проблемными вопросами и список этих проблем.
Твоя задача — переписать ТОЛЬКО проблемные вопросы, исправив все указанные проблемы, и вернуть исправленные версии в JSON.

Параметры исходного запроса:
- Предмет: {subject}
- Класс: {grade}
- Тема: {topic}
- Заявленная сложность: {difficulty}

{sources_section}

ПРОБЛЕМНЫЕ ВОПРОСЫ И ИХ ОШИБКИ:
{problems_block}

{_build_type_rules_block()}

Строгие требования к исправлению:
- Сохрани original_index для каждого вопроса — это его позиция в исходной викторине.
- Исправь ВСЕ перечисленные проблемы, особенно critical.
- Не добавляй новых проблем: проверь количество вариантов, корректность correct_answers, привязку к source_fragment_id.
- Все исправленные вопросы должны быть строго уровня сложности "{difficulty}".
- difficulty каждого вопроса должно быть равно "{difficulty}".
- correct_answers должен содержать только значения из options.
- Баллы в итоговой викторине распределяются так, чтобы каждый correct_answer имел положительный score:
  - для single_choice (и true_false) должно быть ровно 1 correct_answer, и он должен получить > 0 баллов;
  - для multiple_choice должно быть ровно 2 correct_answer, и все correct_answer должны получить > 0 баллов.
  Если при таком распределении хотя бы один correct_answer получил бы 0 баллов — это ошибка (format_error, critical) и вопрос нужно исправить.
{"- source_fragment_id должен быть из списка допустимых." if fragments else "- source_fragment_id оставь null."}
- Не используй внешние знания, если есть фрагменты — опирайся только на них.
- Все математические формулы записывай в LaTeX внутри $...$.
- Используй ключ строго "correct_answers", не "correct answers" и не "correctAnswers".
- Для difficulty используй только: "easy", "medium", "hard".

Верни JSON строго такого вида:
{{
  "fixed_questions": [
    {{
      "original_index": 0,
      "question": {{
        "type": "single_choice|multiple_choice|true_false",
        "text": "string",
        "options": ["string", "string"],
        "correct_answers": ["string"],
        "explanation": "string",
        "difficulty": "{difficulty}",
        "source_fragment_id": {fragment_id_example}
      }}
    }}
  ]
}}

Строгие требования к формату ответа:
- В начале ответа напиши ровно [JSON_START] и сразу после него верни JSON.
- Сразу после JSON напиши ровно [JSON_END].
- Между [JSON_START] и [JSON_END] не должно быть ничего, кроме валидного JSON.
- Не используй markdown, комментарии или пояснения вне JSON.
- В fixed_questions должно быть ровно столько элементов, сколько проблемных вопросов было передано.
- Каждый original_index должен совпадать с одним из переданных.
"""