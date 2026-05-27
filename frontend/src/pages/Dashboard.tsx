import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import type { User } from "@/types/user"
import {
  BarChart3,
  ClipboardList,
  Pencil,
  Presentation,
  Trash2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { authFetch, loginUser, registerUser } from "@/lib/auth"
import { readApiError } from "@/lib/quizApi"
import { cn } from "@/lib/utils"
import { API_BASE_URL } from "@/lib/api"

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
  quizzes: quizzesProp,
  onLogin,
  onLogout,
  onDeleteQuiz,
}: DashboardProps) {
  const [quizzes, setQuizzes] = useState<DashboardQuiz[]>(quizzesProp ?? [])
  const [quizzesLoading, setQuizzesLoading] = useState(false)
  const [quizzesError, setQuizzesError] = useState("")
  const [deleteError, setDeleteError] = useState("")
  const [isDeletingQuizId, setIsDeletingQuizId] = useState<string | null>(null)

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

  useEffect(() => {
    if (!user) return

    let ignore = false

    async function loadQuizzes() {
      setQuizzesLoading(true)
      setQuizzesError("")
      setDeleteError("")
      try {
        const response = await authFetch(`${API_BASE_URL}/quiz/list`)
        if (!response.ok) {
          throw new Error(
            await readApiError(response, "Ошибка загрузки викторин")
          )
        }
        const data = (await response.json()) as { quizzes?: DashboardQuiz[] }
        if (!ignore) setQuizzes(data.quizzes ?? [])
      } catch (err) {
        if (ignore) return
        setQuizzesError(
          err instanceof Error ? err.message : "Не удалось загрузить викторины"
        )
        // Оставляем текущие данные (возможно, это mock), но показываем ошибку.
      } finally {
        if (!ignore) setQuizzesLoading(false)
      }
    }

    void loadQuizzes()

    return () => {
      ignore = true
    }
  }, [user])

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

  const handleDeleteQuiz = async (quizId: string) => {
    setDeleteError("")
    setIsDeletingQuizId(quizId)
    try {
      const response = await authFetch(`${API_BASE_URL}/quiz/${quizId}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error(await readApiError(response, "Ошибка удаления"))
      }

      setQuizzes((prev) => prev.filter((q) => q.id !== quizId))
      onDeleteQuiz(quizId)
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Не удалось удалить викторину"
      )
    } finally {
      setIsDeletingQuizId(null)
    }
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
        <p className="text-lg font-medium">{user.name}</p>
        <Button type="button" variant="secondary" size="sm" onClick={handleLogout}>
          Выйти
        </Button>
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold sm:text-3xl">Мои викторины</h1>
        <Button asChild className={ACCENT_BUTTON_CLASS}>
          <Link to="/create">Создать викторину</Link>
        </Button>
      </div>

      {deleteError && (
        <p className="mb-4 text-sm text-destructive">{deleteError}</p>
      )}

      {quizzes.length === 0 ? (
        <Card className={cn("py-12", CARD_CLASS)}>
          <CardContent className="flex flex-col items-center gap-3 text-center">
            <ClipboardList className="size-12 text-muted-foreground" />
            <p className="text-lg text-muted-foreground">
              У вас пока нет викторин
            </p>
            <Button asChild className={ACCENT_BUTTON_CLASS}>
              <Link to="/create">Создать первую викторину</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {quizzes.map((quiz) => (
            <Card
              key={quiz.id}
              className={cn(
                CARD_CLASS,
                "transition-shadow duration-200 hover:shadow-lg"
              )}
            >
              <CardContent className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-lg font-semibold">{quiz.title}</p>
                <div className="flex flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/edit/${quiz.id}`}>
                      <Pencil />
                      Редактировать
                    </Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/teacher/${quiz.id}`}>
                      <Presentation />
                      Показ
                    </Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/results/${quiz.id}`}>
                      <BarChart3 />
                      Результаты
                    </Link>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => handleDeleteQuiz(quiz.id)}
                    aria-label="Удалить викторину"
                    disabled={isDeletingQuizId === quiz.id}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {quizzesLoading && (
        <p className="mt-4 text-sm text-muted-foreground">Загрузка...</p>
      )}
      {quizzesError && (
        <p className="mt-2 text-sm text-destructive">{quizzesError}</p>
      )}
    </div>
  )
}
