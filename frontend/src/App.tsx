import { useEffect, useState } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import { PageLayout } from "@/components/PageLayout"
import { clearAuth, restoreSession } from "@/lib/auth"
import CreateQuiz from "@/pages/CreateQuiz"
import Dashboard, { type DashboardQuiz } from "@/pages/Dashboard"
import EditQuiz from "@/pages/EditQuiz"
import Results from "@/pages/Results"
import StudentQuiz from "@/pages/StudentQuiz"
import TeacherShow from "@/pages/TeacherShow"
import type { User } from "@/types/user"

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [quizzes, setQuizzes] = useState<DashboardQuiz[]>([])
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    void restoreSession()
      .then((restored) => {
        if (restored) setUser(restored)
      })
      .finally(() => setAuthReady(true))
  }, [])

  const handleLogin = (userData: User) => {
    setUser(userData)
  }

  const handleLogout = () => {
    clearAuth()
    setUser(null)
    setQuizzes([])
  }

  const handleDeleteQuiz = (quizId: string) => {
    setQuizzes((prev) => prev.filter((q) => q.id !== quizId))
  }

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Загрузка…
      </div>
    )
  }

  return (
    <BrowserRouter>
      <PageLayout>
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
                user={user}
                quizzes={quizzes}
                onLogin={handleLogin}
                onLogout={handleLogout}
                onDeleteQuiz={handleDeleteQuiz}
              />
            }
          />
          <Route path="/create" element={<CreateQuiz />} />
          <Route path="/edit/:quizId" element={<EditQuiz />} />
          <Route path="/teacher/:quizId" element={<TeacherShow />} />
          <Route path="/student/:quizId" element={<StudentQuiz />} />
          <Route path="/results/:quizId" element={<Results />} />
        </Routes>
      </PageLayout>
    </BrowserRouter>
  )
}

export default App
