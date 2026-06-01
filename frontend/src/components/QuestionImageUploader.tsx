import { useCallback, useRef, useState } from "react"
import { ImagePlus, Loader2, Trash2, AlertCircle, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import {
  deleteQuestionImage,
  resolveImageSrc,
  uploadQuestionImage,
  validateImageFile,
} from "@/lib/quizApi"

export interface QuestionImageUploaderProps {
  quizId: string | undefined
  questionId: string
  imageUrl: string | null | undefined
  /** true, если вопрос ещё не сохранён в БД (имеет временный id) */
  isUnsaved: boolean
  onImageChange: (newUrl: string | null) => void
  disabled?: boolean
}

export function QuestionImageUploader({
  quizId,
  questionId,
  imageUrl,
  isUnsaved,
  onImageChange,
  disabled = false,
}: QuestionImageUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isDisabled = disabled || isUploading || isDeleting
  const isInteractionBlocked = isUnsaved || !quizId

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return
      if (!quizId) {
        setError("Сначала сохраните черновик викторины")
        return
      }

      const file = files[0]
      const validationError = validateImageFile(file)
      if (validationError) {
        setError(validationError)
        return
      }

      setError(null)
      setIsUploading(true)
      try {
        const newUrl = await uploadQuestionImage({
          quizId,
          questionId,
          file,
        })
        onImageChange(newUrl)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Не удалось загрузить изображение"
        )
      } finally {
        setIsUploading(false)
        if (inputRef.current) inputRef.current.value = ""
      }
    },
    [quizId, questionId, onImageChange]
  )

  const handleDelete = useCallback(async () => {
    if (!quizId) return
    setError(null)
    setIsDeleting(true)
    try {
      await deleteQuestionImage({ quizId, questionId })
      onImageChange(null)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось удалить изображение"
      )
    } finally {
      setIsDeleting(false)
    }
  }, [quizId, questionId, onImageChange])

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (isInteractionBlocked || isDisabled) return
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    if (isInteractionBlocked || isDisabled) return
    void handleFiles(e.dataTransfer.files)
  }

  const openFilePicker = () => {
    if (isInteractionBlocked || isDisabled) return
    inputRef.current?.click()
  }

  // ============ Состояние: вопрос не сохранён ============
  if (isInteractionBlocked && !imageUrl) {
    return (
      <div className="flex flex-col gap-2">
        <Label>Изображение к вопросу</Label>
        <div
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-muted-foreground/30 bg-muted/30 px-4 py-8 text-center",
            "transition-all duration-300"
          )}
        >
          <Lock className="size-6 text-muted-foreground/60" />
          <p className="text-sm text-muted-foreground">
            Сначала сохраните черновик, чтобы добавить изображение
          </p>
        </div>
      </div>
    )
  }

  // ============ Состояние: есть превью ============
  if (imageUrl) {
    return (
      <div className="flex flex-col gap-2">
        <Label>Изображение к вопросу</Label>
        <div
          className={cn(
            "group relative overflow-hidden rounded-xl border-2 border-quiz-card-border bg-muted/20",
            "transition-all duration-300"
          )}
        >
          <img
            src={resolveImageSrc(imageUrl)}
            alt="Изображение к вопросу"
            className={cn(
              "h-auto max-h-80 w-full object-contain transition-all duration-300",
              isDeleting && "scale-95 opacity-40 blur-sm"
            )}
          />

          {isDeleting && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/40 backdrop-blur-sm">
              <Loader2 className="size-8 animate-spin text-foreground" />
            </div>
          )}

          <div
            className={cn(
              "absolute right-3 top-3 flex gap-2",
              "opacity-0 transition-opacity duration-200 group-hover:opacity-100",
              "focus-within:opacity-100"
            )}
          >
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={openFilePicker}
              disabled={isDisabled}
              className="bg-background/90 backdrop-blur-sm hover:bg-background"
            >
              <ImagePlus className="size-4" />
              Заменить
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => void handleDelete()}
              disabled={isDisabled}
            >
              <Trash2 className="size-4" />
              Удалить
            </Button>
          </div>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => void handleFiles(e.target.files)}
        />

        {error && (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>
    )
  }

  // ============ Состояние: dropzone (пусто) ============
  return (
    <div className="flex flex-col gap-2">
      <Label>Изображение к вопросу</Label>

      <div
        role="button"
        tabIndex={0}
        onClick={openFilePicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            openFilePicker()
          }
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        aria-label="Загрузить изображение к вопросу"
        aria-disabled={isDisabled}
        className={cn(
          "group relative flex cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden",
          "rounded-xl border-2 border-dashed px-4 py-10 text-center",
          "transition-all duration-300 ease-out",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quiz-accent focus-visible:ring-offset-2",
          isDragOver
            ? "scale-[1.02] border-quiz-accent bg-quiz-accent/5 shadow-lg"
            : "border-muted-foreground/30 bg-muted/20 hover:border-quiz-accent/60 hover:bg-muted/40",
          isDisabled && "pointer-events-none opacity-60"
        )}
      >
        {isUploading ? (
          <>
            <Loader2 className="size-8 animate-spin text-quiz-accent" />
            <p className="text-sm font-medium text-foreground">
              Загрузка изображения…
            </p>
          </>
        ) : (
          <>
            <div
              className={cn(
                "flex size-12 items-center justify-center rounded-full bg-quiz-accent/10",
                "transition-transform duration-300 group-hover:scale-110"
              )}
            >
              <ImagePlus className="size-6 text-quiz-accent" />
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-foreground">
                {isDragOver
                  ? "Отпустите файл для загрузки"
                  : "Перетащите изображение сюда или нажмите для выбора"}
              </p>
              <p className="text-xs text-muted-foreground">
                JPG, PNG или WebP · до 5 MB
              </p>
            </div>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => void handleFiles(e.target.files)}
      />

      {error && (
        <div className="flex items-start gap-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}