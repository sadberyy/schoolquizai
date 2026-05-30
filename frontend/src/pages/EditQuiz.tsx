import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { Check, ChevronsUpDown, Download, Loader2, Plus, Trash2 } from "lucide-react"

import { MathPreview } from "@/components/MathText"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import {
  API_BASE_URL,
  createFolder,
  getFolders,
  getStudentQuizBaseUrl,
  type QuizFolder,
  type UpdateQuizRequest,
} from "@/lib/api"
import { resolveFolderBackUrl } from "@/lib/navigation"
import { authFetch, downloadAuthenticatedFile } from "@/lib/auth"
import { buildDownloadFilename } from "@/lib/downloadFilename"
import { readApiError } from "@/lib/quizApi"
import {
  DIFFICULTIES,
  type Difficulty,
  type QuestionType,
  type QuizAnswerOption,
  type QuizData,
  type QuizQuestion,
} from "@/types/quiz"

export type { QuizData } from "@/types/quiz"

export interface EditQuizProps {
  quizData?: QuizData
  onSave?: (data: QuizData) => void
  onPublish?: (data: QuizData) => void
}

const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  single: "Одиночный выбор",
  multiple: "Множественный выбор",
  trueFalse: "True/False",
}

const CARD_CLASS =
  "border-2 border-quiz-card-border bg-white/95 shadow-md ring-0"
const QUESTION_CARD_CLASS =
  "border-2 border-quiz-card-border bg-white shadow-sm ring-0"
const ACCENT_BUTTON_CLASS =
  "border-transparent bg-quiz-accent text-white hover:bg-quiz-accent/90"

let idCounter = 0
const genId = () => `id-${++idCounter}-${Date.now()}`

const createOption = (
  text = "",
  isCorrect = false,
  points = 1,
  id?: string
): QuizAnswerOption => ({
  id: id ?? genId(),
  text,
  isCorrect,
  points,
})

const createTrueFalseOptions = (): QuizAnswerOption[] => [
  createOption("Да", true, 1),
  createOption("Нет", false, 1),
]

const createDefaultOptions = (type: QuestionType): QuizAnswerOption[] => {
  if (type === "trueFalse") return createTrueFalseOptions()
  return [
    createOption("Вариант 1", true, 1),
    createOption("Вариант 2", false, 1),
    createOption("Вариант 3", false, 1),
    createOption("Вариант 4", false, 1),
  ]
}

const createNewQuestionOptions = (): QuizAnswerOption[] =>
  Array.from({ length: 5 }, (_, i) => createOption("", i === 0, 1))

const createNewQuestion = (): QuizQuestion => ({
  id: genId(),
  type: "single",
  text: "",
  source: "",
  explanation: "",
  options: createNewQuestionOptions(),
})

export const MOCK_QUIZ_DATA: QuizData = {
  id: "quiz-mock-001",
  title: "Викторина по биологии — Клетка",
  difficulty: "Средне",
  attempts: 3,
  timerMode: "per_question",
  timerPerQuestion: 60,
  totalTimer: 30,
  maxScore: 0,
  questions: [
    {
      id: "q1",
      type: "single",
      text: "Какая органелла отвечает за фотосинтез?",
      source: "Учебник, стр. 42",
      explanation: "Хлоропласты содержат хлорофилл.",
      options: [
        { id: "q1-o1", text: "Митохондрия", isCorrect: false, points: 0 },
        { id: "q1-o2", text: "Хлоропласт", isCorrect: true, points: 2 },
        { id: "q1-o3", text: "Ядро", isCorrect: false, points: 0 },
        { id: "q1-o4", text: "Рибосома", isCorrect: false, points: 0 },
      ],
    },
    {
      id: "q2",
      type: "multiple",
      text: "Какие из перечисленного являются органоидами клетки?",
      source: "Презентация, слайд 8",
      explanation: "Все перечисленные — клеточные органоиды.",
      options: [
        { id: "q2-o1", text: "Митохондрия", isCorrect: true, points: 1 },
        { id: "q2-o2", text: "Хлоропласт", isCorrect: true, points: 1 },
        { id: "q2-o3", text: "Клеточная стенка", isCorrect: true, points: 1 },
        { id: "q2-o4", text: "Плазма", isCorrect: false, points: 0 },
      ],
    },
    {
      id: "q3",
      type: "trueFalse",
      text: "ДНК содержится только в ядре клетки.",
      source: "Фрагмент / стр. 15",
      explanation: "ДНК также есть в митохондриях.",
      options: [
        { id: "q3-o1", text: "Да", isCorrect: false, points: 0 },
        { id: "q3-o2", text: "Нет", isCorrect: true, points: 1 },
      ],
    },
  ],
}

function normalizeQuestion(question: QuizQuestion): QuizQuestion {
  const type = question.type ?? "single"
  let options = question.options?.map((o) => ({
    id: o.id || genId(),
    text: o.text ?? "",
    isCorrect: Boolean(o.isCorrect),
    points: Number(o.points) || 0,
  })) ?? createDefaultOptions(type)

  if (type === "trueFalse") {
    const defs = createTrueFalseOptions()
    options = defs.map((def, i) => {
      const incoming = options[i]
      return {
        ...def,
        id: incoming?.id ?? def.id,
        // Важно для интеграции: backend может использовать другие строки
        // (например "Верно"/"Неверно"), поэтому сохраняем text из входных данных.
        text: incoming?.text ?? def.text,
        isCorrect: incoming?.isCorrect ?? def.isCorrect,
        points: incoming?.points ?? def.points,
      }
    })
  }

  if (type === "single" && !options.some((o) => o.isCorrect) && options.length > 0) {
    options[0].isCorrect = true
  }

  return {
    id: question.id || genId(),
    type,
    text: question.text ?? "",
    source: question.source ?? "",
    explanation: question.explanation ?? "",
    options,
  }
}

