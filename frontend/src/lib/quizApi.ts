import type { QuestionType, QuizQuestion } from "@/types/quiz"
import { authFetch } from "@/lib/auth"
import { API_BASE_URL } from "@/lib/api"


export async function readApiError(
  response: Response,
  fallback: string
): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    if (body.detail) return body.detail
  } catch {
    // ignore
  }
  return `${fallback}: ${response.status}`
}

export function mapQuestionTypeBackendToFrontend(type: string): QuestionType {
  if (type === "single_choice") return "single"
  if (type === "multiple_choice") return "multiple"
  if (type === "true_false") return "trueFalse"
  return "single"
}

export interface ApiStudentQuestion {
  id: string
  question_text: string
  question_type: string
  answers: unknown
  points?: number
  order_idx?: number
  has_image?: boolean
}

  export function mapStudentQuestionsFromApi(
    items: ApiStudentQuestion[],
    quizId: string
  ): { questions: QuizQuestion[]; maxScore: number } {
    const sorted = [...items].sort(
      (a, b) => (Number(a.order_idx) || 0) - (Number(b.order_idx) || 0)
    )

    let maxScore = 0
    const questions: QuizQuestion[] = sorted.map((q) => {
      const points = Number(q.points) || 0
      maxScore += points

      const answerList = Array.isArray(q.answers)
        ? q.answers.filter((x): x is string => typeof x === "string")
        : []

      const type = mapQuestionTypeBackendToFrontend(q.question_type)

      const hasImage = Boolean(q.has_image)

      return {
        id: String(q.id),
        type,
        text: q.question_text ?? "",
        source: "",
        explanation: "",
        options: answerList.map((text, idx) => ({
          id: `opt-${q.id}-${idx}`,
          text,
          isCorrect: false,
          points: 0,
        })),
        hasImage,
        imageUrl: hasImage
        ? getQuestionImageUrl(String(quizId), String(q.id))
        : null,
      }
    })

    return { questions, maxScore }
  }

export function buildStudentAnswerPayload(
  question: QuizQuestion,
  selectedOptionIds: string[]
): string | string[] {
  const texts = selectedOptionIds
    .map((id) => question.options.find((o) => o.id === id)?.text)
    .filter((t): t is string => Boolean(t))

  if (question.type === "multiple") {
    return texts
  }

  return texts[0] ?? ""
}

export interface ApiQuizMeta {
  quiz_id: string
  title?: string
  max_attempts?: number
  question_time_seconds?: number
  full_time_seconds?: number
}

export function mapQuizMetaFromApi(data: ApiQuizMeta) {
  const perQuestion = Math.max(0, Number(data.question_time_seconds) || 0)
  const fullSeconds = Math.max(0, Number(data.full_time_seconds) || 0)
  const timerMode: "per_question" | "total" | "none" =
    perQuestion > 0 ? "per_question" : fullSeconds > 0 ? "total" : "none"

  return {
    id: String(data.quiz_id),
    title: data.title ?? "Викторина",
    attempts: Math.max(1, Number(data.max_attempts) || 1),
    timerMode,
    timerPerQuestion: perQuestion,
    totalTimer: fullSeconds / 60,
  }
}

export interface ApiQuizResultRow {
  student_name: string
  score: number
  max_score?: number
  attempt_number: number
  duration_seconds?: number | null
}

export function mapResultsFromApi(rows: ApiQuizResultRow[]) {
  return rows.map((row, index) => ({
    id: `${row.student_name}-${row.attempt_number}-${index}`,
    firstName: row.student_name,
    lastName: "",
    fullName: row.student_name,
    score: Number(row.score) || 0,
    maxScore: Number(row.max_score) || 0,
    elapsedSeconds: Number(row.duration_seconds) || 0,
    attemptNumber: Number(row.attempt_number) || 1,
  }))
}

const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024 // 5 MB
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"] as const

export function validateImageFile(file: File): string | null {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type as (typeof ALLOWED_IMAGE_TYPES)[number])) {
    return "Поддерживаются только JPG, PNG и WebP"
  }
  if (file.size > MAX_IMAGE_SIZE_BYTES) {
    return "Размер изображения не должен превышать 5 MB"
  }
  return null
}

export function getQuestionImageUrl(quizId: string, questionId: string): string {
  return `${API_BASE_URL}/quiz/${quizId}/questions/${questionId}/image`
}


export function resolveImageSrc(imageUrl: string): string {
  if (/^https?:\/\//i.test(imageUrl)) return imageUrl
  // API_BASE_URL обычно вида "http://host/api" — статика лежит на корне домена.
  // Берём origin от API_BASE_URL.
  try {
    const origin = new URL(API_BASE_URL).origin
    return `${origin}${imageUrl.startsWith("/") ? "" : "/"}${imageUrl}`
  } catch {
    return imageUrl
  }
}

/**
 * Загружает изображение к вопросу.
 * Возвращает URL для отображения (GET-эндпоинт бэкенда).
 */
export async function uploadQuestionImage(params: {
  quizId: string
  questionId: string
  file: File
}): Promise<string> {
  const { quizId, questionId, file } = params

  const validationError = validateImageFile(file)
  if (validationError) {
    throw new Error(validationError)
  }

  const formData = new FormData()
  formData.append("file", file)

  const response = await authFetch(
    `${API_BASE_URL}/quiz/${quizId}/questions/${questionId}/image`,
    {
      method: "POST",
      body: formData,
    }
  )

  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка загрузки изображения"))
  }

  await response.json().catch(() => ({}))
  return getQuestionImageUrl(quizId, questionId)
}

/**
 * Удаляет изображение у вопроса.
 */
export async function deleteQuestionImage(params: {
  quizId: string
  questionId: string
}): Promise<void> {
  const { quizId, questionId } = params

  const response = await authFetch(
    `${API_BASE_URL}/quiz/${quizId}/questions/${questionId}/image`,
    { method: "DELETE" }
  )

  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка удаления изображения"))
  }
}