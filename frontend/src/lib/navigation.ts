export function folderDashboardUrl(folderId: string | null | undefined): string {
  if (!folderId) return "/"
  return `/?folder_id=${encodeURIComponent(folderId)}`
}

export function resolveFolderBackUrl(
  folderIdFromUrl: string | null,
  folderIdFromQuiz: string | null | undefined
): string {
  return folderDashboardUrl(folderIdFromUrl ?? folderIdFromQuiz ?? null)
}
