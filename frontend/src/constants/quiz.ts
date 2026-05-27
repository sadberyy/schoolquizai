import type { QuestionType } from "@/types/quiz"

export const QUESTION_TYPE_HINTS: Record<QuestionType, string> = {
  single: "Одиночный выбор",
  multiple: "Множественный выбор",
  trueFalse: "True/False",
}