function normalizeQuizData(data: QuizData): QuizData {
  const questions = (data.questions ?? []).map(normalizeQuestion)
  const difficulty = DIFFICULTIES.includes(data.difficulty as Difficulty)
    ? data.difficulty
    : "Средне"
  const timerPerQuestion = Math.max(0, Number(data.timerPerQuestion) || 0)
  const totalTimer = Math.max(0, Number(data.totalTimer) || 0)
  const timerMode: TimerMode =
    data.timerMode ??
    (timerPerQuestion > 0 ? "per_question" : totalTimer > 0 ? "total" : "none")

  return {
    id: data.id,
    title: data.title ?? "",
    difficulty,
    attempts: Math.max(1, Number(data.attempts) || 1),
    timerMode,
    timerPerQuestion,
    totalTimer,
    maxScore: 0,
    questions: questions.length > 0 ? questions : MOCK_QUIZ_DATA.questions.map(normalizeQuestion),
  }
}

export function getQuestionMaxScore(question: QuizQuestion): number {
  const correctOptions = question.options.filter((o) => o.isCorrect)
  if (correctOptions.length === 0) return 0
  if (question.type === "multiple") {
    return correctOptions.reduce((sum, o) => sum + o.points, 0)
  }
  return Math.max(...correctOptions.map((o) => o.points))
}

export function getTotalMaxScore(questions: QuizQuestion[]): number {
  return questions.reduce((sum, q) => sum + getQuestionMaxScore(q), 0)
}

function buildQuizPayload(state: QuizData): QuizData {
  const maxScore = getTotalMaxScore(state.questions)
  return { ...state, maxScore }
}

const DIFFICULTY_API: Record<Difficulty, "easy" | "medium" | "hard"> = {
  Легко: "easy",
  Средне: "medium",
  Сложно: "hard",
}
type TimerMode = "per_question" | "total" | "none"
type ExportMode = "teacher" | "student"
type ExportFormat = "pdf" | "pptx" | "docx"

const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = {
  pdf: "PDF",
  pptx: "PPTX",
  docx: "DOCX",
}

function mapDifficultyBackendToFrontend(difficulty: string | null | undefined) {
  if (difficulty === "easy") return "Легко" as Difficulty
  if (difficulty === "medium") return "Средне" as Difficulty
  if (difficulty === "hard") return "Сложно" as Difficulty
  return "Средне" as Difficulty
}

function mapDifficultyFrontendToBackend(difficulty: Difficulty) {
  return DIFFICULTY_API[difficulty]
}

function mapQuestionTypeBackendToFrontend(type: string): QuestionType {
  if (type === "single_choice") return "single"
  if (type === "multiple_choice") return "multiple"
  if (type === "true_false") return "trueFalse"
  return "single"
}

function mapQuestionTypeFrontendToBackend(type: QuestionType) {
  if (type === "single") return "single_choice"
  if (type === "multiple") return "multiple_choice"
  return "true_false"
}

function computeQuestionPointsFromFrontend(question: QuizQuestion): number {
  const correctOptions = question.options.filter((o) => o.isCorrect)
  if (correctOptions.length === 0) return 0

  if (question.type === "multiple") {
    return correctOptions.reduce(
      (sum, o) => sum + (Number(o.points) || 0),
      0
    )
  }

  if (correctOptions.length === 1) {
    return Number(correctOptions[0].points) || 0
  }

  // На UI для single/trueFalse обычно один correct, но если это нарушено —
  // backend присваивает один Question.points всем правильным ответам.
  // Берём максимальный points, чтобы не занизить ожидаемую оценку.
  return Math.max(...correctOptions.map((o) => Number(o.points) || 0), 0)
}

function buildOptionsFromBackendAnswers(params: {
  answers: unknown
  correctAnswers: unknown
  questionType: QuestionType
  questionPoints: number
}): QuizAnswerOption[] {
  const answerList = Array.isArray(params.answers)
    ? params.answers.filter((x) => typeof x === "string")
    : []
  const correctList = Array.isArray(params.correctAnswers)
    ? params.correctAnswers.filter((x) => typeof x === "string")
    : []
  const correctSet = new Set(correctList)

  if (params.questionType === "multiple") {
    const correctCount = answerList.filter((a) => correctSet.has(a)).length
    if (correctCount <= 0) {
      return answerList.map((text, idx) => ({
        id: `opt-${idx}-${text}`,
        text,
        isCorrect: false,
        points: 0,
      }))
    }

    const base = Math.floor(params.questionPoints / correctCount)
    let remainder = params.questionPoints - base * correctCount

    return answerList.map((text, idx) => {
      const isCorrect = correctSet.has(text)
      const points =
        isCorrect
          ? base + (remainder > 0 ? 1 : 0)
          : 0

      if (isCorrect && remainder > 0) remainder -= 1

      return {
        id: `opt-${idx}-${text}`,
        text,
        isCorrect,
        points,
      }
    })
  }

  return answerList.map((text, idx) => ({
    id: `opt-${idx}-${text}`,
    text,
    isCorrect: correctSet.has(text),
    points: correctSet.has(text) ? params.questionPoints : 0,
  }))
}

