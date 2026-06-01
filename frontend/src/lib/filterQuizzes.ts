import type { QuizListItem } from "@/lib/api"

export function normalizeSearchQuery(query: string): string {
  return query.trim().toLowerCase().replace(/\s+/g, " ")
}

function quizSearchableText(
  quiz: QuizListItem,
  folderName?: string
): string {
  const parts = [quiz.title, quiz.subject, quiz.grade, folderName].filter(
    (p): p is string => typeof p === "string" && p.trim().length > 0
  )
  return parts.join(" ").toLowerCase()
}

export function filterQuizzes<T extends QuizListItem>(
  quizzes: T[],
  query: string,
  getFolderName?: (quiz: T) => string | undefined
): T[] {
  const normalized = normalizeSearchQuery(query)
  if (!normalized) return quizzes
  return quizzes.filter((quiz) =>
    quizSearchableText(quiz, getFolderName?.(quiz)).includes(normalized)
  )
}
