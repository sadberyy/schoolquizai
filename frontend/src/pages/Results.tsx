import { useEffect, useMemo, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Loader2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  API_BASE_URL,
  getQuizHeatmap,
  type QuizHeatmapData,
} from "@/lib/api"
import { truncateDisplayName } from "@/lib/displayText"
import { resolveFolderBackUrl } from "@/lib/navigation"
import { authFetch, downloadAuthenticatedFile } from "@/lib/auth"
import { buildDownloadFilename } from "@/lib/downloadFilename"
import { mapResultsFromApi, readApiError } from "@/lib/quizApi"
import { cn } from "@/lib/utils"
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
  const { quizId: routeQuizId } = useParams<{ quizId: string }>()
  const [searchParams] = useSearchParams()
  const folderIdFromUrl = searchParams.get("folder_id")

  const [quizTitle, setQuizTitle] = useState(quizData?.title ?? "Викторина")
  const [quizFolderId, setQuizFolderId] = useState<string | null>(
    quizData?.folderId ?? null
  )
  const [fallbackMaxScore, setFallbackMaxScore] = useState(
    quizData?.maxScore ?? 0
  )
  const [rawResults, setRawResults] = useState<StudentResult[]>(
    results ?? []
  )
  const [isLoading, setIsLoading] = useState(Boolean(routeQuizId && !results))
  const [loadError, setLoadError] = useState("")
  const [exportError, setExportError] = useState("")
  const [isExportingPdf, setIsExportingPdf] = useState(false)

  const [heatmap, setHeatmap] = useState<QuizHeatmapData | null>(null)
  const [heatmapLoading, setHeatmapLoading] = useState(false)
  const [heatmapError, setHeatmapError] = useState("")

  const [sortKey, setSortKey] = useState<SortKey>("score")
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc")

  useEffect(() => {
    if (!routeQuizId || results) return

    let ignore = false

    async function load() {
      setIsLoading(true)
      setLoadError("")

      try {
        const [quizRes, resultsRes] = await Promise.all([
          authFetch(`${API_BASE_URL}/quiz/${routeQuizId}`),
          authFetch(`${API_BASE_URL}/quiz/${routeQuizId}/results`),
        ])

        if (!quizRes.ok) {
          throw new Error(
            await readApiError(quizRes, "Не удалось загрузить викторину")
          )
        }
        if (!resultsRes.ok) {
          throw new Error(
            await readApiError(resultsRes, "Не удалось загрузить результаты")
          )
        }

        const quizJson = (await quizRes.json()) as {
          title?: string
          folder_id?: string | null
          questions?: { points?: number }[]
        }
        const resultsJson = (await resultsRes.json()) as {
          results?: import("@/lib/quizApi").ApiQuizResultRow[]
        }

        if (ignore) return

        setQuizTitle(quizJson.title ?? "Викторина")
        setQuizFolderId(quizJson.folder_id ?? null)

        const computedMax = (quizJson.questions ?? []).reduce(
          (sum, q) => sum + (Number(q.points) || 0),
          0
        )
        setFallbackMaxScore(computedMax)

        setRawResults(mapResultsFromApi(resultsJson.results ?? []))
      } catch (err) {
        if (ignore) return
        setLoadError(
          err instanceof Error ? err.message : "Не удалось загрузить данные"
        )
      } finally {
        if (!ignore) setIsLoading(false)
      }
    }

    void load()

    return () => {
      ignore = true
    }
  }, [routeQuizId, results])

  useEffect(() => {
    if (!routeQuizId) return

    let ignore = false

    async function loadHeatmap() {
      setHeatmapLoading(true)
      setHeatmapError("")
      try {
        const data = await getQuizHeatmap(routeQuizId)
        if (!ignore) setHeatmap(data)
      } catch (err) {
        if (!ignore) {
          setHeatmapError(
            err instanceof Error
              ? err.message
              : "Не удалось загрузить тепловую карту"
          )
        }
      } finally {
        if (!ignore) setHeatmapLoading(false)
      }
    }

    void loadHeatmap()

    return () => {
      ignore = true
    }
  }, [routeQuizId])

  const maxScore = useMemo(() => {
    const fromResults = rawResults.find((r) => r.maxScore > 0)?.maxScore
    if (fromResults) return fromResults
    if (fallbackMaxScore > 0) return fallbackMaxScore
    return 1
  }, [rawResults, fallbackMaxScore])

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

  const handleDownloadPdf = async () => {
    if (!routeQuizId) {
      setExportError("Не указан идентификатор викторины")
      return
    }

    setExportError("")
    setIsExportingPdf(true)
    const params = new URLSearchParams({
      sort_by: sortKey,
      sort_dir: sortDirection,
    })
    try {
      await downloadAuthenticatedFile(
        `${API_BASE_URL}/quiz/${routeQuizId}/results/export?${params.toString()}`,
        buildDownloadFilename(quizTitle, "pdf", { suffix: "_результаты" })
      )
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Не удалось скачать PDF")
    } finally {
      setIsExportingPdf(false)
    }
  }

  const headerButtonClass =
    "inline-flex items-center gap-1.5 font-semibold hover:text-quiz-accent"

  const backToDashboard = resolveFolderBackUrl(folderIdFromUrl, quizFolderId)

  const heatmapStudentNames = useMemo(() => {
    if (!heatmap) return []
    return heatmap.students.map((s) => s.name)
  }, [heatmap])

  function getSuccessRateColor(rate: number): string {
    if (rate > 70) return "text-green-700"
    if (rate >= 50) return "text-yellow-600"
    return "text-red-600"
  }

  function getCellStyle(isCorrect: boolean | null): string {
    if (isCorrect === true) return "bg-[#86efac]"
    if (isCorrect === false) return "bg-[#fca5a5]"
    return "bg-[#e5e7eb]"
  }

  function truncateQuestion(text: string, max = 150): string {
    const trimmed = text.trim()
    if (trimmed.length <= max) return trimmed
    return `${trimmed.slice(0, max)}...`
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <Button asChild variant="ghost" size="sm" className="lf-back-btn mb-4 -ml-2">
        <Link to={backToDashboard}>Назад</Link>
      </Button>

      {isLoading && (
        <p className="mb-4 text-sm text-muted-foreground">Загрузка...</p>
      )}
      {loadError && (
        <p className="mb-4 text-sm text-destructive">{loadError}</p>
      )}
      {exportError && (
        <p className="mb-4 text-sm text-destructive">{exportError}</p>
      )}
      {isExportingPdf && (
        <p className="mb-4 text-sm text-muted-foreground" role="status" aria-live="polite">
          Идёт формирование PDF с результатами… Подождите, пожалуйста.
        </p>
      )}

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="min-w-0 break-words text-2xl font-bold sm:text-3xl [overflow-wrap:anywhere]">
            {truncateDisplayName(quizTitle)}
          </h1>
          <p className="lf-text mt-2 text-lg text-muted-foreground">
            Результаты учеников
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={() => void handleDownloadPdf()}
          disabled={isLoading || isExportingPdf}
          className="shrink-0"
        >
          {isExportingPdf ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Формирование PDF…
            </>
          ) : (
            "Скачать PDF"
          )}
        </Button>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card className={cn(CARD_CLASS, "lf-stat-card")}>
          <CardHeader className="pb-2">
            <CardTitle className="lf-text text-base font-medium text-muted-foreground">
              Средний балл
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="lf-text text-3xl font-bold">
              {averageScore}{" "}
              <span className="text-lg font-normal text-muted-foreground">
                из {maxScore}
              </span>
            </p>
          </CardContent>
        </Card>
        <Card className={cn(CARD_CLASS, "lf-stat-card")}>
          <CardHeader className="pb-2">
            <CardTitle className="lf-text text-base font-medium text-muted-foreground">
              Всего учеников
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="lf-text text-3xl font-bold">{normalizedResults.length}</p>
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
                      Имя и фамилия / Команда
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

      <Card className={cn(CARD_CLASS, "lf-heatmap-section mt-6")}>
        <CardHeader>
          <CardTitle className="lf-text text-xl font-semibold">
            Анализ сложности вопросов
          </CardTitle>
          <p className="lf-text lf-heatmap-desc text-sm text-muted-foreground">
            Тепловая карта ошибок по вопросам и ученикам
          </p>
        </CardHeader>
        <CardContent>
          {heatmapLoading && (
            <p className="text-sm text-muted-foreground">Загрузка карты…</p>
          )}
          {heatmapError && (
            <p className="text-sm text-destructive">{heatmapError}</p>
          )}
          {heatmap && heatmap.questions.length === 0 && !heatmapLoading && (
            <p className="text-sm text-muted-foreground">
              Недостаточно данных для построения карты
            </p>
          )}
          {heatmap && heatmap.questions.length > 0 && (
            <div className="flex flex-col gap-6 xl:flex-row">
              <div className="min-w-0 flex-1 overflow-x-auto">
                <table className="w-full min-w-[480px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-quiz-card-border">
                      <th className="sticky left-0 z-10 bg-white px-2 py-2 text-left font-medium">
                        №
                      </th>
                      {heatmapStudentNames.map((name) => (
                        <th
                          key={name}
                          className="max-w-[8rem] truncate px-2 py-2 text-center text-xs font-medium"
                          title={name}
                        >
                          {name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {heatmap.questions.map((question) => {
                      const studentMap = new Map(
                        question.students.map((s) => [s.student_name, s.is_correct])
                      )
                      return (
                        <tr
                          key={question.question_id}
                          className="border-b border-quiz-card-border/40"
                        >
                          <td className="sticky left-0 z-10 bg-white px-2 py-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="cursor-help font-medium underline decoration-dotted">
                                  {(question.order_idx ?? 0) + 1}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent
                                side="right"
                                className="lf-tooltip max-w-sm text-sm"
                              >
                                {truncateQuestion(question.question_text)}
                              </TooltipContent>
                            </Tooltip>
                          </td>
                          {heatmapStudentNames.map((name) => {
                            const answered = studentMap.has(name)
                            const isCorrect = answered
                              ? studentMap.get(name)!
                              : null
                            return (
                              <td key={`${question.question_id}-${name}`} className="p-1">
                                <div
                                  className={cn(
                                    "mx-auto flex size-8 items-center justify-center rounded-md",
                                    getCellStyle(isCorrect)
                                  )}
                                  title={
                                    isCorrect === true
                                      ? "Правильно"
                                      : isCorrect === false
                                        ? "Неправильно"
                                        : "Нет ответа"
                                  }
                                >
                                  {isCorrect === true && (
                                    <Check className="size-4 text-green-900" />
                                  )}
                                  {isCorrect === false && (
                                    <X className="size-4 text-red-900" />
                                  )}
                                </div>
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="lf-heatmap-stats w-full shrink-0 xl:w-64">
                <p className="lf-text mb-3 text-sm font-medium text-muted-foreground">
                  % успешных ответов
                </p>
                <ul className="flex flex-col gap-2">
                  {heatmap.questions.map((question) => (
                    <li
                      key={`stat-${question.question_id}`}
                      className="lf-text flex items-center justify-between gap-2 text-sm"
                    >
                      <span className="font-medium">
                        Вопрос {(question.order_idx ?? 0) + 1}
                      </span>
                      <span
                        className={cn(
                          "font-semibold tabular-nums",
                          getSuccessRateColor(question.success_rate)
                        )}
                      >
                        {question.total_answers > 0
                          ? `${question.success_rate}%`
                          : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
