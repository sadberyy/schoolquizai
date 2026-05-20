import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Trash2 } from "lucide-react"

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
import { cn } from "@/lib/utils"
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

export const MOCK_QUIZ_DATA: QuizData = {
  id: "quiz-mock-001",
  title: "Викторина по биологии — Клетка",
  difficulty: "Средне",
  attempts: 3,
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
    options = createTrueFalseOptions().map((def, i) => ({
      ...def,
      id: options[i]?.id ?? def.id,
      isCorrect: options[i]?.isCorrect ?? def.isCorrect,
      points: options[i]?.points ?? def.points,
    }))
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

  return {
    id: data.id,
    title: data.title ?? "",
    difficulty,
    attempts: Math.max(1, Number(data.attempts) || 1),
    timerPerQuestion: Math.max(0, Number(data.timerPerQuestion) || 0),
    totalTimer: Math.max(0, Number(data.totalTimer) || 0),
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

export default function EditQuiz({
  quizData,
  onSave,
  onPublish,
}: EditQuizProps) {
  const [quiz, setQuiz] = useState<QuizData>(() =>
    normalizeQuizData(quizData ?? MOCK_QUIZ_DATA)
  )

  useEffect(() => {
    setQuiz(normalizeQuizData(quizData ?? MOCK_QUIZ_DATA))
  }, [quizData])

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

  const getPayload = useCallback(
    () => buildQuizPayload(quiz),
    [quiz]
  )

  const handleSave = () => {
    onSave?.(getPayload())
  }

  const handlePublish = async () => {
    const payload = getPayload()
    const link = `${window.location.origin}/quiz/${payload.id ?? "demo"}`
    try {
      await navigator.clipboard.writeText(link)
    } catch {
      // clipboard may be unavailable
    }
    onPublish?.(payload)
  }

  const parseNumberInput = (value: string, min: number, fallback: number) =>
    Math.max(min, Number(value) || fallback)

  return (
    <div className="mx-auto max-w-4xl px-4 pb-28 pt-8 sm:px-6 lg:px-8">
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2">
        <Link to="/">Назад</Link>
      </Button>

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
              <Label htmlFor="timerPerQuestion">
                Время на один вопрос (сек)
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

            <div className="flex flex-col gap-2">
              <Label htmlFor="totalTimer">Общее время (мин)</Label>
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
          <Card key={question.id} className={QUESTION_CARD_CLASS}>
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle className="text-base font-semibold">
                  Вопрос №{index + 1}
                </CardTitle>
                <Select
                  value={question.type}
                  onValueChange={(value) =>
                    handleTypeChange(question.id, value as QuestionType)
                  }
                >
                  <SelectTrigger
                    id={`type-${question.id}`}
                    className="w-[220px]"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    <SelectItem value="single">Одиночный выбор</SelectItem>
                    <SelectItem value="multiple">Множественный выбор</SelectItem>
                    <SelectItem value="trueFalse">True/False</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <p className="text-sm font-medium text-muted-foreground">
                Тип: {QUESTION_TYPE_LABELS[question.type]}
              </p>
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
                  <div
                    key={option.id}
                    className="flex flex-wrap items-center gap-2 sm:flex-nowrap"
                  >
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
                        className="size-4 shrink-0 accent-quiz-accent"
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
                      <span className="text-xs whitespace-nowrap text-muted-foreground">
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
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="fixed inset-x-0 bottom-0 z-50 border-t-2 border-quiz-card-border bg-white/95 px-4 py-3 shadow-lg backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-3 sm:justify-end">
          <Button
            type="button"
            className={cn(ACCENT_BUTTON_CLASS)}
            onClick={handleSave}
          >
            Сохранить черновик
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => console.log("Скачать PDF", getPayload())}
          >
            Скачать PDF
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={handlePublish}
          >
            Копировать ссылку для учеников
          </Button>
        </div>
      </div>
    </div>
  )
}
