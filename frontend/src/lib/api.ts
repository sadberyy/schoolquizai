import { authFetch } from "@/lib/auth"
import { readApiError } from "@/lib/quizApi"

const rawApiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
export const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, "")

/** Базовый URL для публичной ссылки ученику: …/student/{quizId} */
export function getStudentQuizBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_STUDENT_URL?.trim()
  if (fromEnv) {
    return fromEnv.replace(/\/+$/, "")
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin.replace(/\/+$/, "")}/student`
  }
  return "http://localhost:5173/student"
}

export interface QuizFolder {
  id: string
  name: string
  quizzes_count?: number
  updated_at: string
}

export interface QuizListItem {
  id: string
  title: string
  folder_id?: string | null
  updated_at?: string
}

export interface UpdateQuizRequest {
  title?: string
  difficulty?: string
  full_time_seconds?: number
  question_time_seconds?: number
  max_attempts?: number
  status?: string
  folder_id?: string | null
}

function sortByUpdatedAtDesc<T extends { updated_at?: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0
    const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0
    return tb - ta
  })
}

export async function getFolders(): Promise<QuizFolder[]> {
  const response = await authFetch(`${API_BASE_URL}/quiz/folders`)
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка загрузки папок"))
  }
  const data = (await response.json()) as { folders?: QuizFolder[] }
  return sortByUpdatedAtDesc(data.folders ?? [])
}

export async function createFolder(name: string): Promise<QuizFolder> {
  const response = await authFetch(`${API_BASE_URL}/quiz/folders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name.trim() }),
  })
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка создания папки"))
  }
  const data = (await response.json()) as {
    folder_id: string
    name: string
  }
  return {
    id: data.folder_id,
    name: data.name,
    updated_at: new Date().toISOString(),
  }
}

export async function renameFolder(id: string, name: string): Promise<void> {
  const params = new URLSearchParams({ name: name.trim() })
  const response = await authFetch(
    `${API_BASE_URL}/quiz/folders/${encodeURIComponent(id)}?${params}`,
    { method: "PUT" }
  )
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка переименования папки"))
  }
}

export async function deleteFolder(id: string): Promise<void> {
  const response = await authFetch(
    `${API_BASE_URL}/quiz/folders/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  )
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка удаления папки"))
  }
}

export async function listQuizzesInFolder(
  folderId: string
): Promise<QuizListItem[]> {
  const params = new URLSearchParams({ folder_id: folderId })
  const response = await authFetch(`${API_BASE_URL}/quiz/list?${params}`)
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка загрузки викторин"))
  }
  const data = (await response.json()) as { quizzes?: QuizListItem[] }
  return sortByUpdatedAtDesc(data.quizzes ?? [])
}

export async function deleteQuiz(quizId: string): Promise<void> {
  const response = await authFetch(
    `${API_BASE_URL}/quiz/${encodeURIComponent(quizId)}`,
    { method: "DELETE" }
  )
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка удаления викторины"))
  }
}

export interface QuizResultRow {
  student_name: string
  score: number
  max_score?: number
  attempt_number?: number
  duration_seconds?: number | null
}

export async function getQuizResults(quizId: string): Promise<QuizResultRow[]> {
  const response = await authFetch(
    `${API_BASE_URL}/quiz/${encodeURIComponent(quizId)}/results`
  )
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка загрузки результатов"))
  }
  const data = (await response.json()) as { results?: QuizResultRow[] }
  return data.results ?? []
}

export interface HeatmapStudentCell {
  student_name: string
  is_correct: boolean
  answer?: unknown
  points_received?: number
}

export interface HeatmapQuestionRow {
  question_id: string
  question_text: string
  order_idx: number
  total_answers: number
  correct_answers: number
  success_rate: number
  students: HeatmapStudentCell[]
}

export interface QuizHeatmapData {
  quiz_id: string
  quiz_title: string
  students: { name: string }[]
  questions: HeatmapQuestionRow[]
}

export async function getQuizHeatmap(quizId: string): Promise<QuizHeatmapData> {
  const response = await authFetch(
    `${API_BASE_URL}/quiz/${encodeURIComponent(quizId)}/heatmap`
  )
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка загрузки тепловой карты"))
  }
  return (await response.json()) as QuizHeatmapData
}

export async function cloneQuiz(
  quizId: string,
  folderId?: string | null
): Promise<{ quiz_id: string; title?: string }> {
  const response = await authFetch(
    `${API_BASE_URL}/quiz/${encodeURIComponent(quizId)}/clone`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        folderId != null ? { folder_id: folderId } : {}
      ),
    }
  )
  if (!response.ok) {
    throw new Error(await readApiError(response, "Ошибка клонирования викторины"))
  }
  return (await response.json()) as { quiz_id: string; title?: string }
}
