import type { ReactNode } from "react"

export function PageLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen">
      <div
        className="quiz-page-background pointer-events-none fixed top-0 left-0 -z-10"
        aria-hidden
      />
      <div className="relative">{children}</div>
    </div>
  )
}
