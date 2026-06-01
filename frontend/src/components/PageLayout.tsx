import type { ReactNode } from "react"

import { AccessibilityToggle } from "@/components/AccessibilityToggle"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"

export function PageLayout({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider>
      <Toaster position="top-center" richColors closeButton />
      <div className="relative min-h-screen">
        <div
          className="quiz-page-background pointer-events-none fixed top-0 left-0 -z-10"
          aria-hidden
        />
        <AccessibilityToggle />
        <div className="relative min-h-screen pt-2 pr-14 sm:pr-16">
          {children}
        </div>
      </div>
    </TooltipProvider>
  )
}
