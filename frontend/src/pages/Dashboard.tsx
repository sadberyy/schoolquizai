import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import type { User } from "@/types/user"
import {
  ArrowLeft,
  BarChart3,
  Folder,
  Pencil,
  Presentation,
  Search,
  Trash2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { loginUser, registerUser } from "@/lib/auth"
import {
  createFolder,
  deleteFolder,
  deleteQuiz,
  getFolders,
  listQuizzesInFolder,
  loadAllQuizzesForSearch,
  renameFolder,
  type QuizFolder,
  type QuizListItem,
  type QuizSearchItem,
} from "@/lib/api"
import { formatFolderDisplayName, truncateDisplayName } from "@/lib/displayText"
import {
  filterQuizzes,
  normalizeSearchQuery,
} from "@/lib/filterQuizzes"
import { cn } from "@/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export type { User } from "@/types/user"

export interface DashboardQuiz {
  id: string
  title: string
}

export interface DashboardProps {
  user: User | null
  quizzes?: DashboardQuiz[]
  onLogin: (userData: User) => void
  onLogout: () => void
  onDeleteQuiz: (quizId: string) => void
}

const CARD_CLASS =
  "border-2 border-quiz-card-border bg-white/95 shadow-md ring-0"
const ACCENT_BUTTON_CLASS =
  "border-transparent bg-quiz-accent text-white hover:bg-quiz-accent/90"

export default function Dashboard({
  user,
  onLogin,
  onLogout,
  onDeleteQuiz,
}: DashboardProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const folderIdFromUrl = searchParams.get("folder_id")
  const [searchQuery, setSearchQuery] = useState(
    () => searchParams.get("q") ?? ""
  )
  const [allQuizzesCache, setAllQuizzesCache] = useState<
    QuizSearchItem[] | null
  >(null)
  const [allQuizzesLoading, setAllQuizzesLoading] = useState(false)
  const [allQuizzesError, setAllQuizzesError] = useState("")

  const [folders, setFolders] = useState<QuizFolder[]>([])
  const [foldersLoading, setFoldersLoading] = useState(false)
  const [foldersError, setFoldersError] = useState("")

  const [activeFolderId, setActiveFolderId] = useState<string | null>(null)
  const [activeFolderName, setActiveFolderName] = useState("")

  const [quizzes, setQuizzes] = useState<QuizListItem[]>([])
  const [quizzesLoading, setQuizzesLoading] = useState(false)
  const [quizzesError, setQuizzesError] = useState("")
  const [deleteError, setDeleteError] = useState("")
  const [isDeletingQuizId, setIsDeletingQuizId] = useState<string | null>(null)

  const [showNewFolderInput, setShowNewFolderInput] = useState(false)
  const [newFolderName, setNewFolderName] = useState("")
  const [folderActionError, setFolderActionError] = useState("")
  const [renamingFolderId, setRenamingFolderId] = useState<string | null>(null)
  const [renameFolderValue, setRenameFolderValue] = useState("")
  const [isFolderActionLoading, setIsFolderActionLoading] = useState(false)
  const [folderToDelete, setFolderToDelete] = useState<QuizFolder | null>(null)

  const [loginEmail, setLoginEmail] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [registerName, setRegisterName] = useState("")
  const [registerEmail, setRegisterEmail] = useState("")
  const [registerPassword, setRegisterPassword] = useState("")
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState("")

  const [loginError, setLoginError] = useState("")
  const [registerNameError, setRegisterNameError] = useState("")
  const [registerEmailError, setRegisterEmailError] = useState("")
  const [registerPasswordError, setRegisterPasswordError] = useState("")
  const [registerConfirmError, setRegisterConfirmError] = useState("")
  const [registerGeneralError, setRegisterGeneralError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const isInsideFolder = Boolean(activeFolderId)
  const trimmedSearchQuery = normalizeSearchQuery(searchQuery)
  const isGlobalSearchActive =
    !isInsideFolder && trimmedSearchQuery.length > 0
  const isFolderSearchActive =
    isInsideFolder && trimmedSearchQuery.length > 0

  const filteredFolderQuizzes = useMemo(
    () => filterQuizzes(quizzes, searchQuery),
    [quizzes, searchQuery]
  )
  const filteredGlobalQuizzes = useMemo(
    () =>
      filterQuizzes(allQuizzesCache ?? [], searchQuery, (q) => q.folderName),
    [allQuizzesCache, searchQuery]
  )
  const displayedFolderQuizzes = isFolderSearchActive
    ? filteredFolderQuizzes
    : quizzes

  const loadFolders = useCallback(async () => {
    setFoldersLoading(true)
    setFoldersError("")
    try {
      const list = await getFolders()
      setFolders(list)
      return list
    } catch (err) {
      setFoldersError(
        err instanceof Error ? err.message : "Не удалось загрузить папки"
      )
      return []
    } finally {
      setFoldersLoading(false)
    }
  }, [])

  const loadQuizzesInFolder = useCallback(async (folderId: string) => {
    setQuizzesLoading(true)
    setQuizzesError("")
    setDeleteError("")
    try {
      const list = await listQuizzesInFolder(folderId)
      setQuizzes(list)
    } catch (err) {
      setQuizzesError(
        err instanceof Error ? err.message : "Не удалось загрузить викторины"
      )
    } finally {
      setQuizzesLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!user) return
    void loadFolders()
  }, [user, loadFolders])

  useEffect(() => {
    const qFromUrl = searchParams.get("q") ?? ""
    setSearchQuery((prev) => (prev === qFromUrl ? prev : qFromUrl))
  }, [searchParams])

  useEffect(() => {
    if (!user || isInsideFolder) return
    if (!trimmedSearchQuery) {
      setAllQuizzesCache(null)
      setAllQuizzesError("")
      return
    }
    if (allQuizzesCache !== null) return

    let cancelled = false
    setAllQuizzesLoading(true)
    setAllQuizzesError("")
    void loadAllQuizzesForSearch()
      .then((list) => {
        if (!cancelled) setAllQuizzesCache(list)
      })
      .catch((err) => {
        if (!cancelled) {
          setAllQuizzesError(
            err instanceof Error ? err.message : "Не удалось выполнить поиск"
          )
        }
      })
      .finally(() => {
        if (!cancelled) setAllQuizzesLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [user, isInsideFolder, trimmedSearchQuery, allQuizzesCache])

  useEffect(() => {
    if (!user || !folderIdFromUrl) {
      if (!folderIdFromUrl) {
        setActiveFolderId(null)
        setActiveFolderName("")
      }
      return
    }

    setActiveFolderId(folderIdFromUrl)

    const folderFromList = folders.find((f) => f.id === folderIdFromUrl)
    if (folderFromList) {
      setActiveFolderName(folderFromList.name)
    }

    void loadQuizzesInFolder(folderIdFromUrl)
  }, [user, folderIdFromUrl, folders, loadQuizzesInFolder])

  const updateSearchInUrl = (value: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        const trimmed = value.trim()
        if (trimmed) next.set("q", trimmed)
        else next.delete("q")
        return next
      },
      { replace: true }
    )
  }

  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    updateSearchInUrl(value)
  }

  const openFolder = (folder: QuizFolder) => {
    setActiveFolderId(folder.id)
    setActiveFolderName(folder.name)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("folder_id", folder.id)
      return next
    })
  }

  const goBackToFolders = () => {
    setActiveFolderId(null)
    setActiveFolderName("")
    setQuizzes([])
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("folder_id")
      return next
    })
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginError("")
    setIsLoading(true)

    try {
      const loggedIn = await loginUser(loginEmail, loginPassword)
      onLogin(loggedIn)
    } catch (err) {
      setLoginError(
        err instanceof Error ? err.message : "Неверный email или пароль"
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setRegisterNameError("")
    setRegisterEmailError("")
    setRegisterPasswordError("")
    setRegisterConfirmError("")
    setRegisterGeneralError("")

    let hasError = false

    if (!registerName.trim()) {
      setRegisterNameError("Введите имя")
      hasError = true
    }
    if (!registerEmail.trim()) {
      setRegisterEmailError("Введите email")
      hasError = true
    }
    if (!registerPassword) {
      setRegisterPasswordError("Введите пароль")
      hasError = true
    }
    if (registerPassword !== registerPasswordConfirm) {
      setRegisterConfirmError("Пароли не совпадают")
      hasError = true
    }
    if (hasError) return

    setIsLoading(true)

    try {
      const registered = await registerUser(
        registerName,
        registerEmail,
        registerPassword
      )
      onLogin(registered)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось зарегистрироваться"
      if (message.includes("email")) {
        setRegisterEmailError(message)
      } else {
        setRegisterGeneralError(message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogout = () => {
    setLoginEmail("")
    setLoginPassword("")
    onLogout()
  }

  const handleCreateFolder = async () => {
    const name = newFolderName.trim()
    if (!name) return

    setFolderActionError("")
    setIsFolderActionLoading(true)
    try {
      await createFolder(name)
      setNewFolderName("")
      setShowNewFolderInput(false)
      await loadFolders()
    } catch (err) {
      setFolderActionError(
        err instanceof Error ? err.message : "Не удалось создать папку"
      )
    } finally {
      setIsFolderActionLoading(false)
    }
  }

  const startRenameFolder = (folder: QuizFolder, e: React.MouseEvent) => {
    e.stopPropagation()
    setRenamingFolderId(folder.id)
    setRenameFolderValue(folder.name)
    setFolderActionError("")
  }

  const submitRenameFolder = async (folderId: string) => {
    const name = renameFolderValue.trim()
    if (!name) return

    setIsFolderActionLoading(true)
    setFolderActionError("")
    try {
      await renameFolder(folderId, name)
      setRenamingFolderId(null)
      const list = await loadFolders()
      if (activeFolderId === folderId) {
        const updated = list.find((f) => f.id === folderId)
        if (updated) setActiveFolderName(updated.name)
      }
    } catch (err) {
      setFolderActionError(
        err instanceof Error ? err.message : "Не удалось переименовать папку"
      )
    } finally {
      setIsFolderActionLoading(false)
    }
  }

  const handleDeleteFolder = (folder: QuizFolder, e: React.MouseEvent) => {
    e.stopPropagation()
    setFolderActionError("")
    setFolderToDelete(folder)
  }

  const confirmDeleteFolder = async () => {
    if (!folderToDelete) return

    setFolderActionError("")
    setIsFolderActionLoading(true)
    try {
      await deleteFolder(folderToDelete.id)
      if (activeFolderId === folderToDelete.id) {
        goBackToFolders()
      }
      setAllQuizzesCache(null)
      setFolderToDelete(null)
      await loadFolders()
    } catch (err) {
      setFolderActionError(
        err instanceof Error ? err.message : "Не удалось удалить папку"
      )
    } finally {
      setIsFolderActionLoading(false)
    }
  }

  const handleDeleteQuiz = async (quizId: string) => {
    setDeleteError("")
    setIsDeletingQuizId(quizId)
    try {
      await deleteQuiz(quizId)
      setQuizzes((prev) => prev.filter((q) => q.id !== quizId))
      setAllQuizzesCache((prev) =>
        prev ? prev.filter((q) => q.id !== quizId) : prev
      )
      onDeleteQuiz(quizId)
      await loadFolders()
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Не удалось удалить викторину"
      )
    } finally {
      setIsDeletingQuizId(null)
    }
  }


  const linkFolderId = (folderId?: string | null) =>
    folderId ?? activeFolderId ?? null

  const editLink = (quizId: string, folderId?: string | null) => {
    const fid = linkFolderId(folderId)
    return fid
      ? `/edit/${quizId}?folder_id=${encodeURIComponent(fid)}`
      : `/edit/${quizId}`
  }

  const teacherLink = (quizId: string, folderId?: string | null) => {
    const fid = linkFolderId(folderId)
    return fid
      ? `/teacher/${quizId}?folder_id=${encodeURIComponent(fid)}`
      : `/teacher/${quizId}`
  }

  const resultsLink = (quizId: string, folderId?: string | null) => {
    const fid = linkFolderId(folderId)
    return fid
      ? `/results/${quizId}?folder_id=${encodeURIComponent(fid)}`
      : `/results/${quizId}`
  }

  const renderQuizCard = (
    quiz: QuizListItem,
    options?: { folderId?: string | null; folderLabel?: string }
  ) => {
    const fid = linkFolderId(options?.folderId ?? quiz.folder_id)
    return (
      <Card
        key={quiz.id}
        className={cn(
          CARD_CLASS,
          "transition-shadow duration-200 hover:shadow-lg"
        )}
      >
        <CardContent className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <p
              className="lf-text break-words text-lg font-semibold [overflow-wrap:anywhere]"
              title={quiz.title}
            >
              {truncateDisplayName(quiz.title)}
            </p>
            {options?.folderLabel && (
              <p className="lf-text mt-1 text-sm text-muted-foreground">
                {options.folderLabel}
              </p>
            )}
          </div>
          <div className="dashboard-quiz-actions flex shrink-0 flex-wrap gap-2">
            <Button
              asChild
              variant="outline"
              size="sm"
              className="dashboard-quiz-btn h-auto min-h-8 shrink-0 whitespace-normal"
            >
              <Link to={editLink(quiz.id, fid)}>
                <Pencil />
                Редактировать
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              size="sm"
              className="dashboard-quiz-btn h-auto min-h-8 shrink-0 whitespace-normal"
            >
              <Link to={teacherLink(quiz.id, fid)}>
                <Presentation />
                Показ
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              size="sm"
              className="dashboard-quiz-btn h-auto min-h-8 shrink-0 whitespace-normal"
            >
              <Link to={resultsLink(quiz.id, fid)}>
                <BarChart3 />
                Результаты
              </Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="dashboard-quiz-btn h-auto min-h-8 shrink-0 whitespace-normal text-muted-foreground hover:text-destructive"
              onClick={() => void handleDeleteQuiz(quiz.id)}
              disabled={isDeletingQuizId === quiz.id}
            >
              <Trash2 className="size-4" />
              Удалить
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 py-8">
        <Card className={cn("w-full max-w-md", CARD_CLASS)}>
          <CardHeader>
            <CardTitle className="text-center text-2xl">
              Quiz Builder
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="login" className="w-full">
              <TabsList className="mb-4 grid w-full grid-cols-2">
                <TabsTrigger value="login">Войти</TabsTrigger>
                <TabsTrigger value="register">Регистрация</TabsTrigger>
              </TabsList>

              <TabsContent value="login">
                <form onSubmit={handleLogin} className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="login-email">Email</Label>
                    <Input
                      id="login-email"
                      type="email"
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                      placeholder="teacher@example.com"
                      autoComplete="email"
                      required
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="login-password">Пароль</Label>
                    <Input
                      id="login-password"
                      type="password"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      autoComplete="current-password"
                      required
                    />
                  </div>
                  {loginError && (
                    <p className="text-sm text-destructive">{loginError}</p>
                  )}
                  <Button
                    type="submit"
                    className={cn("w-full", ACCENT_BUTTON_CLASS)}
                    disabled={isLoading}
                  >
                    {isLoading ? "Вход…" : "Войти"}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="register">
                <form
                  onSubmit={handleRegister}
                  className="flex flex-col gap-4"
                >
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="register-name">Имя</Label>
                    <Input
                      id="register-name"
                      value={registerName}
                      onChange={(e) => setRegisterName(e.target.value)}
                      placeholder="Ваше имя"
                      autoComplete="name"
                    />
                    {registerNameError && (
                      <p className="text-sm text-destructive">
                        {registerNameError}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="register-email">Email</Label>
                    <Input
                      id="register-email"
                      type="email"
                      value={registerEmail}
                      onChange={(e) => setRegisterEmail(e.target.value)}
                      placeholder="email@example.com"
                      autoComplete="email"
                    />
                    {registerEmailError && (
                      <p className="text-sm text-destructive">
                        {registerEmailError}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="register-password">Пароль</Label>
                    <Input
                      id="register-password"
                      type="password"
                      value={registerPassword}
                      onChange={(e) => setRegisterPassword(e.target.value)}
                      autoComplete="new-password"
                    />
                    {registerPasswordError && (
                      <p className="text-sm text-destructive">
                        {registerPasswordError}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="register-password-confirm">
                      Подтверждение пароля
                    </Label>
                    <Input
                      id="register-password-confirm"
                      type="password"
                      value={registerPasswordConfirm}
                      onChange={(e) =>
                        setRegisterPasswordConfirm(e.target.value)
                      }
                      autoComplete="new-password"
                    />
                    {registerConfirmError && (
                      <p className="text-sm text-destructive">
                        {registerConfirmError}
                      </p>
                    )}
                  </div>
                  {registerGeneralError && (
                    <p className="text-sm text-destructive">
                      {registerGeneralError}
                    </p>
                  )}
                  <Button
                    type="submit"
                    className={cn("w-full", ACCENT_BUTTON_CLASS)}
                    disabled={isLoading}
                  >
                    {isLoading ? "Регистрация…" : "Зарегистрироваться"}
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto min-h-screen max-w-5xl px-4 py-6 sm:px-8 sm:py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <p className="dashboard-user-name lf-text text-lg font-medium">{user.name}</p>
        <Button type="button" variant="secondary" size="sm" onClick={handleLogout}>
          Выйти
        </Button>
      </div>

      <div className="relative mb-6">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          id="quiz-search"
          type="search"
          value={searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Поиск по названию, предмету, классу…"
          className="bg-white pl-9"
          aria-label="Поиск викторин"
        />
      </div>

      {isInsideFolder ? (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={goBackToFolders}
            >
              <ArrowLeft />
              Назад
            </Button>
            <h1 className="lf-text text-2xl font-bold sm:text-3xl">
              {activeFolderName || "Папка"}
            </h1>
          </div>

          <div className="mb-6 flex flex-wrap justify-end gap-3">
            <Button asChild className={cn(ACCENT_BUTTON_CLASS, "dashboard-action-btn")}>
              <Link to="/create">Создать викторину</Link>
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
            <h1 className="text-2xl font-bold sm:text-3xl">Мои папки</h1>
            <div className="flex flex-wrap items-center gap-2">
              {!showNewFolderInput ? (
                <Button
                  type="button"
                  className={cn(ACCENT_BUTTON_CLASS, "dashboard-action-btn")}
                  onClick={() => {
                    setShowNewFolderInput(true)
                    setFolderActionError("")
                  }}
                >
                  Новая папка
                </Button>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="Название папки"
                    className="w-48 bg-white"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void handleCreateFolder()
                      if (e.key === "Escape") {
                        setShowNewFolderInput(false)
                        setNewFolderName("")
                      }
                    }}
                    autoFocus
                  />
                  <Button
                    type="button"
                    size="sm"
                    className={ACCENT_BUTTON_CLASS}
                    disabled={isFolderActionLoading || !newFolderName.trim()}
                    onClick={() => void handleCreateFolder()}
                  >
                    Создать
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowNewFolderInput(false)
                      setNewFolderName("")
                    }}
                  >
                    Отмена
                  </Button>
                </div>
              )}
              <Button asChild className={cn(ACCENT_BUTTON_CLASS, "dashboard-action-btn")}>
                <Link to="/create">Создать викторину</Link>
              </Button>
            </div>
          </div>
        </>
      )}

      {(folderActionError || deleteError) && (
        <p className="mb-4 text-sm text-destructive">
          {folderActionError || deleteError}
        </p>
      )}

      {!isInsideFolder && isGlobalSearchActive && (
        <>
          {allQuizzesLoading && (
            <p className="text-sm text-muted-foreground">Поиск…</p>
          )}
          {allQuizzesError && (
            <p className="text-sm text-destructive">{allQuizzesError}</p>
          )}
          {!allQuizzesLoading &&
            !allQuizzesError &&
            allQuizzesCache !== null &&
            filteredGlobalQuizzes.length === 0 && (
              <Card className={cn("py-12", CARD_CLASS)}>
                <CardContent className="text-center">
                  <p className="lf-text text-lg text-muted-foreground">
                    Ничего не найдено по запросу «{searchQuery.trim()}»
                  </p>
                </CardContent>
              </Card>
            )}
          {!allQuizzesLoading &&
            !allQuizzesError &&
            filteredGlobalQuizzes.length > 0 && (
              <div className="flex flex-col gap-4">
                {filteredGlobalQuizzes.map((quiz) =>
                  renderQuizCard(quiz, {
                    folderId: quiz.folder_id,
                    folderLabel: quiz.folderName
                      ? `Папка: ${quiz.folderName}`
                      : "Без папки",
                  })
                )}
              </div>
            )}
        </>
      )}

      {!isInsideFolder && !isGlobalSearchActive && (
        <>
          {folders.length === 0 && !foldersLoading ? (
            <Card className={cn("py-12", CARD_CLASS)}>
              <CardContent className="flex flex-col items-center gap-3 text-center">
                <Folder className="dashboard-empty-icon lf-no-scale size-12 text-muted-foreground" />
                <p className="lf-text text-lg text-muted-foreground">
                  У вас пока нет папок
                </p>
                <Button
                  type="button"
                  className={ACCENT_BUTTON_CLASS}
                  onClick={() => setShowNewFolderInput(true)}
                >
                  Создать первую папку
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-4">
              {folders.map((folder) => (
                <Card
                  key={folder.id}
                  className={cn(
                    CARD_CLASS,
                    "cursor-pointer transition-shadow duration-200 hover:shadow-lg"
                  )}
                  onClick={() => {
                    if (renamingFolderId === folder.id) return
                    openFolder(folder)
                  }}
                >
                  <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
                    {renamingFolderId === folder.id ? (
                      <div
                        className="flex flex-1 flex-wrap items-center gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Input
                          value={renameFolderValue}
                          onChange={(e) =>
                            setRenameFolderValue(e.target.value)
                          }
                          className="max-w-xs bg-white"
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              void submitRenameFolder(folder.id)
                            }
                            if (e.key === "Escape") {
                              setRenamingFolderId(null)
                            }
                          }}
                          autoFocus
                        />
                        <Button
                          type="button"
                          size="sm"
                          className={ACCENT_BUTTON_CLASS}
                          disabled={isFolderActionLoading}
                          onClick={() => void submitRenameFolder(folder.id)}
                        >
                          Сохранить
                        </Button>
                      </div>
                    ) : (
                      <div className="flex min-w-0 flex-1 items-center gap-2">
                        <Folder className="size-5 shrink-0 text-quiz-accent" />
                        <p
                          className="lf-text min-w-0 flex-1 break-words text-lg font-semibold [overflow-wrap:anywhere]"
                          title={folder.name}
                        >
                          {formatFolderDisplayName(folder.name)}
                        </p>
                        {folder.quizzes_count != null && (
                          <span className="lf-text shrink-0 text-sm text-muted-foreground">
                            ({folder.quizzes_count})
                          </span>
                        )}
                      </div>
                    )}
                    <div
                      className="flex gap-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        aria-label="Переименовать папку"
                        onClick={(e) => startRenameFolder(folder, e)}
                        disabled={isFolderActionLoading}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive"
                        aria-label="Удалить папку"
                        onClick={(e) => handleDeleteFolder(folder, e)}
                        disabled={isFolderActionLoading}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {foldersLoading && (
            <p className="mt-4 text-sm text-muted-foreground">Загрузка…</p>
          )}
          {foldersError && (
            <p className="mt-2 text-sm text-destructive">{foldersError}</p>
          )}
        </>
      )}

      {isInsideFolder && (
        <>
          {quizzes.length === 0 && !quizzesLoading ? (
            <Card className={cn("py-12", CARD_CLASS)}>
              <CardContent className="flex flex-col items-center gap-3 text-center">
                <p className="lf-text text-lg text-muted-foreground">
                  В этой папке пока нет викторин
                </p>
                <Button asChild className={cn(ACCENT_BUTTON_CLASS, "dashboard-action-btn")}>
                  <Link to="/create">Создать викторину</Link>
                </Button>
              </CardContent>
            </Card>
          ) : isFolderSearchActive && displayedFolderQuizzes.length === 0 ? (
            <Card className={cn("py-12", CARD_CLASS)}>
              <CardContent className="text-center">
                <p className="lf-text text-lg text-muted-foreground">
                  Ничего не найдено по запросу «{searchQuery.trim()}»
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-4">
              {displayedFolderQuizzes.map((quiz) => renderQuizCard(quiz))}
            </div>
          )}

          {quizzesLoading && (
            <p className="mt-4 text-sm text-muted-foreground">Загрузка…</p>
          )}
          {quizzesError && (
            <p className="mt-2 text-sm text-destructive">{quizzesError}</p>
          )}
        </>
      )}

      <Dialog
        open={folderToDelete !== null}
        onOpenChange={(open) => {
          if (!open) setFolderToDelete(null)
        }}
      >
        <DialogContent className="sm:max-w-md" showCloseButton>
          <DialogHeader>
            <DialogTitle>Удалить папку?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Папка «{folderToDelete?.name}» и все викторины в ней будут удалены.
            Это действие нельзя отменить.
          </p>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setFolderToDelete(null)}
              disabled={isFolderActionLoading}
            >
              Отмена
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void confirmDeleteFolder()}
              disabled={isFolderActionLoading}
            >
              {isFolderActionLoading ? "Удаление…" : "Удалить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