export function backendQuizToQuizData(backendQuiz: any): QuizData {
  const mappedDifficulty = mapDifficultyBackendToFrontend(backendQuiz.difficulty)

  const questions: QuizQuestion[] = (backendQuiz.questions ?? []).map(
    (q: any) => {
      const type = mapQuestionTypeBackendToFrontend(q.question_type)
      const questionPoints = Number(q.points) || 0
      return {
        id: String(q.id),
        type,
        text: q.question_text ?? "",
        source: q.source_fragment ?? "",
        explanation: q.explanation ?? "",
        options: buildOptionsFromBackendAnswers({
          answers: q.answers,
          correctAnswers: q.correct_answers,
          questionType: type,
          questionPoints,
        }),
      }
    }
  )

  return {
    id: String(backendQuiz.quiz_id),
    folderId: backendQuiz.folder_id ?? null,
    title: backendQuiz.title ?? "",
    difficulty: mappedDifficulty,
    attempts: Math.max(1, Number(backendQuiz.max_attempts) || 1),
    timerMode:
      Math.max(0, Number(backendQuiz.question_time_seconds) || 0) > 0
        ? "per_question"
        : Math.max(0, Number(backendQuiz.full_time_seconds) || 0) > 0
          ? "total"
          : "none",
    timerPerQuestion: Math.max(0, Number(backendQuiz.question_time_seconds) || 0),
    totalTimer: Math.max(0, Number(backendQuiz.full_time_seconds) || 0) / 60,
    maxScore: 0,
    questions,
  }
}

function frontendQuestionToBackendCreatePayload(question: QuizQuestion) {
  const correctOptions = question.options.filter((o) => o.isCorrect)
  return {
    question_text: question.text,
    question_type: mapQuestionTypeFrontendToBackend(question.type),
    answers: question.options.map((o) => o.text),
    correct_answers: correctOptions.map((o) => o.text),
    explanation: question.explanation || "",
    source_fragment: question.source || "",
    points: computeQuestionPointsFromFrontend(question),
  }
}

function frontendQuestionToBackendUpdatePayload(
  question: QuizQuestion,
  orderIdx: number
) {
  return {
    ...frontendQuestionToBackendCreatePayload(question),
    order_idx: orderIdx,
  }
}

