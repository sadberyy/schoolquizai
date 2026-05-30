const DEFAULT_MAX_LENGTH = 100
const FOLDER_SINGLE_WORD_MAX = 15

/** Обрезает длинные названия для отображения в списках. */
export function truncateDisplayName(
  name: string,
  maxLength = DEFAULT_MAX_LENGTH
): string {
  const trimmed = name.trim()
  if (trimmed.length <= maxLength) return trimmed
  return `${trimmed.slice(0, maxLength)}...`
}

/** Форматирование названия папки: длинное слово без пробелов — до 15 символов. */
export function formatFolderDisplayName(name: string): string {
  const trimmed = name.trim()
  if (trimmed.length > DEFAULT_MAX_LENGTH) {
    return `${trimmed.slice(0, DEFAULT_MAX_LENGTH)}...`
  }
  if (!/\s/.test(trimmed) && trimmed.length > FOLDER_SINGLE_WORD_MAX) {
    return `${trimmed.slice(0, FOLDER_SINGLE_WORD_MAX)}...`
  }
  return trimmed
}
