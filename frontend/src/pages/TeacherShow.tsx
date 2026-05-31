import { useEffect, useMemo, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { Check, Pause, Play, X } from "lucide-react"

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
import { API_BASE_URL } from "@/lib/api"
import { resolveFolderBackUrl } from "@/lib/navigation"
import { authFetch } from "@/lib/auth"
import { readApiError } from "@/lib/quizApi"
import { MathText } from "@/components/MathText"
import { cn } from "@/lib/utils"
import { backendQuizToQuizData } from "@/pages/EditQuiz"
import type { QuestionType, QuizData, QuizQuestion } from "@/types/quiz"

export type { QuizData } from "@/types/quiz"

export interface TeacherShowProps {
  quizData?: QuizData
}

type TeacherMode = "end" | "instant"
type TeacherStage = "setup" | "quiz" | "answers-table" | "finished"

const QUESTION_TYPE_HINTS: Record<QuestionType, string> = {
  single: "Одиночный выбор",
  multiple: "Множественный выбор",
  trueFalse: "True/False",
}

const ACCENT_BUTTON_CLASS =
  "h-12 border-transparent bg-quiz-accent text-base text-white hover:bg-quiz-accent/90 sm:h-14 sm:text-lg"
const NEXT_BUTTON_CLASS =
  "h-12 border-2 border-quiz-card-border bg-quiz-card-border text-base text-white hover:bg-quiz-card-border/90 sm:h-14 sm:text-lg"

const EMPTY_QUIZ: QuizData = {
  id: "",
  title: "",
  difficulty: "Средне",
  attempts: 1,
  timerPerQuestion: 0,
  totalTimer: 0,
  maxScore: 0,
  questions: [],
}

function normalizeQuizData(data: QuizData): QuizData {
  return {
    ...data,
    title: data.title ?? "Викторина",
    questions: data.questions ?? [],
  }
}

function formatTimer(seconds: number): string {
  const mm = Math.floor(seconds / 60)
  const ss = seconds % 60
  return `${mm}:${ss.toString().padStart(2, "0")}`
}

function getCorrectAnswersText(question: QuizQuestion): string {
  const correct = question.options.filter((o) => o.isCorrect).map((o) => o.text)
  return correct.length > 0 ? correct.join(", ") : "—"
}

export default function TeacherShow({ quizData: quizDataProp }: TeacherShowProps) {
  const { quizId } = useParams<{ quizId: string }>()
  const [searchParams] = useSearchParams()
  const folderIdFromUrl = searchParams.get("folder_id")
  const [loadedQuiz, setLoadedQuiz] = useState<QuizData | null>(
    quizDataProp ?? null
  )
  const [isLoadingQuiz, setIsLoadingQuiz] = useState(
    !quizDataProp && Boolean(quizId)
  )
  const [loadError, setLoadError] = useState("")

  useEffect(() => {
    if (quizDataProp) {
      setLoadedQuiz(quizDataProp)
      return
    }
    if (!quizId) {
      setLoadError("Не указан идентификатор викторины")
      setIsLoadingQuiz(false)
      return
    }

    let ignore = false

    async function loadQuiz() {
      setIsLoadingQuiz(true)
      setLoadError("")
      try {
        const response = await authFetch(`${API_BASE_URL}/quiz/${quizId}`)
        if (!response.ok) {
          throw new Error(
            await readApiError(response, "Ошибка загрузки викторины")
          )
        }
        const data = (await response.json()) as Record<string, unknown>
        if (!ignore) setLoadedQuiz(backendQuizToQuizData(data))
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
  }, [quizId, quizDataProp])

  const quiz = useMemo(
    () => normalizeQuizData(loadedQuiz ?? EMPTY_QUIZ),
    [loadedQuiz]
  )

  const backToDashboard = resolveFolderBackUrl(
    folderIdFromUrl,
    loadedQuiz?.folderId
  )

  const [stage, setStage] = useState<TeacherStage>("setup")
  const [mode, setMode] = useState<TeacherMode>("end")
  const [questionTimerSeconds, setQuestionTimerSeconds] = useState(20)
  const [withoutQuestionTimer, setWithoutQuestionTimer] = useState(false)

  const [questionIndex, setQuestionIndex] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [isRevealed, setIsRevealed] = useState(false)
  const [timeLeft, setTimeLeft] = useState(20)
  const [isPaused, setIsPaused] = useState(false)

  useEffect(() => {
    if (!loadedQuiz?.timerPerQuestion) return
    const seconds = Math.max(10, Number(loadedQuiz.timerPerQuestion) || 0)
    if (seconds > 0) {
      setQuestionTimerSeconds(seconds)
      setTimeLeft(seconds)
    }
  }, [loadedQuiz?.timerPerQuestion])

  const totalQuestions = quiz.questions.length
  const currentQuestion = quiz.questions[questionIndex]
  const isLastQuestion = questionIndex >= totalQuestions - 1
  const timerEnabled = mode === "end" || (mode === "instant" && !withoutQuestionTimer)
  const shouldAutoReveal = mode === "instant" && timerEnabled
  const shouldAutoNext = mode === "end" && timerEnabled
  const canManualReveal = mode === "instant" && withoutQuestionTimer

  const resetToQuestion = (nextIndex: number) => {
    setQuestionIndex(nextIndex)
    setSelectedIds([])
    setIsRevealed(false)
    setIsPaused(false)
    setTimeLeft(questionTimerSeconds)
  }

  useEffect(() => {
    if (stage !== "quiz" || !timerEnabled || isPaused || isRevealed) return

    const id = window.setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          window.clearInterval(id)
          if (mode === "end") {
            const last = questionIndex >= totalQuestions - 1
            if (last) {
              setStage("answers-table")
              return 0
            }

            // Переход к следующему вопросу и запуск таймера с чистого состояния
            setQuestionIndex(questionIndex + 1)
            setSelectedIds([])
            setIsRevealed(false)
            setIsPaused(false)
            return questionTimerSeconds
          }

          if (mode === "instant") {
            // В режиме "Ответы сразу" с таймером показываем ответы только по истечению времени
            setIsRevealed(true)
            setIsPaused(false)
            return 0
          }

          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => window.clearInterval(id)
  }, [
    stage,
    timerEnabled,
    isPaused,
    isRevealed,
    questionIndex,
    questionTimerSeconds,
    mode,
    totalQuestions,
  ])

  const handleStart = () => {
    setStage("quiz")
    resetToQuestion(0)
  }

  const handleNextQuestion = () => {
    if (!isRevealed) return
    if (isLastQuestion) return
    resetToQuestion(questionIndex + 1)
  }

  const toggleOption = (optionId: string) => {
    if (!currentQuestion || isRevealed) return

    if (currentQuestion.type === "multiple") {
      setSelectedIds((prev) =>
        prev.includes(optionId)
          ? prev.filter((id) => id !== optionId)
          : [...prev, optionId]
      )
      return
    }

    setSelectedIds([optionId])
  }

  const revealAnswersManually = () => {
    if (!canManualReveal || selectedIds.length === 0) return
    setIsRevealed(true)
  }

  const getOptionClassName = (optionId: string, isCorrect: boolean) => {
    const isSelected = selectedIds.includes(optionId)

    if (!isRevealed) {
      return cn(
        "h-auto min-h-16 w-full justify-start whitespace-normal rounded-xl border-2 border-quiz-card-border bg-white px-6 py-4 text-left text-lg font-medium transition-colors hover:bg-quiz-card-border/15",
        isSelected && "border-quiz-accent bg-quiz-accent/10 ring-2 ring-quiz-accent/30"
      )
    }

    if (isCorrect) {
      return "h-auto min-h-16 w-full justify-start whitespace-normal rounded-xl border-2 border-green-600 bg-green-100 px-6 py-4 text-left text-lg font-medium text-green-900"
    }

    if (isSelected) {
      return "h-auto min-h-16 w-full justify-start whitespace-normal rounded-xl border-2 border-red-600 bg-red-100 px-6 py-4 text-left text-lg font-medium text-red-900"
    }

    return "h-auto min-h-16 w-full justify-start whitespace-normal rounded-xl border-2 border-quiz-card-border/50 bg-white/80 px-6 py-4 text-left text-lg font-medium text-muted-foreground"
  }

  if (isLoadingQuiz) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <p className="text-lg text-muted-foreground">Загрузка викторины...</p>
      </div>
    )
  }

  if (loadError || !loadedQuiz) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
        <p className="text-lg text-destructive">
          {loadError || "Викторина не найдена"}
        </p>
        <Button asChild variant="outline">
          <Link to={backToDashboard}>К списку викторин</Link>
        </Button>
      </div>
    )
  }

  if (stage === "setup") {
    return (
      <div className="relative mx-auto flex min-h-screen max-w-3xl items-center px-4 py-8 sm:px-8">
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="lf-back-btn absolute top-4 left-4 text-muted-foreground"
        >
          <Link to={backToDashboard}>Выйти</Link>
        </Button>

        <Card className="w-full border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardHeader>
            <CardTitle className="text-2xl font-bold sm:text-3xl">
              Настройки показа
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label htmlFor="question-timer">Таймер на вопрос</Label>
              <Input
                id="question-timer"
                type="number"
                min={10}
                value={questionTimerSeconds}
                disabled={mode === "instant" && withoutQuestionTimer}
                onChange={(e) =>
                  setQuestionTimerSeconds(Math.max(10, Number(e.target.value) || 10))
                }
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="mode">Выберите режим</Label>
              <Select
                value={mode}
                onValueChange={(value) => setMode(value as TeacherMode)}
              >
                <SelectTrigger id="mode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper">
                  <SelectItem value="end">Ответы в конце</SelectItem>
                  <SelectItem value="instant">Ответы сразу</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {mode === "instant" && (
              <div className="flex items-center gap-2 rounded-lg border border-input bg-muted/20 p-3">
                <Checkbox
                  id="without-timer"
                  checked={withoutQuestionTimer}
                  onCheckedChange={(checked) => setWithoutQuestionTimer(checked === true)}
                />
                <Label htmlFor="without-timer">Без таймера на вопрос</Label>
              </div>
            )}

            <Button
              type="button"
              className={cn("mt-2 w-full", ACCENT_BUTTON_CLASS)}
              onClick={handleStart}
            >
              Начать показ
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (stage === "answers-table") {
    return (
      <div className="relative mx-auto min-h-screen max-w-5xl px-4 py-8 sm:px-8">
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="lf-back-btn absolute top-4 left-4 text-muted-foreground"
        >
          <Link to={backToDashboard}>Выйти</Link>
        </Button>

        <Card className="mx-auto max-w-3xl border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardContent className="flex flex-col items-center gap-6 py-10 text-center">
            <h2 className="lf-text text-2xl font-bold sm:text-3xl">Вопросы завершены</h2>
            <Button
              type="button"
              className={cn(ACCENT_BUTTON_CLASS)}
              onClick={() => setStage("finished")}
            >
              Перейти к ответам
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (stage === "finished" && mode === "end") {
    return (
      <div className="relative mx-auto min-h-screen max-w-6xl px-4 py-8 sm:px-8">
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="lf-back-btn absolute top-4 left-4 text-muted-foreground"
        >
          <Link to={backToDashboard}>Выйти</Link>
        </Button>

        <h2 className="mb-6 text-center text-2xl font-bold sm:text-3xl">
          Правильные ответы
        </h2>
        <Card className="border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left text-base">
                <thead>
                  <tr className="border-b-2 border-quiz-card-border bg-muted/40">
                    <th className="px-4 py-3 sm:px-6">Текст вопроса</th>
                    <th className="px-4 py-3 sm:px-6">Правильный ответ</th>
                  </tr>
                </thead>
                <tbody>
                  {quiz.questions.map((q, i) => (
                    <tr
                      key={q.id}
                      className="border-b border-quiz-card-border/40 hover:bg-muted/20"
                    >
                      <td className="px-4 py-4 sm:px-6">
                        <MathText>{`${i + 1}. ${q.text}`}</MathText>
                      </td>
                      <td className="px-4 py-4 font-medium text-green-700 sm:px-6">
                        <MathText>{getCorrectAnswersText(q)}</MathText>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!currentQuestion) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <p className="text-xl text-muted-foreground">В викторине нет вопросов</p>
      </div>
    )
  }

  return (
    <div className="relative mx-auto min-h-screen max-w-4xl px-4 py-6 sm:px-8 sm:py-8">
      <Button
        asChild
        variant="ghost"
        size="sm"
        className="lf-back-btn absolute top-4 left-4 text-muted-foreground"
      >
        <Link to={backToDashboard}>Выйти</Link>
      </Button>

      <header className="mb-8 pt-8 text-center sm:pt-0">
        <h1 className="text-2xl font-bold sm:text-3xl">{quiz.title}</h1>
        <p className="lf-text mt-2 text-lg text-muted-foreground sm:text-xl">
          Вопрос {questionIndex + 1} из {totalQuestions}
        </p>
      </header>

      <main className="flex flex-col gap-6">
        <Card className="border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardContent className="flex flex-col gap-6 pt-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="lf-text text-sm font-medium text-muted-foreground sm:text-base">
                  {QUESTION_TYPE_HINTS[currentQuestion.type]}
                </p>
                <h2 className="mt-3 text-xl font-semibold leading-snug sm:text-2xl">
                  <MathText as="span">{currentQuestion.text}</MathText>
                </h2>
              </div>

              {timerEnabled && (
                <div className="flex items-center gap-2 rounded-lg border-2 border-quiz-card-border bg-white px-3 py-2">
                  <span className="lf-timer text-xl font-bold tabular-nums">
                    {formatTimer(timeLeft)}
                  </span>
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    className="size-8"
                    onClick={() => setIsPaused((v) => !v)}
                    disabled={isRevealed}
                    aria-label={isPaused ? "Продолжить таймер" : "Пауза таймера"}
                  >
                    {isPaused ? <Play className="size-4" /> : <Pause className="size-4" />}
                  </Button>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-3">
              {currentQuestion.options.map((option) => {
                const showCheck = isRevealed && option.isCorrect
                const showCross =
                  isRevealed && selectedIds.includes(option.id) && !option.isCorrect

                return (
                  <Button
                    key={option.id}
                    type="button"
                    variant="outline"
                    disabled={isRevealed}
                    onClick={() => toggleOption(option.id)}
                    className={cn(getOptionClassName(option.id, option.isCorrect), "quiz-option-btn")}
                  >
                    <span className="flex w-full min-w-0 items-start justify-between gap-4">
                      <MathText className="quiz-option-text min-w-0 flex-1 break-words text-left [overflow-wrap:anywhere]">
                        {option.text}
                      </MathText>
                      <span className="flex shrink-0 items-center gap-2">
                        {showCheck && <Check className="size-6 text-green-700" aria-hidden />}
                        {showCross && <X className="size-6 text-red-700" aria-hidden />}
                      </span>
                    </span>
                  </Button>
                )
              })}
            </div>

            {canManualReveal && !isRevealed && (
              <Button
                type="button"
                className={cn("w-full", ACCENT_BUTTON_CLASS)}
                disabled={selectedIds.length === 0}
                onClick={revealAnswersManually}
              >
                Отправить ответ
              </Button>
            )}

            {isRevealed && currentQuestion.explanation.trim() && (
              <Card className="border border-quiz-card-border/60 bg-muted/40 shadow-none">
                <CardContent className="pt-4">
                  <p className="lf-text mb-1 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Пояснение
                  </p>
                  <MathText as="p" className="lf-text text-lg">
                    {currentQuestion.explanation}
                  </MathText>
                </CardContent>
              </Card>
            )}

            {isRevealed && !isLastQuestion && (
              <Button
                type="button"
                className={cn("w-full", NEXT_BUTTON_CLASS)}
                onClick={handleNextQuestion}
              >
                Следующий вопрос
              </Button>
            )}

            {isRevealed && isLastQuestion && (
              <p className="lf-text text-center text-lg font-medium text-muted-foreground">
                Викторина окончена
              </p>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
