import katex from "katex"
/** mhchem (\ce, \pu); для бандлера — katex/contrib/mhchem */
import "katex/contrib/mhchem"
import { useMemo } from "react"

import { splitMathSegments } from "@/lib/mathText"
import { cn } from "@/lib/utils"

type MathTextProps = {
  children: string
  className?: string
  as?: "span" | "p" | "div"
}

export function MathText({ children, className, as: Tag = "span" }: MathTextProps) {
  const segments = useMemo(() => splitMathSegments(children ?? ""), [children])

  return (
    <Tag className={cn("math-text leading-relaxed", className)}>
      {segments.map((segment, index) => {
        if (segment.kind === "text") {
          return <span key={index}>{segment.value}</span>
        }

        const html = katex.renderToString(segment.value.trim(), {
          throwOnError: false,
          displayMode: segment.display,
          strict: "ignore",
        })

        return (
          <span
            key={index}
            className={segment.display ? "my-2 block" : "inline"}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )
      })}
    </Tag>
  )
}

type MathPreviewProps = {
  text: string
  className?: string
}

/** Предпросмотр формул */
export function MathPreview({ text, className }: MathPreviewProps) {
  if (!text.trim()) return null

  // Показываем preview только когда реально есть LaTeX-разметка
  const hasMath = splitMathSegments(text).some((s) => s.kind === "math")
  if (!hasMath) return null

  return (
    <div
      className={cn(
        "rounded-md border border-dashed border-muted-foreground/25 bg-muted/15 px-3 py-2",
        className
      )}
    >
      <p className="mb-1 text-xs text-muted-foreground">Предпросмотр</p>
      <MathText className="text-sm">{text}</MathText>
    </div>
  )
}
