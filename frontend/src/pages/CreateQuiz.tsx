import {
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from "react"
import { Link } from "react-router-dom"
import { Camera, ImagePlus, Upload } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const SUBJECTS = [
  "Математика",
  "Русский язык",
  "Биология",
  "История",
  "Физика",
  "Алгебра",
  "Геометрия",
  "Обществознание",
  "Химия",
  "Музыка",
  "Литература",
  "Физкультура",
  "Информатика",
  "Окружающий мир",
  "Теор. вер. и статистика",
  "ОБЖ",
  "География",
  "Астрономия",
  "Религия и этика",
  "Технология",
  "Инд. проект",
  "ИЗО",
  "Краеведение",
  "Экономика",
  "Финансовая грамотность",
  "Философия",
] as const

const GRADES = Array.from({ length: 11 }, (_, i) => String(i + 1))

const DIFFICULTIES = ["Легко", "Средне", "Сложно"] as const

type QuestionType = "single" | "multiple" | "trueFalse"

const QUESTION_TYPE_OPTIONS: { id: QuestionType; label: string }[] = [
  { id: "single", label: "Одиночный выбор" },
  { id: "multiple", label: "Множественный выбор" },
  { id: "trueFalse", label: "True/False" },
]

function FormField({
  label,
  htmlFor,
  children,
  className,
}: {
  label: string
  htmlFor?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`flex flex-col gap-2 ${className ?? ""}`}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  )
}

