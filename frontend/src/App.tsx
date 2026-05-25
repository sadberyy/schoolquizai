import { useState } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import { PageLayout } from "@/components/PageLayout"
import CreateQuiz from "@/pages/CreateQuiz"
import Dashboard, { MOCK_QUIZZES, type DashboardQuiz } from "@/pages/Dashboard"
import EditQuiz from "@/pages/EditQuiz"
import Results from "@/pages/Results"
import StudentQuiz from "@/pages/StudentQuiz"
import TeacherShow from "@/pages/TeacherShow"
import type { User } from "@/types/user"

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [quizzes, setQuizzes] = useState<DashboardQuiz[]>(MOCK_QUIZZES)

  const handleLogin = (userData: User) => {
    setUser(userData)
  }

  const handleLogout = () => {
    setUser(null)
  }

  const handleDeleteQuiz = (quizId: string) => {
    setQuizzes((prev) => prev.filter((q) => q.id !== quizId))
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