export default function EditQuiz({
  quizData,
  onSave,
  onPublish,
}: EditQuizProps) {
  const { quizId: routeQuizId } = useParams<{ quizId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const returnFolderId = searchParams.get("folder_id")

  const resolvedQuizId = routeQuizId

  const [quiz, setQuiz] = useState<QuizData>(() =>
    normalizeQuizData(quizData ?? MOCK_QUIZ_DATA)
  )

  const backendQuestionIdsRef = useRef<Set<string>>(new Set())

  const [isLoadingQuiz, setIsLoadingQuiz] = useState(!quizData)
  const [loadError, setLoadError] = useState("")
  const [isSavingQuiz, setIsSavingQuiz] = useState(false)
  const [pdfExportMode, setPdfExportMode] = useState<ExportMode>("teacher")
  const [pptxExportMode, setPptxExportMode] = useState<ExportMode>("teacher")
  const [docxExportMode, setDocxExportMode] = useState<ExportMode>("teacher")
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null)
  const [saveError, setSaveError] = useState("")

  const [quizFolderId, setQuizFolderId] = useState<string | null>(null)
  const [folderDialogOpen, setFolderDialogOpen] = useState(false)
  const [dialogFolders, setDialogFolders] = useState<QuizFolder[]>([])
  const [selectedFolderId, setSelectedFolderId] = useState<string>("")
  const [folderComboboxOpen, setFolderComboboxOpen] = useState(false)
  const [folderDialogError, setFolderDialogError] = useState("")
  const [foldersDialogLoading, setFoldersDialogLoading] = useState(false)
  const [showNewFolderField, setShowNewFolderField] = useState(false)
  const [newFolderDialogName, setNewFolderDialogName] = useState("")
  const [isCreatingFolder, setIsCreatingFolder] = useState(false)

  useEffect(() => {
    if (!quizData) return
    const normalized = normalizeQuizData(quizData)
    setQuiz(normalized)
    setQuizFolderId(normalized.folderId ?? null)
  }, [quizData])

  useEffect(() => {
    if (!resolvedQuizId) return
    if (quizData) return

    let ignore = false

    async function loadQuiz() {
      setIsLoadingQuiz(true)
      setLoadError("")
      setSaveError("")

      try {
        const response = await authFetch(`${API_BASE_URL}/quiz/${resolvedQuizId}`)
        if (!response.ok) {
          throw new Error(
            await readApiError(response, "Ошибка загрузки викторины")
          )
        }

        const data = (await response.json()) as any
        const mapped = backendQuizToQuizData(data)
        const normalized = normalizeQuizData(mapped)

        if (ignore) return
        setQuiz(normalized)
        setQuizFolderId(normalized.folderId ?? null)
        backendQuestionIdsRef.current = new Set(
          normalized.questions.map((q) => q.id)
        )
      } catch (err) {
        if (ignore) return
        setLoadError(
          err instanceof Error
            ? err.message
            : "Не удалось загрузить викторину"
        )
      } finally {
        if (!ignore) setIsLoadingQuiz(false)
      }
    }

    void loadQuiz()

    return () => {
      ignore = true
    }
  }, [resolvedQuizId, quizData])

  const maxScore = useMemo(
    () => getTotalMaxScore(quiz.questions),
    [quiz.questions]
  )

  const updateSettings = useCallback(
    (patch: Partial<Omit<QuizData, "questions" | "maxScore">>) => {
      setQuiz((prev) => ({ ...prev, ...patch }))
    },
    []
  )

  const updateQuestion = useCallback(
    (questionId: string, patch: Partial<QuizQuestion>) => {
      setQuiz((prev) => ({
        ...prev,
        questions: prev.questions.map((q) =>
          q.id === questionId ? { ...q, ...patch } : q
        ),
      }))
    },
    []
  )

  const handleTypeChange = useCallback(
    (questionId: string, newType: QuestionType) => {
      setQuiz((prev) => ({
        ...prev,
        questions: prev.questions.map((q) => {
          if (q.id !== questionId) return q

          if (newType === "trueFalse") {
            return { ...q, type: newType, options: createTrueFalseOptions() }
          }

          let options =
            q.type === "trueFalse"
              ? createDefaultOptions("single")
              : [...q.options]

          if (newType === "single") {
            const firstCorrect = options.findIndex((o) => o.isCorrect)
            const correctIndex = firstCorrect >= 0 ? firstCorrect : 0
            options = options.map((o, i) => ({
              ...o,
              isCorrect: i === correctIndex,
            }))
          }

          return { ...q, type: newType, options }
        }),
      }))
    },
    []
  )

  const updateOption = useCallback(
    (
      questionId: string,
      optionId: string,
      patch: Partial<QuizAnswerOption>
    ) => {
      setQuiz((prev) => ({
        ...prev,
        questions: prev.questions.map((q) => {
          if (q.id !== questionId) return q
          return {
            ...q,
            options: q.options.map((o) =>
              o.id === optionId ? { ...o, ...patch } : o
            ),
          }
        }),
      }))
    },
    []
  )

  const setSingleCorrect = useCallback(
    (questionId: string, optionId: string) => {
      setQuiz((prev) => ({
        ...prev,
        questions: prev.questions.map((q) => {
          if (q.id !== questionId) return q
          return {
            ...q,
            options: q.options.map((o) => ({
              ...o,
              isCorrect: o.id === optionId,
            })),
          }
        }),
      }))
    },
    []
  )

  const toggleMultipleCorrect = useCallback(
    (questionId: string, optionId: string, checked: boolean) => {
      updateOption(questionId, optionId, { isCorrect: checked })
    },
    [updateOption]
  )

  const addOption = useCallback((questionId: string) => {
    setQuiz((prev) => ({
      ...prev,
      questions: prev.questions.map((q) => {
        if (q.id !== questionId || q.type === "trueFalse") return q
        return { ...q, options: [...q.options, createOption()] }
      }),
    }))
  }, [])

  const removeOption = useCallback((questionId: string, optionId: string) => {
    setQuiz((prev) => ({
      ...prev,
      questions: prev.questions.map((q) => {
        if (q.id !== questionId || q.type === "trueFalse") return q
        if (q.options.length <= 2) return q
        const options = q.options.filter((o) => o.id !== optionId)
        if (q.type === "single" && !options.some((o) => o.isCorrect)) {
          options[0] = { ...options[0], isCorrect: true }
        }
        return { ...q, options }
      }),
    }))
  }, [])

  const insertQuestionAfter = useCallback((afterQuestionId: string) => {
    setQuiz((prev) => {
      const index = prev.questions.findIndex((q) => q.id === afterQuestionId)
      if (index === -1) return prev
      const questions = [...prev.questions]
      questions.splice(index + 1, 0, createNewQuestion())
      return { ...prev, questions }
    })
  }, [])

  const removeQuestion = useCallback((questionId: string) => {
    setQuiz((prev) => {
      if (prev.questions.length <= 1) return prev
      return {
        ...prev,
        questions: prev.questions.filter((q) => q.id !== questionId),
      }
    })
  }, [])

  const getPayload = useCallback(
    () => buildQuizPayload(quiz),
    [quiz]
  )

  const syncQuizWithBackend = async (
    status: "draft" | "published",
    folderId?: string | null
  ): Promise<boolean> => {
    if (!resolvedQuizId) return false

    setIsSavingQuiz(true)
    setSaveError("")

    try {
      const updateQuizPayload: UpdateQuizRequest = {
        title: quiz.title,
        difficulty: mapDifficultyFrontendToBackend(quiz.difficulty),
        full_time_seconds:
          quiz.timerMode === "total" ? Math.round(Number(quiz.totalTimer) * 60) : 0,
        question_time_seconds:
          quiz.timerMode === "per_question"
            ? Math.round(Number(quiz.timerPerQuestion))
            : 0,
        max_attempts: Math.round(Number(quiz.attempts)),
        status,
      }

      if (folderId !== undefined) {
        updateQuizPayload.folder_id = folderId
      }

      const updateQuizRes = await authFetch(`${API_BASE_URL}/quiz/${resolvedQuizId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updateQuizPayload),
      })

      if (!updateQuizRes.ok) {
        const errBody = await updateQuizRes.json().catch(() => ({}))
        throw new Error(
          (errBody as { detail?: string }).detail ??
            `Ошибка сохранения настроек: ${updateQuizRes.status}`
        )
      }

      const updateResult = (await updateQuizRes.json().catch(() => ({}))) as {
        quiz_id?: string
        duplicated?: boolean
      }
      const isDuplicated = updateResult.duplicated === true
      const targetQuizId =
        isDuplicated && updateResult.quiz_id
          ? updateResult.quiz_id
          : resolvedQuizId

      const originalQuestionIds = isDuplicated
        ? new Set<string>()
        : backendQuestionIdsRef.current
      const currentQuestionIds = new Set(quiz.questions.map((q) => q.id))

      const deletedQuestionIds = [...originalQuestionIds].filter(
        (id) => !currentQuestionIds.has(id)
      )

      if (!isDuplicated) {
        for (const questionId of deletedQuestionIds) {
          const deleteRes = await authFetch(
            `${API_BASE_URL}/quiz/${targetQuizId}/questions/${questionId}`,
            { method: "DELETE" }
          )
          if (!deleteRes.ok) {
            const errBody = await deleteRes.json().catch(() => ({}))
            throw new Error(
              (errBody as { detail?: string }).detail ??
                `Ошибка удаления вопроса: ${deleteRes.status}`
            )
          }
        }
      }

      for (let orderIdx = 0; orderIdx < quiz.questions.length; orderIdx++) {
        const q = quiz.questions[orderIdx]

        if (originalQuestionIds.has(q.id)) {
          const updatePayload = frontendQuestionToBackendUpdatePayload(
            q,
            orderIdx
          )

          const putRes = await authFetch(
            `${API_BASE_URL}/quiz/${targetQuizId}/questions/${q.id}`,
            {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(updatePayload),
            }
          )

          if (!putRes.ok) {
            const errBody = await putRes.json().catch(() => ({}))
            throw new Error(
              (errBody as { detail?: string }).detail ??
                `Ошибка обновления вопроса: ${putRes.status}`
            )
          }
        } else {
          const createPayload = frontendQuestionToBackendCreatePayload(q)

          const postRes = await authFetch(
            `${API_BASE_URL}/quiz/${targetQuizId}/questions`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(createPayload),
            }
          )

          if (!postRes.ok) {
            const errBody = await postRes.json().catch(() => ({}))
            throw new Error(
              (errBody as { detail?: string }).detail ??
                `Ошибка добавления вопроса: ${postRes.status}`
            )
          }

          const created = (await postRes.json().catch(() => ({}))) as {
            question_id?: string
          }

          if (!created.question_id) {
            throw new Error("Backend не вернул question_id при добавлении")
          }

          const updatePayload = frontendQuestionToBackendUpdatePayload(
            q,
            orderIdx
          )

          const putRes = await authFetch(
            `${API_BASE_URL}/quiz/${targetQuizId}/questions/${created.question_id}`,
            {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(updatePayload),
            }
          )

          if (!putRes.ok) {
            const errBody = await putRes.json().catch(() => ({}))
            throw new Error(
              (errBody as { detail?: string }).detail ??
                `Ошибка выставления порядка вопроса: ${putRes.status}`
            )
          }
        }
      }

      // Обновляем состояние после синхронизации (чтобы получить реальные question_id)
      const refreshedRes = await authFetch(`${API_BASE_URL}/quiz/${targetQuizId}`)
      if (!refreshedRes.ok) {
        const errBody = await refreshedRes.json().catch(() => ({}))
        throw new Error(
          (errBody as { detail?: string }).detail ??
            `Ошибка загрузки после сохранения: ${refreshedRes.status}`
        )
      }

      const refreshed = (await refreshedRes.json()) as any
      const mapped = backendQuizToQuizData(refreshed)
      const normalized = normalizeQuizData(mapped)

      setQuiz(normalized)
      if (folderId !== undefined) {
        setQuizFolderId(folderId)
      }
      backendQuestionIdsRef.current = new Set(
        normalized.questions.map((qq) => qq.id)
      )

      onSave?.(getPayload())
      return true
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Не удалось сохранить викторину"
      )
      return false
    } finally {
      setIsSavingQuiz(false)
    }
  }

  const openFolderDialog = async () => {
    setFolderDialogError("")
    setFoldersDialogLoading(true)
    setFolderDialogOpen(true)
    setShowNewFolderField(false)
    setNewFolderDialogName("")

    try {
      const list = await getFolders()
      setDialogFolders(list)
      const defaultId =
        quizFolderId ??
        returnFolderId ??
        (list.length > 0 ? list[0].id : "")
      setSelectedFolderId(defaultId)
    } catch (err) {
      setFolderDialogError(
        err instanceof Error ? err.message : "Не удалось загрузить папки"
      )
    } finally {
      setFoldersDialogLoading(false)
    }
  }

  const handleCreateFolderInDialog = async () => {
    const name = newFolderDialogName.trim()
    if (!name) {
      setFolderDialogError("Введите название папки")
      return
    }

    setFolderDialogError("")
    setIsCreatingFolder(true)
    try {
      const created = await createFolder(name)
      const list = await getFolders()
      setDialogFolders(list)
      setSelectedFolderId(created.id)
      setShowNewFolderField(false)
      setNewFolderDialogName("")
    } catch (err) {
      setFolderDialogError(
        err instanceof Error ? err.message : "Не удалось создать папку"
      )
    } finally {
      setIsCreatingFolder(false)
    }
  }

  const handleConfirmSaveToFolder = async () => {
    if (!selectedFolderId) {
      setFolderDialogError("Выберите папку")
      return
    }

    const ok = await syncQuizWithBackend("draft", selectedFolderId)
    if (!ok) {
      setFolderDialogError(saveError || "Не удалось сохранить викторину")
      return
    }

    setFolderDialogOpen(false)
    navigate(`/?folder_id=${encodeURIComponent(selectedFolderId)}`)
  }

  const handleSave = () => {
    void openFolderDialog()
  }

  const dashboardBackTo = resolveFolderBackUrl(returnFolderId, quizFolderId)

  const selectedFolderName =
    dialogFolders.find((f) => f.id === selectedFolderId)?.name ?? ""

  const handlePublish = async () => {
    await syncQuizWithBackend("published")

    const link = `${getStudentQuizBaseUrl()}/${resolvedQuizId}`
    try {
      await navigator.clipboard.writeText(link)
    } catch {
      // clipboard may be unavailable
    }
    onPublish?.(getPayload())
  }

  const handleExport = async (format: ExportFormat, mode: ExportMode) => {
    if (!resolvedQuizId) return

    setExportingFormat(format)
    setSaveError("")
    try {
      await downloadAuthenticatedFile(
        `${API_BASE_URL}/quiz/${resolvedQuizId}/export?format=${format}&mode=${mode}`,
        buildDownloadFilename(quiz.title, format)
      )
    } catch (err) {
      setSaveError(
        err instanceof Error
          ? err.message
          : `Не удалось скачать ${EXPORT_FORMAT_LABELS[format]}`
      )
    } finally {
      setExportingFormat(null)
    }
  }

  const isExporting = exportingFormat !== null

  const parseNumberInput = (value: string, min: number, fallback: number) =>
    Math.max(min, Number(value) || fallback)

  return (
    <div className="edit-quiz-page mx-auto max-w-4xl px-4 pb-40 pt-8 sm:px-6 lg:px-8">
      <Button asChild variant="ghost" size="sm" className="lf-back-btn mb-4 -ml-2">
        <Link to={dashboardBackTo}>Назад</Link>
      </Button>

      <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
        <DialogContent className="sm:max-w-md" showCloseButton>
          <DialogHeader>
            <DialogTitle>Выберите папку</DialogTitle>
          </DialogHeader>

          {foldersDialogLoading ? (
            <p className="text-sm text-muted-foreground">Загрузка папок…</p>
          ) : (
            <div className="flex items-start gap-2">
              <Popover
                open={folderComboboxOpen}
                onOpenChange={setFolderComboboxOpen}
              >
                <PopoverTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    role="combobox"
                    aria-expanded={folderComboboxOpen}
                    className="min-w-0 flex-1 justify-between bg-white"
                  >
                    <span className="truncate">
                      {selectedFolderName || "Выберите папку…"}
                    </span>
                    <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0">
                  <Command>
                    <CommandInput placeholder="Поиск папки…" />
                    <CommandList>
                      <CommandEmpty>Папки не найдены</CommandEmpty>
                      <CommandGroup>
                        {dialogFolders.map((folder) => (
                          <CommandItem
                            key={folder.id}
                            value={folder.name}
                            onSelect={() => {
                              setSelectedFolderId(folder.id)
                              setFolderComboboxOpen(false)
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 size-4",
                                selectedFolderId === folder.id
                                  ? "opacity-100"
                                  : "opacity-0"
                              )}
                            />
                            {folder.name}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label="Создать папку"
                onClick={() => {
                  setShowNewFolderField((v) => !v)
                  setFolderDialogError("")
                }}
              >
                <Plus />
              </Button>
            </div>
          )}

          {showNewFolderField && !foldersDialogLoading && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="new-folder-dialog-name">Название новой папки</Label>
              <div className="flex flex-wrap gap-2">
                <Input
                  id="new-folder-dialog-name"
                  value={newFolderDialogName}
                  onChange={(e) => setNewFolderDialogName(e.target.value)}
                  placeholder="Введите название"
                  className="min-w-0 flex-1 bg-white"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleCreateFolderInDialog()
                  }}
                  autoFocus
                />
                <Button
                  type="button"
                  size="sm"
                  className={cn(ACCENT_BUTTON_CLASS)}
                  disabled={isCreatingFolder || !newFolderDialogName.trim()}
                  onClick={() => void handleCreateFolderInDialog()}
                >
                  {isCreatingFolder ? "Создание…" : "Создать"}
                </Button>
              </div>
            </div>
          )}

          {folderDialogError && (
            <p className="text-sm text-destructive">{folderDialogError}</p>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setFolderDialogOpen(false)}
            >
              Отмена
            </Button>
            <Button
              type="button"
              className={cn(ACCENT_BUTTON_CLASS)}
              disabled={isSavingQuiz || foldersDialogLoading || !selectedFolderId}
              onClick={() => void handleConfirmSaveToFolder()}
            >
              {isSavingQuiz ? "Сохранение…" : "Сохранить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isLoadingQuiz && (
        <p className="mb-4 text-sm text-muted-foreground">Загрузка викторины...</p>
      )}
      {loadError && (
        <p className="mb-4 text-sm text-destructive">{loadError}</p>
      )}
      {saveError && (
        <p className="mb-4 text-sm text-destructive">{saveError}</p>
      )}

      <Card className={CARD_CLASS}>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">
            Настройки викторины
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="difficulty">Сложность викторины</Label>
              <Select
                value={quiz.difficulty}
                onValueChange={(value) =>
                  updateSettings({ difficulty: value as Difficulty })
                }
              >
                <SelectTrigger id="difficulty" className="w-full">
                  <SelectValue placeholder="Выберите сложность" />
                </SelectTrigger>
                <SelectContent
                  position="popper"
                  className="max-h-60 overflow-y-auto"
                >
                  {DIFFICULTIES.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="attempts">Количество попыток</Label>
              <Input
                id="attempts"
                type="number"
                min={1}
                max={100}
                value={quiz.attempts}
                onChange={(e) =>
                  updateSettings({
                    attempts: parseNumberInput(e.target.value, 1, 1),
                  })
                }
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="timerMode">Режим таймера</Label>
              <Select
                value={quiz.timerMode}
                onValueChange={(value) =>
                  updateSettings({
                    timerMode: value as TimerMode,
                    timerPerQuestion:
                      value === "per_question" ? quiz.timerPerQuestion : 0,
                    totalTimer: value === "total" ? quiz.totalTimer : 0,
                  })
                }
              >
                <SelectTrigger id="timerMode" className="w-full">
                  <SelectValue placeholder="Выберите режим" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="per_question">
                    Таймер на вопрос (сек)
                  </SelectItem>
                  <SelectItem value="total">Общий таймер (мин)</SelectItem>
                  <SelectItem value="none">Без таймера</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {quiz.timerMode === "per_question" && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="timerPerQuestion">
                  Время на один вопрос (секунд)
                </Label>
                <Input
                  id="timerPerQuestion"
                  type="number"
                  min={0}
                  value={quiz.timerPerQuestion}
                  onChange={(e) =>
                    updateSettings({
                      timerPerQuestion: parseNumberInput(e.target.value, 0, 0),
                    })
                  }
                />
              </div>
            )}

            {quiz.timerMode === "total" && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="totalTimer">Общее время на викторину (минут)</Label>
                <Input
                  id="totalTimer"
                  type="number"
                  min={0}
                  value={quiz.totalTimer}
                  onChange={(e) =>
                    updateSettings({
                      totalTimer: parseNumberInput(e.target.value, 0, 0),
                    })
                  }
                />
              </div>
            )}

            <div className="flex flex-col gap-2">
              <Label htmlFor="maxScore">Максимальный балл</Label>
              <Input
                id="maxScore"
                type="number"
                readOnly
                value={maxScore}
                className="bg-muted/50"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="mt-6 flex flex-col gap-2">
        <Label htmlFor="quizTitle">Название викторины</Label>
        <Input
          id="quizTitle"
          value={quiz.title}
          onChange={(e) => updateSettings({ title: e.target.value })}
          className="text-lg font-medium"
        />
      </div>

      <div className="mt-4 flex flex-col gap-4">
        {quiz.questions.map((question, index) => (
          <Card key={question.id} className={cn(QUESTION_CARD_CLASS, "card")}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <CardTitle className="lf-text text-base font-semibold">
                  Вопрос №{index + 1}
                </CardTitle>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="size-8 shrink-0"
                    onClick={() => insertQuestionAfter(question.id)}
                    title="Добавить вопрос после этого"
                    aria-label="Добавить вопрос после этого"
                  >
                    <Plus className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => removeQuestion(question.id)}
                    disabled={quiz.questions.length <= 1}
                    title="Удалить вопрос"
                    aria-label="Удалить вопрос"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
              <div className="mt-2 flex flex-col gap-1">
                <Label htmlFor={`type-${question.id}`}>Тип вопроса</Label>
                <Select
                  value={question.type}
                  onValueChange={(value) =>
                    handleTypeChange(question.id, value as QuestionType)
                  }
                >
                  <SelectTrigger
                    id={`type-${question.id}`}
                    className="w-full sm:w-[240px]"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    <SelectItem value="single">Одиночный выбор</SelectItem>
                    <SelectItem value="multiple">Множественный выбор</SelectItem>
                    <SelectItem value="trueFalse">True/False</SelectItem>
                  </SelectContent>
                </Select>
                <p className="lf-text text-sm text-muted-foreground">
                  {QUESTION_TYPE_LABELS[question.type]}
                </p>
              </div>
            </CardHeader>

            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor={`text-${question.id}`}>Текст вопроса</Label>
                <Textarea
                  id={`text-${question.id}`}
                  value={question.text}
                  onChange={(e) =>
                    updateQuestion(question.id, { text: e.target.value })
                  }
                  rows={3}
                />
                <MathPreview text={question.text} />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor={`source-${question.id}`}>Источник</Label>
                <Input
                  id={`source-${question.id}`}
                  value={question.source}
                  onChange={(e) =>
                    updateQuestion(question.id, { source: e.target.value })
                  }
                  placeholder="Фрагмент / страница / слайд"
                />
              </div>

              <div className="flex flex-col gap-3">
                <Label>Варианты ответов</Label>
                {question.options.map((option) => (
                  <div key={option.id} className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
                      {question.type === "multiple" ? (
                        <Checkbox
                          id={`correct-${option.id}`}
                          checked={option.isCorrect}
                          onCheckedChange={(checked) =>
                            toggleMultipleCorrect(
                              question.id,
                              option.id,
                              checked === true
                            )
                          }
                          className="shrink-0"
                        />
                      ) : (
                        <input
                          type="radio"
                          id={`correct-${option.id}`}
                          name={`correct-${question.id}`}
                          checked={option.isCorrect}
                          onChange={() =>
                            setSingleCorrect(question.id, option.id)
                          }
                          className="lf-radio size-4 shrink-0 accent-quiz-accent"
                        />
                      )}

                      <Input
                        id={`text-${option.id}`}
                        value={option.text}
                        onChange={(e) =>
                          updateOption(question.id, option.id, {
                            text: e.target.value,
                          })
                        }
                        disabled={question.type === "trueFalse"}
                        className="min-w-0 flex-1"
                        placeholder="Текст ответа"
                      />

                      <div className="flex shrink-0 items-center gap-1.5">
                        <Label
                          htmlFor={`points-${option.id}`}
                          className="sr-only"
                        >
                          Баллы
                        </Label>
                        <Input
                          id={`points-${option.id}`}
                          type="number"
                          min={0}
                          value={option.points}
                          onChange={(e) =>
                            updateOption(question.id, option.id, {
                              points: parseNumberInput(e.target.value, 0, 0),
                            })
                          }
                          className="w-20"
                          title="Баллы"
                        />
                        <span className="lf-text option-points-label text-xs whitespace-nowrap text-muted-foreground">
                          балл.
                        </span>
                      </div>

                      {question.type !== "trueFalse" && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeOption(question.id, option.id)}
                          className="shrink-0 text-muted-foreground hover:text-destructive"
                          aria-label="Удалить вариант"
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      )}
                    </div>

                    {option.text.trim() && (
                      <MathPreview text={option.text} className="sm:ml-6" />
                    )}
                  </div>
                ))}

                {question.type === "multiple" && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => addOption(question.id)}
                    className="w-fit"
                  >
                    <Plus />
                    Добавить вариант
                  </Button>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor={`explanation-${question.id}`}>
                  Пояснение к правильному ответу
                </Label>
                <Textarea
                  id={`explanation-${question.id}`}
                  value={question.explanation}
                  onChange={(e) =>
                    updateQuestion(question.id, {
                      explanation: e.target.value,
                    })
                  }
                  rows={2}
                />
                <MathPreview text={question.explanation} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="edit-quiz-footer fixed inset-x-0 bottom-0 z-50 border-t-2 border-quiz-card-border bg-white/95 px-4 py-3 shadow-lg backdrop-blur-sm">
        <div className="mx-auto max-w-4xl">
          {exportingFormat && (
            <p
              className="mb-2 text-center text-sm text-muted-foreground"
              role="status"
              aria-live="polite"
            >
              Идёт формирование {EXPORT_FORMAT_LABELS[exportingFormat]}… Это может
              занять до минуты, особенно если в викторине есть формулы.
            </p>
          )}
          <div className="flex flex-wrap items-center justify-center gap-3 sm:justify-end">
          <Button
            type="button"
            className={cn(ACCENT_BUTTON_CLASS)}
            onClick={handleSave}
            disabled={isLoadingQuiz || isSavingQuiz || isExporting}
          >
            Сохранить черновик
          </Button>
          <div className="flex items-center gap-2">
            <Select
              value={pdfExportMode}
              onValueChange={(value) => setPdfExportMode(value as ExportMode)}
              disabled={isExporting}
            >
              <SelectTrigger className="w-[180px] bg-white" aria-label="Экспорт PDF">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="teacher">Для учителя</SelectItem>
                <SelectItem value="student">Для учеников</SelectItem>
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleExport("pdf", pdfExportMode)}
              disabled={isLoadingQuiz || isSavingQuiz || isExporting}
            >
              {exportingFormat === "pdf" ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Формирование PDF…
                </>
              ) : (
                <>
                  <Download className="size-4" />
                  Скачать PDF
                </>
              )}
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={pptxExportMode}
              onValueChange={(value) => setPptxExportMode(value as ExportMode)}
              disabled={isExporting}
            >
              <SelectTrigger className="w-[180px] bg-white" aria-label="Экспорт PPTX">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="teacher">Для учителя</SelectItem>
                <SelectItem value="student">Для учеников</SelectItem>
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleExport("pptx", pptxExportMode)}
              disabled={isLoadingQuiz || isSavingQuiz || isExporting}
            >
              {exportingFormat === "pptx" ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Формирование PPTX…
                </>
              ) : (
                <>
                  <Download className="size-4" />
                  Скачать PPTX
                </>
              )}
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={docxExportMode}
              onValueChange={(value) => setDocxExportMode(value as ExportMode)}
              disabled={isExporting}
            >
              <SelectTrigger className="w-[180px] bg-white" aria-label="Экспорт DOCX">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="teacher">Для учителя</SelectItem>
                <SelectItem value="student">Для учеников</SelectItem>
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleExport("docx", docxExportMode)}
              disabled={isLoadingQuiz || isSavingQuiz || isExporting}
            >
              {exportingFormat === "docx" ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Формирование DOCX…
                </>
              ) : (
                <>
                  <Download className="size-4" />
                  Скачать DOCX
                </>
              )}
            </Button>
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={handlePublish}
            disabled={isLoadingQuiz || isSavingQuiz || isExporting}
          >
            Копировать ссылку для учеников
          </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
