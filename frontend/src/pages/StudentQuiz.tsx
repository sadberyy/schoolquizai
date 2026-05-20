import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { getTotalMaxScore, MOCK_QUIZ_DATA } from "@/pages/EditQuiz"
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

function normalizeQuizData(data: QuizData): QuizData {
  return {
    ...data,
    title: data.title ?? "Викторина",
    attempts: Math.max(1, Number(data.attempts) || 1),
    timerPerQuestion: Math.max(0, Number(data.timerPerQuestion) || 0),
    totalTimer: Math.max(0, Number(data.totalTimer) || 0),
    questions: data.questions?.length ? data.questions : MOCK_QUIZ_DATA.questions,
  }
}

function scoreAnswer(
  question: QuizQuestion,
  selectedIds: string[]
): number {
  if (selectedIds.length === 0) return 0

  if (question.type === "multiple") {
    const correctIds = question.options
      .filter((o) => o.isCorrect)
      .map((o) => o.id)
    const allCorrectSelected = correctIds.every((id) =>
      selectedIds.includes(id)
    )
    const noWrongSelected = selectedIds.every((id) =>
      correctIds.includes(id)
    )
    if (
      allCorrectSelected &&
      noWrongSelected &&
      selectedIds.length === correctIds.length
    ) {
      return question.options
        .filter((o) => o.isCorrect)
        .reduce((sum, o) => sum + o.points, 0)
    }
    return 0
  }

  if (selectedIds.length !== 1) return 0
  const selected = question.options.find((o) => o.id === selectedIds[0])
  return selected?.isCorrect ? selected.points : 0
}

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
  const quiz = useMemo(
    () => normalizeQuizData(quizData ?? MOCK_QUIZ_DATA),
    [quizData]
  )

  const maxScore = useMemo(
    () =>
      quiz.maxScore > 0 ? quiz.maxScore : getTotalMaxScore(quiz.questions),
    [quiz]
  )

  const [stage, setStage] = useState<Stage>("intro")
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
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
  const questionTimeoutHandledRef = useRef(-1)
  const onQuestionTimeExpiredRef = useRef<() => void>(() => {})

  const totalQuestions = quiz.questions.length
  const currentQuestion = quiz.questions[questionIndex]
  const isLastQuestion = questionIndex >= totalQuestions - 1
  const canStart = firstName.trim().length > 0 && lastName.trim().length > 0
  const hasAttemptsLeft = attemptNumber < quiz.attempts

  useEffect(() => {
    questionIndexRef.current = questionIndex
  }, [questionIndex])

  const recordAnswer = useCallback(
    (question: QuizQuestion, optionIds: string[]) => {
      const points = scoreAnswer(question, optionIds)
      setScore((s) => s + points)
      setAnswers((prev) => [
        ...prev,
        {
          questionId: question.id,
          selectedOptionIds: optionIds,
          pointsEarned: points,
        },
      ])
    },
    []
  )

  const finishQuiz = useCallback(() => {
    const q = quiz.questions[questionIndexRef.current]
    if (q && !hasSubmittedRef.current) {
      recordAnswer(q, [])
      hasSubmittedRef.current = true
    }
    setStage("result")
  }, [quiz.questions, recordAnswer])

  const buildResult = useCallback(
    (): QuizResultData => ({
      quizId: quiz.id,
      firstName: firstName.trim(),
      lastName: lastName.trim(),
      fullName: `${firstName.trim()} ${lastName.trim()}`,
      score,
      maxScore,
      elapsedSeconds,
      attemptNumber,
      maxAttempts: quiz.attempts,
      answers,
      completedAt: new Date().toISOString(),
    }),
    [
      quiz.id,
      quiz.attempts,
      firstName,
      lastName,
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

    const question = quiz.questions[index]
    if (!question) {
      finishQuiz()
      return
    }

    recordAnswer(question, [])

    if (index >= quiz.questions.length - 1) {
      finishQuiz()
      return
    }

    questionTimeoutHandledRef.current = -1
    setQuestionIndex(index + 1)
    setSelectedIds([])
    setHasSubmitted(false)
    hasSubmittedRef.current = false
  }, [quiz.questions, recordAnswer, finishQuiz])

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
    setQuestionTimeLeft(quiz.timerPerQuestion)
    setTotalTimeLeft(quiz.totalTimer * 60)
    completeSentForAttempt.current = 0
    questionTimeoutHandledRef.current = -1
  }, [quiz.timerPerQuestion, quiz.totalTimer])

  const handleStart = () => {
    resetQuizSession()
    setStage("quiz")
  }

  const handleRetry = () => {
    setAttemptNumber((n) => n + 1)
    resetQuizSession()
    setStage("quiz")
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
    recordAnswer(currentQuestion, [...selectedIds])
    setHasSubmitted(true)
    hasSubmittedRef.current = true
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
          finishQuiz()
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
      finishQuiz()
    }
  }, [stage, questionIndex, totalQuestions, finishQuiz])

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
            <div className="flex flex-col gap-2">
              <Label htmlFor="firstName">Имя</Label>
              <Input
                id="firstName"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Введите имя"
                autoComplete="given-name"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="lastName">Фамилия</Label>
              <Input
                id="lastName"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Введите фамилию"
                autoComplete="family-name"
              />
            </div>
            <Button
              type="button"
              className={cn("mt-2 w-full", ACCENT_BUTTON_CLASS)}
              disabled={!canStart}
              onClick={handleStart}
            >
              Начать викторину
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
              {firstName.trim()} {lastName.trim()}, ваш результат
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

            <div className="mt-4 flex flex-col gap-3">
              {hasAttemptsLeft && (
                <Button
                  type="button"
                  className={cn("w-full", ACCENT_BUTTON_CLASS)}
                  onClick={handleRetry}
                >
                  Пройти ещё раз
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
