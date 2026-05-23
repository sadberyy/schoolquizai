export const DIFFICULTIES = ["Легко", "Средне", "Сложно"] as const

export type Difficulty = (typeof DIFFICULTIES)[number]
export type QuestionType = "single" | "multiple" | "trueFalse"

export interface QuizAnswerOption {
  id: string
  text: string
  isCorrect: boolean
  points: number
}

export interface QuizQuestion {
  id: string
  type: QuestionType
  text: string
  source: string
  options: QuizAnswerOption[]
  explanation: string
}

export interface QuizData {
  id?: string
  title: string
  difficulty: Difficulty
  attempts: number
  timerPerQuestion: number
  totalTimer: number
  maxScore: number
  questions: QuizQuestion[]
}
