from app.schemas.material import SourceFragment


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
- Для single_choice должно быть ровно 4 варианта и 1 правильный ответ.
- Для multiple_choice должно быть ровно 5 вариантов и 2 правильных ответа.
- Для true_false варианты должны быть ровно: ["Верно", "Неверно"].
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
- Для single_choice должно быть ровно 4 варианта и ровно 1 правильный ответ.
- Для multiple_choice должно быть ровно 5 вариантов и ровно 2 правильных ответа.
- Для true_false варианты должны быть ровно: ["Верно", "Неверно"].
- correct_answers должен содержать только варианты из options.
- Вопросы должны быть разнообразными и не дублировать друг друга.
- Формулировки должны быть понятными для школьника указанного класса.
- explanation должен быть кратким (желательно не более 150 символов).

- В начале ответа напиши ровно [JSON_START] и сразу после него верни JSON.
- Сразу после JSON напиши ровно [JSON_END].
- Между [JSON_START] и [JSON_END] не должно быть ничего, кроме валидного JSON.
- Убедись, что все строки в JSON закрыты кавычками и дописаны.
- Не пиши ничего вне [JSON_START] и [JSON_END].
"""