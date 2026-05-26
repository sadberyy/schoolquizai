"""Единый источник истины по структурным правилам викторины."""

# Количество вариантов ответа для каждого типа вопроса
OPTIONS_COUNT_BY_TYPE: dict[str, int] = {
    "single_choice": 4,
    "multiple_choice": 5,
    "true_false": 2,
}

# Количество правильных ответов для каждого типа вопроса
CORRECT_ANSWERS_COUNT_BY_TYPE: dict[str, int] = {
    "single_choice": 1,
    "multiple_choice": 2,
    "true_false": 1,
}

# Фиксированные варианты для true_false
TRUE_FALSE_OPTIONS: list[str] = ["Верно", "Неверно"]