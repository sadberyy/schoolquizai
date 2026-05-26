import { useEffect, useState } from "react"
import { Eye, EyeOff } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const STORAGE_KEY = "schoolquiz-large-font"

function readStoredPreference(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true"
  } catch {
    return false
  }
}

export function AccessibilityToggle() {
  const [enabled, setEnabled] = useState(readStoredPreference)

  useEffect(() => {
    document.body.classList.toggle("large-font", enabled)
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? "true" : "false")
    } catch {
      // localStorage unavailable
    }
  }, [enabled])

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className={cn(
        "fixed top-4 right-4 z-50 border-2 border-quiz-card-border bg-white/95 shadow-md transition-colors hover:bg-muted/80",
        "h-auto w-auto min-h-[2.75rem] min-w-[2.75rem] p-2.5",
        enabled && "border-quiz-accent bg-quiz-accent/15 ring-2 ring-quiz-accent/30"
      )}
      onClick={() => setEnabled((value) => !value)}
      aria-pressed={enabled}
      aria-label={
        enabled
          ? "Отключить версию для слабовидящих"
          : "Включить версию для слабовидящих"
      }
      title={
        enabled
          ? "Обычный размер текста"
          : "Версия для слабовидящих — увеличенный текст и элементы"
      }
    >
      {enabled ? (
        <EyeOff className="shrink-0" aria-hidden />
      ) : (
        <Eye className="shrink-0" aria-hidden />
      )}
    </Button>
  )
}