export default function CreateQuiz() {
  const documentInputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  const [subject, setSubject] = useState("")
  const [grade, setGrade] = useState("")
  const [topic, setTopic] = useState("")
  const [questionCount, setQuestionCount] = useState(10)
  const [questionTypes, setQuestionTypes] = useState<QuestionType[]>([
    "single",
  ])
  const [difficulty, setDifficulty] = useState("")
  const [timerPerQuestion, setTimerPerQuestion] = useState("")
  const [totalTimer, setTotalTimer] = useState("")
  const [attempts, setAttempts] = useState(1)
  const [uploadedDocument, setUploadedDocument] = useState<File | null>(null)
  const [uploadedImage, setUploadedImage] = useState<File | null>(null)
  const [capturedPhoto, setCapturedPhoto] = useState<File | null>(null)

  const toggleQuestionType = (type: QuestionType, checked: boolean) => {
    setQuestionTypes((prev) => {
      if (checked) {
        return prev.includes(type) ? prev : [...prev, type]
      }
      const next = prev.filter((t) => t !== type)
      return next.length > 0 ? next : prev
    })
  }

  const handleDocumentChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setUploadedDocument(file)
  }

  const handleImageChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setUploadedImage(file)
  }

  const handleCameraCapture = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setCapturedPhoto(file)
  }

  const handleGenerate = (e: FormEvent) => {
    e.preventDefault()
    console.log({
      subject,
      grade,
      topic,
      questionCount,
      questionTypes,
      difficulty,
      timerPerQuestion,
      totalTimer,
      attempts,
      uploadedDocument,
      uploadedImage,
      capturedPhoto,
    })
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2 text-muted-foreground">
        <Link to="/">← К списку викторин</Link>
      </Button>

      <Card className="border-2 border-quiz-card-border bg-white/95 shadow-md ring-0">
        <CardHeader>
          <CardTitle className="text-2xl font-semibold">
            Создание викторины
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGenerate} className="space-y-8">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <FormField label="Предмет">
                <Select value={subject} onValueChange={setSubject}>
                  <SelectTrigger className="w-full" id="subject">
                    <SelectValue placeholder="Выберите предмет" />
                  </SelectTrigger>
                  <SelectContent
                    position="popper"
                    className="max-h-60 overflow-y-auto"
                  >
                    {SUBJECTS.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>

              <FormField label="Класс">
                <Select value={grade} onValueChange={setGrade}>
                  <SelectTrigger className="w-full" id="grade">
                    <SelectValue placeholder="Выберите класс" />
                  </SelectTrigger>
                  <SelectContent>
                    {GRADES.map((g) => (
                      <SelectItem key={g} value={g}>
                        {g} класс
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>

              <FormField label="Тема" htmlFor="topic">
                <Input
                  id="topic"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="Введите тему викторины"
                />
              </FormField>

              <FormField label="Число вопросов" htmlFor="questionCount">
                <Input
                  id="questionCount"
                  type="number"
                  min={1}
                  max={50}
                  value={questionCount}
                  onChange={(e) =>
                    setQuestionCount(
                      Math.min(50, Math.max(1, Number(e.target.value) || 1))
                    )
                  }
                />
              </FormField>

              <FormField label="Сложность вопросов">
                <Select value={difficulty} onValueChange={setDifficulty}>
                  <SelectTrigger className="w-full" id="difficulty">
                    <SelectValue placeholder="Выберите сложность" />
                  </SelectTrigger>
                  <SelectContent>
                    {DIFFICULTIES.map((d) => (
                      <SelectItem key={d} value={d}>
                        {d}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>

              <FormField label="Таймер на вопрос" htmlFor="timerPerQuestion">
                <Input
                  id="timerPerQuestion"
                  type="number"
                  min={0}
                  value={timerPerQuestion}
                  onChange={(e) => setTimerPerQuestion(e.target.value)}
                  placeholder="Секунды"
                />
              </FormField>

              <FormField label="Общий таймер" htmlFor="totalTimer">
                <Input
                  id="totalTimer"
                  type="number"
                  min={0}
                  value={totalTimer}
                  onChange={(e) => setTotalTimer(e.target.value)}
                  placeholder="Минуты"
                />
              </FormField>

              <FormField label="Количество попыток" htmlFor="attempts">
                <Input
                  id="attempts"
                  type="number"
                  min={1}
                  max={100}
                  value={attempts}
                  onChange={(e) =>
                    setAttempts(
                      Math.min(100, Math.max(1, Number(e.target.value) || 1))
                    )
                  }
                />
              </FormField>
            </div>

            <FormField label="Типы вопросов">
              <div className="flex flex-wrap gap-6 rounded-lg border border-input bg-muted/30 p-4">
                {QUESTION_TYPE_OPTIONS.map(({ id, label }) => (
                  <div key={id} className="flex items-center gap-2">
                    <Checkbox
                      id={`type-${id}`}
                      checked={questionTypes.includes(id)}
                      onCheckedChange={(checked) =>
                        toggleQuestionType(id, checked === true)
                      }
                    />
                    <Label
                      htmlFor={`type-${id}`}
                      className="cursor-pointer font-normal"
                    >
                      {label}
                    </Label>
                  </div>
                ))}
              </div>
            </FormField>

            <FormField label="Загрузка материалов">
              <input
                ref={documentInputRef}
                type="file"
                accept=".pdf,.docx,.pptx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation,text/plain"
                className="hidden"
                onChange={handleDocumentChange}
              />
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageChange}
              />
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={handleCameraCapture}
              />
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => documentInputRef.current?.click()}
                  >
                    <Upload />
                    Загрузить файл
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => imageInputRef.current?.click()}
                  >
                    <ImagePlus />
                    Загрузить картинку
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => cameraInputRef.current?.click()}
                  >
                    <Camera />
                    Сделать фото
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">PDF, PPTX, TXT, DOCX</p>
                {(uploadedDocument || uploadedImage || capturedPhoto) && (
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium">
                    {uploadedDocument && <span>{uploadedDocument.name}</span>}
                    {uploadedImage && <span>{uploadedImage.name}</span>}
                    {capturedPhoto && <span>{capturedPhoto.name}</span>}
                  </div>
                )}
              </div>
            </FormField>

            <Button
              type="submit"
              size="lg"
              className="h-12 w-full border-transparent bg-quiz-accent text-base text-white hover:bg-quiz-accent/90"
            >
              Сгенерировать викторину
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
