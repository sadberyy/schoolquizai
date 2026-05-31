import { resolveImageSrc } from "@/lib/quizApi"
import { cn } from "@/lib/utils"

interface QuestionImageProps {
  imageUrl?: string | null
  alt?: string
  className?: string
  /** Размер: 'sm' для preview/teacher show, 'md' для student */
  size?: "sm" | "md" | "lg"
}

const SIZE_CLASSES: Record<NonNullable<QuestionImageProps["size"]>, string> = {
  sm: "max-h-48 sm:max-h-56",
  md: "max-h-64 sm:max-h-80",
  lg: "max-h-80 sm:max-h-[28rem]",
}

export function QuestionImage({
  imageUrl,
  alt = "Изображение к вопросу",
  className,
  size = "md",
}: QuestionImageProps) {
  if (!imageUrl) return null

  return (
    <div className={cn("flex justify-center", className)}>
      <img
        src={resolveImageSrc(imageUrl)}
        alt={alt}
        loading="lazy"
        className={cn(
          "w-auto rounded-xl border-2 border-quiz-card-border object-contain shadow-sm",
          SIZE_CLASSES[size]
        )}
      />
    </div>
  )
}