import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Check, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { MOCK_QUIZ_DATA } from "@/pages/EditQuiz"
import type { QuestionType, QuizData, QuizQuestion } from "@/types/quiz"

export type { QuizData } from "@/types/quiz"

export interface TeacherShowProps {
  quizData?: QuizData
}

const QUESTION_TYPE_HINTS: Record<QuestionType, string> = {
  single: "Одиночный выбор",
  multiple: "Множественный выбор — можно выбрать несколько",
  trueFalse: "True / False",
}

const ACCENT_BUTTON_CLASS =
  "h-14 border-transparent bg-quiz-accent text-lg text-white hover:bg-quiz-accent/90"
const NEXT_BUTTON_CLASS =
  "h-14 border-2 border-quiz-card-border bg-quiz-card-border text-lg text-white hover:bg-quiz-card-border/90"

function normalizeQuizData(data: QuizData): QuizData {
  return {
    ...data,
    title: data.title ?? "Викторина",
    questions: data.questions?.length ? data.questions : MOCK_QUIZ_DATA.questions,
  }
}

export default function TeacherShow({ quizData }: TeacherShowProps) {
  const quiz = useMemo(
    () => normalizeQuizData(quizData ?? MOCK_QUIZ_DATA),
    [quizData]
  )

  const [questionIndex, setQuestionIndex] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [isRevealed, setIsRevealed] = useState(false)

  const totalQuestions = quiz.questions.length
  const currentQuestion: QuizQuestion | undefined = quiz.questions[questionIndex]
  const isLastQuestion = questionIndex >= totalQuestions - 1

  useEffect(() => {
    setSelectedIds([])
    setIsRevealed(false)
  }, [questionIndex])

  const toggleOption = (optionId: string) => {
    if (isRevealed || !currentQuestion) return

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
    if (selectedIds.length === 0) return
    setIsRevealed(true)
  }

  const handleNext = () => {
    if (!isLastQuestion) {
      setQuestionIndex((i) => i + 1)
    }
  }

  const getOptionClassName = (optionId: string, isCorrect: boolean) => {
    const isSelected = selectedIds.includes(optionId)

    if (!isRevealed) {
      return cn(
        "min-h-16 w-full justify-start rounded-xl border-2 border-quiz-card-border bg-white px-6 py-4 text-left text-lg font-medium transition-colors hover:bg-quiz-card-border/15",
        isSelected && "border-quiz-accent bg-quiz-accent/10 ring-2 ring-quiz-accent/30"
      )
    }

    if (isCorrect) {
      return cn(
        "min-h-16 w-full justify-start rounded-xl border-2 border-green-600 bg-green-100 px-6 py-4 text-left text-lg font-medium text-green-900"
      )
    }

    if (isSelected) {
      return cn(
        "min-h-16 w-full justify-start rounded-xl border-2 border-red-600 bg-red-100 px-6 py-4 text-left text-lg font-medium text-red-900"
      )
    }

    return cn(
      "min-h-16 w-full justify-start rounded-xl border-2 border-quiz-card-border/50 bg-white/80 px-6 py-4 text-left text-lg font-medium text-muted-foreground"
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
        className="absolute top-4 left-4 text-muted-foreground"
      >
        <Link to="/">Выйти</Link>
      </Button>

      <header className="mb-8 pt-8 text-center sm:pt-0 sm:pr-0">
        <h1 className="text-2xl font-bold sm:text-3xl">{quiz.title}</h1>
        <p className="mt-2 text-lg text-muted-foreground sm:text-xl">
          Вопрос {questionIndex + 1} / {totalQuestions}
        </p>
      </header>

      <main className="flex flex-col gap-6">
        <Card className="border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
          <CardContent className="flex flex-col gap-6 pt-6">
            <div>
              <p className="text-sm font-medium text-muted-foreground sm:text-base">
                {QUESTION_TYPE_HINTS[currentQuestion.type]}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Вопрос {questionIndex + 1}
              </p>
              <h2 className="mt-3 text-xl font-semibold leading-snug sm:text-2xl">
                {currentQuestion.text}
              </h2>
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
                    className={getOptionClassName(option.id, option.isCorrect)}
                  >
                    <span className="flex w-full items-center justify-between gap-4">
                      <span>{option.text}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        {showCheck && (
                          <Check className="size-6 text-green-700" aria-hidden />
                        )}
                        {showCross && (
                          <X className="size-6 text-red-700" aria-hidden />
                        )}
                      </span>
                    </span>
                  </Button>
                )
              })}
            </div>

            {!isRevealed && (
              <Button
                type="button"
                className={cn("w-full", ACCENT_BUTTON_CLASS)}
                disabled={selectedIds.length === 0}
                onClick={handleSubmit}
              >
                Отправить ответ
              </Button>
            )}

            {isRevealed && currentQuestion.explanation.trim() && (
              <Card className="border border-quiz-card-border/60 bg-muted/40 shadow-none">
                <CardContent className="pt-4">
                  <p className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Пояснение
                  </p>
                  <p className="text-lg leading-relaxed">
                    {currentQuestion.explanation}
                  </p>
                </CardContent>
              </Card>
            )}

            {isRevealed && !isLastQuestion && (
              <Button
                type="button"
                className={cn("w-full", NEXT_BUTTON_CLASS)}
                onClick={handleNext}
              >
                Следующий вопрос
              </Button>
            )}

            {isRevealed && isLastQuestion && (
              <p className="text-center text-lg font-medium text-muted-foreground">
                Это был последний вопрос
              </p>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
