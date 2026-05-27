/** Имя файла для скачивания (как на backend в _safe_filename). */
export function buildDownloadFilename(
  title: string,
  extension: "pdf" | "pptx",
  options?: { suffix?: string; fallbackBase?: string }
): string {
  const fallbackBase = options?.fallbackBase ?? "quiz"
  const raw = `${title.trim()}${options?.suffix ?? ""}`
  const base = raw.replace(/[<>:"/\\|?*]/g, "").trim().slice(0, 80) || fallbackBase
  return `${base}.${extension}`
}
