export type TextSegment =
  | { kind: "text"; value: string }
  | { kind: "math"; value: string; display: boolean }

type MathMatch = {
  start: number
  end: number
  value: string
  display: boolean
}

/** Разбивает строку на обычный текст и фрагменты LaTeX ($...$ / $$...$$). */
export function splitMathSegments(input: string): TextSegment[] {
  if (!input) return [{ kind: "text", value: "" }]

  const matches: MathMatch[] = []

  const displayRe = /\$\$([\s\S]+?)\$\$/g
  let match: RegExpExecArray | null
  while ((match = displayRe.exec(input)) !== null) {
    matches.push({
      start: match.index,
      end: match.index + match[0].length,
      value: match[1],
      display: true,
    })
  }

  const inlineRe = /(?<!\$)\$([^$\n]+?)\$(?!\$)/g
  while ((match = inlineRe.exec(input)) !== null) {
    const insideDisplay = matches.some(
      (d) => match!.index >= d.start && match!.index < d.end
    )
    if (insideDisplay) continue
    matches.push({
      start: match.index,
      end: match.index + match[0].length,
      value: match[1],
      display: false,
    })
  }

  matches.sort((a, b) => a.start - b.start)

  const segments: TextSegment[] = []
  let cursor = 0

  for (const item of matches) {
    if (item.start < cursor) continue
    if (item.start > cursor) {
      segments.push({ kind: "text", value: input.slice(cursor, item.start) })
    }
    segments.push({ kind: "math", value: item.value, display: item.display })
    cursor = item.end
  }

  if (cursor < input.length) {
    segments.push({ kind: "text", value: input.slice(cursor) })
  }

  return segments.length > 0 ? segments : [{ kind: "text", value: input }]
}
