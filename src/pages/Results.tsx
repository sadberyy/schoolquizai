import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { getTotalMaxScore, MOCK_QUIZ_DATA } from "@/pages/EditQuiz"
import type { QuizData } from "@/types/quiz"

export type { QuizData } from "@/types/quiz"

export interface StudentResult {
  id?: string
  firstName: string
  lastName: string
  fullName?: string
  score: number
  maxScore: number
  elapsedSeconds: number
  attemptNumber: number
  completedAt?: string
}

export interface ResultsProps {
  quizData?: QuizData
  results?: StudentResult[]
}

type SortKey = "name" | "score" | "time" | "attempt"
type SortDirection = "asc" | "desc"

const CARD_CLASS =
  "border-2 border-quiz-card-border bg-white/95 shadow-md ring-0"

export const MOCK_RESULTS: StudentResult[] = [
  {
    id: "r1",
    firstName: "Иван",
    lastName: "Петров",
    score: 7,
    maxScore: 10,
    elapsedSeconds: 272,
    attemptNumber: 2,
    completedAt: "2026-05-20T10:15:00Z",
  },
  {
    id: "r2",
    firstName: "Мария",
    lastName: "Сидорова",
    score: 10,
    maxScore: 10,
    elapsedSeconds: 198,
    attemptNumber: 1,
    completedAt: "2026-05-20T10:22:00Z",
  },
  {
    id: "r3",
    firstName: "Алексей",
    lastName: "Козлов",
    score: 5,
    maxScore: 10,
    elapsedSeconds: 340,
    attemptNumber: 3,
    completedAt: "2026-05-20T10:30:00Z",
  },
  {
    id: "r4",
    firstName: "Елена",
    lastName: "Новикова",
    score: 8,
    maxScore: 10,
    elapsedSeconds: 245,
    attemptNumber: 1,
    completedAt: "2026-05-20T10:35:00Z",
  },
  {
    id: "r5",
    firstName: "Дмитрий",
    lastName: "Волков",
    score: 6,
    maxScore: 10,
    elapsedSeconds: 301,
    attemptNumber: 2,
    completedAt: "2026-05-20T10:40:00Z",
  },
]

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m} мин ${s} сек`
}

function getDisplayName(result: StudentResult): string {
  return (
    result.fullName?.trim() ||
    `${result.firstName.trim()} ${result.lastName.trim()}`.trim()
  )
}

function normalizeResults(results: StudentResult[]): StudentResult[] {
  return results.map((r) => ({
    ...r,
    fullName: getDisplayName(r),
  }))
}

function compareResults(
  a: StudentResult,
  b: StudentResult,
  key: SortKey,
  direction: SortDirection
): number {
  let cmp = 0

  switch (key) {
    case "name":
      cmp = getDisplayName(a).localeCompare(getDisplayName(b), "ru")
      break
    case "score":
      cmp = a.score - b.score
      break
    case "time":
      cmp = a.elapsedSeconds - b.elapsedSeconds
      break
    case "attempt":
      cmp = a.attemptNumber - b.attemptNumber
      break
  }

  return direction === "asc" ? cmp : -cmp
}

function SortIcon({
  column,
  sortKey,
  sortDirection,
}: {
  column: SortKey
  sortKey: SortKey
  sortDirection: SortDirection
}) {
  if (sortKey !== column) {
    return <ArrowUpDown className="size-4 opacity-40" />
  }
  return sortDirection === "asc" ? (
    <ArrowUp className="size-4" />
  ) : (
    <ArrowDown className="size-4" />
  )
}

export default function Results({ quizData, results }: ResultsProps) {
  const quiz = quizData ?? MOCK_QUIZ_DATA
  const rawResults = results ?? MOCK_RESULTS
  const maxScore =
    quiz.maxScore > 0
      ? quiz.maxScore
      : rawResults[0]?.maxScore ?? getTotalMaxScore(quiz.questions)

  const [sortKey, setSortKey] = useState<SortKey>("score")
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc")

  const normalizedResults = useMemo(
    () => normalizeResults(rawResults),
    [rawResults]
  )

  const sortedResults = useMemo(
    () =>
      [...normalizedResults].sort((a, b) =>
        compareResults(a, b, sortKey, sortDirection)
      ),
    [normalizedResults, sortKey, sortDirection]
  )

  const averageScore = useMemo(() => {
    if (normalizedResults.length === 0) return 0
    const sum = normalizedResults.reduce((acc, r) => acc + r.score, 0)
    return Math.round((sum / normalizedResults.length) * 10) / 10
  }, [normalizedResults])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortKey(key)
      setSortDirection(key === "name" ? "asc" : "desc")
    }
  }

  const handleDownloadPdf = () => {
    console.log("Скачать PDF", {
      quizTitle: quiz.title,
      results: sortedResults,
      averageScore,
      totalStudents: normalizedResults.length,
    })
  }

  const headerButtonClass =
    "inline-flex items-center gap-1.5 font-semibold hover:text-quiz-accent"

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2">
        <Link to="/">Назад</Link>
      </Button>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">{quiz.title}</h1>
          <p className="mt-2 text-lg text-muted-foreground">
            Результаты учеников
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={handleDownloadPdf}
          className="shrink-0"
        >
          Скачать PDF
        </Button>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card className={CARD_CLASS}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium text-muted-foreground">
              Средний балл
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {averageScore}{" "}
              <span className="text-lg font-normal text-muted-foreground">
                из {maxScore}
              </span>
            </p>
          </CardContent>
        </Card>
        <Card className={CARD_CLASS}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium text-muted-foreground">
              Всего учеников
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{normalizedResults.length}</p>
          </CardContent>
        </Card>
      </div>

      <Card className={cn(CARD_CLASS, "overflow-hidden")}>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-left text-base">
              <thead>
                <tr className="border-b-2 border-quiz-card-border bg-muted/40">
                  <th className="px-4 py-3 sm:px-6">
                    <button
                      type="button"
                      onClick={() => handleSort("name")}
                      className={headerButtonClass}
                    >
                      Имя и фамилия
                      <SortIcon
                        column="name"
                        sortKey={sortKey}
                        sortDirection={sortDirection}
                      />
                    </button>
                  </th>
                  <th className="px-4 py-3 sm:px-6">
                    <button
                      type="button"
                      onClick={() => handleSort("score")}
                      className={headerButtonClass}
                    >
                      Баллы
                      <SortIcon
                        column="score"
                        sortKey={sortKey}
                        sortDirection={sortDirection}
                      />
                    </button>
                  </th>
                  <th className="px-4 py-3 sm:px-6">
                    <button
                      type="button"
                      onClick={() => handleSort("time")}
                      className={headerButtonClass}
                    >
                      Затраченное время
                      <SortIcon
                        column="time"
                        sortKey={sortKey}
                        sortDirection={sortDirection}
                      />
                    </button>
                  </th>
                  <th className="px-4 py-3 sm:px-6">
                    <button
                      type="button"
                      onClick={() => handleSort("attempt")}
                      className={headerButtonClass}
                    >
                      Номер попытки
                      <SortIcon
                        column="attempt"
                        sortKey={sortKey}
                        sortDirection={sortDirection}
                      />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-6 py-12 text-center text-muted-foreground"
                    >
                      Пока нет результатов
                    </td>
                  </tr>
                ) : (
                  sortedResults.map((result, index) => (
                    <tr
                      key={result.id ?? `${result.firstName}-${result.lastName}-${index}`}
                      className="border-b border-quiz-card-border/40 transition-colors hover:bg-muted/20"
                    >
                      <td className="px-4 py-4 font-medium sm:px-6">
                        {getDisplayName(result)}
                      </td>
                      <td className="px-4 py-4 sm:px-6">
                        {result.score}/{result.maxScore || maxScore}
                      </td>
                      <td className="px-4 py-4 sm:px-6">
                        {formatElapsed(result.elapsedSeconds)}
                      </td>
                      <td className="px-4 py-4 sm:px-6">
                        {result.attemptNumber}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
