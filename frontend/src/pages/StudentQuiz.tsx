import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { API_BASE_URL } from "@/lib/api"
import {
  buildStudentAnswerPayload,
  mapQuizMetaFromApi,
  mapStudentQuestionsFromApi,
  readApiError,
} from "@/lib/quizApi"
import { cn } from "@/lib/utils"
import type { QuizData, QuizQuestion } from "@/types/quiz"

export type { QuizData } from "@/types/quiz"

export interface StudentAnswerRecord {
  questionId: string
  selectedOptionIds: string[]
  pointsEarned: number
}

export interface QuizResultData {
  quizId?: string
  firstName: string
  lastName: string
  fullName: string
  score: number
  maxScore: number
  elapsedSeconds: number
  attemptNumber: number
  maxAttempts: number
  answers: StudentAnswerRecord[]
  completedAt: string
}

export interface StudentQuizProps {
  quizData?: QuizData
  onComplete?: (result: QuizResultData) => void
}

type Stage = "intro" | "quiz" | "result"

const ACCENT_BUTTON_CLASS =
  "h-12 border-transparent bg-quiz-accent text-base text-white hover:bg-quiz-accent/90 sm:h-14 sm:text-lg"
const NEXT_BUTTON_CLASS =
  "h-12 border-2 border-quiz-card-border bg-quiz-card-border text-base text-white hover:bg-quiz-card-border/90 sm:h-14 sm:text-lg"

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m} мин ${s} сек`
}

function formatTimer(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export default function StudentQuiz({
  quizData,
  onComplete,
}: StudentQuizProps) {
  const { quizId: routeQuizId } = useParams<{ quizId: string }>()

  const [quizSettings, setQuizSettings] = useState({
    title: quizData?.title ?? "Викторина",
    attempts: quizData?.attempts ?? 1,
    timerPerQuestion: quizData?.timerPerQuestion ?? 0,
    totalTimer: quizData?.totalTimer ?? 0,
  })
  const [questions, setQuestions] = useState<QuizQuestion[]>(
    quizData?.questions ?? []
  )
  const [maxScore, setMaxScore] = useState(quizData?.maxScore ?? 0)

  const quiz = useMemo<QuizData>(
    () => ({
      id: routeQuizId ?? quizData?.id,
      title: quizSettings.title,
      difficulty: quizData?.difficulty ?? "Средне",
      attempts: quizSettings.attempts,
      timerPerQuestion: quizSettings.timerPerQuestion,
      totalTimer: quizSettings.totalTimer,
      maxScore,
      questions,
    }),
    [routeQuizId, quizData, quizSettings, maxScore, questions]
  )

  const [isLoadingMeta, setIsLoadingMeta] = useState(Boolean(routeQuizId))
  const [loadMetaError, setLoadMetaError] = useState("")
  const [startError, setStartError] = useState("")
  const [apiError, setApiError] = useState("")
  const [isStarting, setIsStarting] = useState(false)
  const [attemptId, setAttemptId] = useState<string | null>(null)
  const attemptIdRef = useRef<string | null>(null)

  const [stage, setStage] = useState<Stage>("intro")
  const [participantName, setParticipantName] = useState("")
  const [attemptNumber, setAttemptNumber] = useState(1)
  const [questionIndex, setQuestionIndex] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [hasSubmitted, setHasSubmitted] = useState(false)
  const [score, setScore] = useState(0)
  const [answers, setAnswers] = useState<StudentAnswerRecord[]>([])
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [questionTimeLeft, setQuestionTimeLeft] = useState(0)
  const [totalTimeLeft, setTotalTimeLeft] = useState(0)

  const hasSubmittedRef = useRef(false)
  const completeSentForAttempt = useRef(0)
  const questionIndexRef = useRef(questionIndex)
  const elapsedSecondsRef = useRef(0)
  const questionTimeoutHandledRef = useRef(-1)
  const onQuestionTimeExpiredRef = useRef<() => void>(() => {})

  const totalQuestions = quiz.questions.length
  const currentQuestion = quiz.questions[questionIndex]
  const isLastQuestion = questionIndex >= totalQuestions - 1
  const canStart = participantName.trim().length > 0
  const hasAttemptsLeft = attemptNumber < quiz.attempts

  useEffect(() => {
    questionIndexRef.current = questionIndex
  }, [questionIndex])

  useEffect(() => {
    elapsedSecondsRef.current = elapsedSeconds
  }, [elapsedSeconds])

  useEffect(() => {
    attemptIdRef.current = attemptId
  }, [attemptId])

  useEffect(() => {
    if (!routeQuizId || quizData) {
      setIsLoadingMeta(false)
      return
    }

    let ignore = false

    async function loadMeta() {
      setIsLoadingMeta(true)
      setLoadMetaError("")
      try {
        const response = await fetch(`${API_BASE_URL}/quiz/${routeQuizId}`)
        if (!response.ok) {
          throw new Error(
            await readApiError(response, "Не удалось загрузить викторину")
          )
        }
        const data = (await response.json()) as {
          quiz_id: string
          title?: string
          max_attempts?: number
          question_time_seconds?: number
          full_time_seconds?: number
        }
        if (ignore) return
        setQuizSettings(mapQuizMetaFromApi(data))
      } catch (err) {
        if (ignore) return
        setLoadMetaError(
          err instanceof Error ? err.message : "Не удалось загрузить викторину"
        )
      } finally {
        if (!ignore) setIsLoadingMeta(false)
      }
    }

    void loadMeta()

    return () => {
      ignore = true
    }
  }, [routeQuizId, quizData])

  const submitAnswerToBackend = useCallback(
    async (question: QuizQuestion, optionIds: string[]) => {
      const currentAttemptId = attemptIdRef.current
      if (!currentAttemptId) {
        throw new Error("Попытка не начата")
      }

      const answer = buildStudentAnswerPayload(question, optionIds)
      const response = await fetch(
        `${API_BASE_URL}/quiz/attempt/${currentAttemptId}/answer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question_id: question.id,
            answer,
          }),
        }
      )

      if (!response.ok) {
        throw new Error(
          await readApiError(response, "Не удалось отправить ответ")
        )
      }

      const data = (await response.json()) as {
        points_received?: number
        total_score?: number
      }

      const pointsReceived = Number(data.points_received) || 0
      const totalScore = Number(data.total_score) || 0

      setScore(totalScore)
      setAnswers((prev) => [
        ...prev,
        {
          questionId: question.id,
          selectedOptionIds: optionIds,
          pointsEarned: pointsReceived,
        },
      ])
    },
    []
  )

  const finishQuiz = useCallback(async () => {
    setApiError("")
    const q = questions[questionIndexRef.current]

    try {
      if (q && !hasSubmittedRef.current) {
        await submitAnswerToBackend(q, [])
        hasSubmittedRef.current = true
      }

      const currentAttemptId = attemptIdRef.current
      if (currentAttemptId) {
        const durationSeconds = Math.max(
          0,
          Math.round(elapsedSecondsRef.current)
        )
        const response = await fetch(
          `${API_BASE_URL}/quiz/attempt/${currentAttemptId}/finish`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ duration_seconds: durationSeconds }),
          }
        )

        if (!response.ok) {
          throw new Error(
            await readApiError(response, "Не удалось завершить викторину")
          )
        }

        const data = (await response.json()) as {
          score?: number
          max_score?: number
          attempt_number?: number
          duration_seconds?: number
        }

        if (data.score !== undefined) setScore(Number(data.score) || 0)
        if (data.max_score !== undefined) {
          setMaxScore(Number(data.max_score) || maxScore)
        }
        if (data.attempt_number !== undefined) {
          setAttemptNumber(Number(data.attempt_number) || 1)
        }
        if (data.duration_seconds !== undefined) {
          const savedDuration = Math.max(0, Number(data.duration_seconds) || 0)
          setElapsedSeconds(savedDuration)
          elapsedSecondsRef.current = savedDuration
        }
      }

      setStage("result")
    } catch (err) {
      setApiError(
        err instanceof Error ? err.message : "Не удалось завершить викторину"
      )
    }
  }, [questions, submitAnswerToBackend, maxScore, attemptNumber])

  const buildResult = useCallback(
    (): QuizResultData => {
      const name = participantName.trim()
      return {
        quizId: quiz.id,
        firstName: name,
        lastName: "",
        fullName: name,
        score,
        maxScore,
        elapsedSeconds,
        attemptNumber,
        maxAttempts: quiz.attempts,
        answers,
        completedAt: new Date().toISOString(),
      }
    },
    [
      quiz.id,
      quiz.attempts,
      participantName,
      score,
      maxScore,
      elapsedSeconds,
      attemptNumber,
      answers,
    ]
  )

  const advanceToNextQuestion = useCallback(() => {
    const index = questionIndexRef.current

    if (index >= quiz.questions.length - 1) {
      finishQuiz()
      return
    }

    questionTimeoutHandledRef.current = -1
    setQuestionIndex(index + 1)
    setSelectedIds([])
    setHasSubmitted(false)
    hasSubmittedRef.current = false
  }, [quiz.questions.length, finishQuiz])

  const onQuestionTimeExpired = useCallback(() => {
    const index = questionIndexRef.current

    if (questionTimeoutHandledRef.current === index) return
    questionTimeoutHandledRef.current = index

    if (hasSubmittedRef.current) return

    const question = questions[index]
    if (!question) {
      void finishQuiz()
      return
    }

    void submitAnswerToBackend(question, [])
      .then(() => {
        if (index >= questions.length - 1) {
          void finishQuiz()
          return
        }

        questionTimeoutHandledRef.current = -1
        setQuestionIndex(index + 1)
        setSelectedIds([])
        setHasSubmitted(false)
        hasSubmittedRef.current = false
      })
      .catch((err) => {
        setApiError(
          err instanceof Error ? err.message : "Не удалось отправить ответ"
        )
      })
  }, [questions, submitAnswerToBackend, finishQuiz])

  useEffect(() => {
    onQuestionTimeExpiredRef.current = onQuestionTimeExpired
  }, [onQuestionTimeExpired])

  const resetQuizSession = useCallback(() => {
    setQuestionIndex(0)
    setSelectedIds([])
    setHasSubmitted(false)
    hasSubmittedRef.current = false
    setScore(0)
    setAnswers([])
    setElapsedSeconds(0)
    elapsedSecondsRef.current = 0
    setQuestionTimeLeft(quiz.timerPerQuestion)
    setTotalTimeLeft(quiz.totalTimer * 60)
    completeSentForAttempt.current = 0
    questionTimeoutHandledRef.current = -1
  }, [quiz.timerPerQuestion, quiz.totalTimer])

  const beginAttempt = async () => {
    if (!routeQuizId) {
      setStartError("Не указан идентификатор викторины")
      return
    }

    setIsStarting(true)
    setStartError("")
    setApiError("")

    try {
      const startResponse = await fetch(
        `${API_BASE_URL}/quiz/${routeQuizId}/start`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ student_name: participantName.trim() }),
        }
      )

      if (!startResponse.ok) {
        throw new Error(
          await readApiError(startResponse, "Не удалось начать викторину")
        )
      }

      const startData = (await startResponse.json()) as { attempt_id?: string }
      if (!startData.attempt_id) {
        throw new Error("Backend не вернул attempt_id")
      }

      setAttemptId(startData.attempt_id)
      attemptIdRef.current = startData.attempt_id

      const questionsResponse = await fetch(
        `${API_BASE_URL}/quiz/${routeQuizId}/questions`
      )

      if (!questionsResponse.ok) {
        throw new Error(
          await readApiError(questionsResponse, "Не удалось загрузить вопросы")
        )
      }

      const questionsData = (await questionsResponse.json()) as {
        questions?: import("@/lib/quizApi").ApiStudentQuestion[]
      }

      const mapped = mapStudentQuestionsFromApi(questionsData.questions ?? [])
      if (mapped.questions.length === 0) {
        throw new Error("Викторина не содержит вопросов")
      }

      setQuestions(mapped.questions)
      setMaxScore(mapped.maxScore)
      resetQuizSession()
      setStage("quiz")
    } catch (err) {
      setStartError(
        err instanceof Error ? err.message : "Не удалось начать викторину"
      )
    } finally {
      setIsStarting(false)
    }
  }

  const handleStart = () => {
    void beginAttempt()
  }

  const handleRetry = () => {
    void beginAttempt()
  }

  const toggleOption = (optionId: string) => {
    if (hasSubmitted || !currentQuestion) return

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

  const handleSubmit = () => {
    if (hasSubmitted || selectedIds.length === 0 || !currentQuestion) return

    void submitAnswerToBackend(currentQuestion, [...selectedIds])
      .then(() => {
        setHasSubmitted(true)
        hasSubmittedRef.current = true
      })
      .catch((err) => {
        setApiError(
          err instanceof Error ? err.message : "Не удалось отправить ответ"
        )
      })
  }

  const handleNext = () => {
    if (!hasSubmitted) return
    advanceToNextQuestion()
  }

  useEffect(() => {
    hasSubmittedRef.current = hasSubmitted
  }, [hasSubmitted])

  useEffect(() => {
    if (stage !== "result" || !onComplete) return
    if (completeSentForAttempt.current === attemptNumber) return
    completeSentForAttempt.current = attemptNumber
    onComplete(buildResult())
  }, [stage, attemptNumber, score, answers, elapsedSeconds, onComplete, buildResult])

  useEffect(() => {
    if (stage !== "quiz") return

    const id = window.setInterval(() => {
      setElapsedSeconds((s) => s + 1)
    }, 1000)

    return () => window.clearInterval(id)
  }, [stage])

  useEffect(() => {
    if (stage !== "quiz" || quiz.totalTimer <= 0) return

    setTotalTimeLeft(quiz.totalTimer * 60)

    const id = window.setInterval(() => {
      setTotalTimeLeft((prev) => {
        if (prev <= 1) {
          window.clearInterval(id)
          void finishQuiz()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => window.clearInterval(id)
  }, [stage, attemptNumber, quiz.totalTimer, finishQuiz])

  useEffect(() => {
    if (stage !== "quiz" || quiz.timerPerQuestion <= 0) return

    questionTimeoutHandledRef.current = -1
    setQuestionTimeLeft(quiz.timerPerQuestion)

    const id = window.setInterval(() => {
      setQuestionTimeLeft((prev) => {
        if (prev <= 1) {
          window.clearInterval(id)
          onQuestionTimeExpiredRef.current()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => window.clearInterval(id)
  }, [stage, questionIndex, attemptNumber, quiz.timerPerQuestion])

  useEffect(() => {
    if (
      stage === "quiz" &&
      totalQuestions > 0 &&
      questionIndex >= totalQuestions
    ) {
      void finishQuiz()
    }
  }, [stage, questionIndex, totalQuestions, finishQuiz])

  if (!routeQuizId && !quizData) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 py-8">
        <p className="text-destructive">Некорректная ссылка на викторину</p>
      </div>
    )
  }

  if (stage === "intro") {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 py-8">
        <Card className="w-full max-w-md border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardHeader>
            <CardTitle className="text-center text-2xl">
              {quiz.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {isLoadingMeta && (
              <p className="text-sm text-muted-foreground">Загрузка...</p>
            )}
            {loadMetaError && (
              <p className="text-sm text-destructive">{loadMetaError}</p>
            )}
            <div className="flex flex-col gap-2">
              <Label htmlFor="participantName">Имя и фамилия / Команда</Label>
              <Input
                id="participantName"
                value={participantName}
                onChange={(e) => setParticipantName(e.target.value)}
                placeholder="Введите имя и фамилию или название команды"
                autoComplete="name"
                disabled={isLoadingMeta}
                required
              />
            </div>
            {startError && (
              <p className="text-sm text-destructive">{startError}</p>
            )}
            <Button
              type="button"
              className={cn("mt-2 w-full", ACCENT_BUTTON_CLASS)}
              disabled={!canStart || isStarting || isLoadingMeta}
              onClick={handleStart}
            >
              {isStarting ? "Запуск…" : "Начать викторину"}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (stage === "result") {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 py-8">
        <Card className="w-full max-w-lg border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl sm:text-3xl">
              {participantName.trim()}, ваш результат
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-center text-lg">
            <p>
              <span className="font-semibold">Баллы:</span> {score} из{" "}
              {maxScore}
            </p>
            <p>
              <span className="font-semibold">Затраченное время:</span>{" "}
              {formatElapsed(elapsedSeconds)}
            </p>
            <p>
              <span className="font-semibold">Номер попытки:</span>{" "}
              {attemptNumber}
            </p>
            <p className="text-sm text-muted-foreground">
              Попытка {attemptNumber} из {quiz.attempts}
            </p>

            {apiError && (
              <p className="text-sm text-destructive">{apiError}</p>
            )}

            <div className="mt-4 flex flex-col gap-3">
              {hasAttemptsLeft && (
                <Button
                  type="button"
                  className={cn("w-full", ACCENT_BUTTON_CLASS)}
                  disabled={isStarting}
                  onClick={handleRetry}
                >
                  {isStarting ? "Запуск…" : "Пройти ещё раз"}
                </Button>
              )}
              <Button
                type="button"
                variant="secondary"
                className="w-full"
                onClick={() => console.log("Результат передан учителю")}
              >
                {hasAttemptsLeft ? "Закрыть" : "Результат передан учителю"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!currentQuestion) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <p className="text-xl text-muted-foreground">
          {totalQuestions === 0 ? "Нет вопросов" : "Завершение викторины…"}
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto min-h-screen max-w-3xl px-4 py-6 sm:px-8">
      {apiError && (
        <p className="mb-4 text-sm text-destructive">{apiError}</p>
      )}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {quiz.totalTimer > 0 && (
          <div className="rounded-lg border-2 border-quiz-card-border bg-white/90 px-3 py-1.5 text-sm font-medium sm:text-base">
            Общее время: {formatTimer(totalTimeLeft)}
          </div>
        )}
        <p className="text-base font-medium text-muted-foreground sm:text-lg">
          Попытка {attemptNumber} из {quiz.attempts}
        </p>
        {quiz.timerPerQuestion > 0 && (
          <div className="rounded-lg border-2 border-quiz-card-border bg-white/90 px-3 py-1.5 text-sm font-medium sm:text-base">
            На вопрос: {formatTimer(questionTimeLeft)}
          </div>
        )}
      </div>

      <p className="mb-4 text-center text-lg text-muted-foreground sm:text-xl">
        Вопрос {questionIndex + 1} / {totalQuestions}
      </p>

      <Card className="border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
        <CardContent className="flex flex-col gap-5 pt-6">
          <h2 className="text-xl font-semibold leading-snug sm:text-2xl">
            {currentQuestion.text}
          </h2>

          <div className="flex flex-col gap-3">
            {currentQuestion.options.map((option) => {
              const isSelected = selectedIds.includes(option.id)
              return (
                <Button
                  key={option.id}
                  type="button"
                  variant="outline"
                  disabled={hasSubmitted}
                  onClick={() => toggleOption(option.id)}
                  className={cn(
                    "min-h-14 w-full justify-start rounded-xl border-2 border-quiz-card-border bg-white px-5 py-3 text-left text-base font-medium transition-colors hover:bg-quiz-card-border/15 sm:min-h-16 sm:text-lg",
                    isSelected &&
                      "border-quiz-accent bg-quiz-accent/10 ring-2 ring-quiz-accent/30"
                  )}
                >
                  {option.text}
                </Button>
              )
            })}
          </div>

          {!hasSubmitted && (
            <Button
              type="button"
              className={cn("w-full", ACCENT_BUTTON_CLASS)}
              disabled={selectedIds.length === 0}
              onClick={handleSubmit}
            >
              Отправить ответ
            </Button>
          )}

          {hasSubmitted && (
            <Button
              type="button"
              className={cn("w-full", NEXT_BUTTON_CLASS)}
              onClick={handleNext}
            >
              {isLastQuestion ? "Завершить викторину" : "Следующий вопрос"}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
