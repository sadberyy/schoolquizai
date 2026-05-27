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
