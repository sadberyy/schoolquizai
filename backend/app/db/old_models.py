import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy import (
    event,
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """
    Генерирует UUID в строковом формате.

    Используется как значение по умолчанию для первичных ключей моделей.
    UUID удобен тем, что не зависит от конкретной базы данных и безопасен
    для использования в распределённых системах.
    """
    return str(uuid.uuid4())


def default_expires_at():
    """
    Возвращает дату и время автоматического истечения временной загрузки.

    По умолчанию временные загруженные материалы хранятся 24 часа.
    После наступления expires_at их можно удалить фоновым процессом очистки.
    """
    return utcnow() + timedelta(hours=24)


@event.listens_for(Engine, "connect")
def _fk_pragma_on_connect(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Teacher(Base):
    """
       Учитель, зарегистрированный в системе.

       Эта таблица хранит аккаунты пользователей-учителей, которые создают викторины,
       загружают учебные материалы и просматривают результаты прохождения.

       Основные поля:
       - id: уникальный идентификатор учителя.
       - name: имя учителя.
       - email: уникальная почта для входа в систему.
       - password_hash: хеш пароля. Пароль в открытом виде хранить нельзя.
       - created_at: дата и время создания аккаунта.
       - updated_at: дата и время последнего обновления аккаунта.

       Связи:
       - quizzes: викторины, созданные этим учителем.
       - materials: постоянные материалы учителя в библиотеке.
       - temporary_uploads: временные загрузки учителя для генерации викторин.

       Примечание:
       Если teacher удаляется, связанные с ним викторины, материалы и временные загрузки
       также удаляются благодаря cascade="all, delete-orphan".
       """

    __tablename__ = "teachers"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    quizzes = relationship("Quiz", back_populates="teacher", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="teacher", cascade="all, delete-orphan")
    temporary_uploads = relationship("TemporaryUpload", back_populates="teacher", cascade="all, delete-orphan")


class Quiz(Base):
    """
    Викторина, созданная учителем.

    Эта таблица хранит настройки и метаинформацию о викторине:
    название, сложность, ограничения по времени, количество попыток и статус публикации.

    Викторина может быть в статусе черновика, опубликованной или архивной.
    Учитель может сначала сгенерировать вопросы, отредактировать их,
    а затем опубликовать викторину для учеников.

    Основные поля:
    - id: уникальный идентификатор викторины.
    - teacher_id: идентификатор учителя, который создал викторину.
    - title: название викторины.
    - description: описание викторины.
    - difficulty: уровень сложности, например easy, medium, hard.
    - full_time_seconds: общее время на прохождение всей викторины в секундах.
    - question_time_seconds: ограничение времени на один вопрос в секундах.
    - max_attempts: максимальное количество попыток прохождения.
    - status: статус викторины, например draft, published, archived.
    - access_token: уникальный токен для доступа учеников к викторине по ссылке.
    - created_at: дата и время создания викторины.
    - updated_at: дата и время последнего обновления викторины.

    Связи:
    - teacher: учитель-владелец викторины.
    - questions: список вопросов викторины.
    - attempts: попытки прохождения этой викторины учениками.

    Пример ссылки для ученика:
    /quiz/{access_token}

    Примечание:
    Ученики не обязаны регистрироваться. Они открывают викторину по access_token
    и указывают имя/фамилию перед прохождением.
    """

    __tablename__ = "quizzes"

    id = Column(String, primary_key=True, default=generate_uuid)

    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    difficulty = Column(String, nullable=True)

    full_time_seconds = Column(Integer, nullable=True)
    question_time_seconds = Column(Integer, nullable=True)

    max_attempts = Column(Integer, default=1)

    status = Column(String, default="draft")
    access_token = Column(String, unique=True, nullable=False, index=True, default=generate_uuid)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    teacher = relationship("Teacher", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    """
    Вопрос внутри конкретной викторины.

    Эта таблица хранит вопросы, которые были сгенерированы моделью или добавлены
    учителем вручную. Вопросы сохраняются отдельно от викторины, чтобы учитель
    мог редактировать их перед публикацией.

    Основные поля:
    - id: уникальный идентификатор вопроса.
    - quiz_id: идентификатор викторины, к которой относится вопрос.
    - question_text: текст вопроса.
    - question_type: тип вопроса, например:
        - single_choice: один правильный вариант;
        - multiple_choice: несколько правильных вариантов;
        - true_false: верно/неверно;
        - short_answer: короткий текстовый ответ;
        - open_answer: развёрнутый ответ.
    - answers: варианты ответа в JSON-формате.
    - correct_answers: правильный ответ или список правильных ответов в JSON-формате.
    - explanation: объяснение правильного ответа.
    - source_fragment: фрагмент исходного материала, на основе которого создан вопрос.
    - order_idx: порядок вопроса внутри викторины.
    - points: количество баллов за правильный ответ.
    - created_at: дата и время создания вопроса.
    - updated_at: дата и время последнего обновления вопроса.

    Связи:
    - quiz: викторина, к которой относится вопрос.
    - student_answers: ответы учеников на этот вопрос.

    Пример answers для single_choice:
    [
        {"id": "a", "text": "Париж"},
        {"id": "b", "text": "Лондон"},
        {"id": "c", "text": "Берлин"}
    ]

    Пример correct_answers:
    ["a"]

    Примечание:
    Поля answers и correct_answers сделаны JSON, чтобы гибко поддерживать
    разные типы вопросов без создания отдельных таблиц под каждый тип.
    """

    __tablename__ = "questions"

    __table_args__ = (UniqueConstraint("quiz_id", "order_idx", name="uq_question_order"),)

    id = Column(String, primary_key=True, default=generate_uuid)

    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)

    question_text = Column(Text, nullable=False)

    question_type = Column(String, nullable=False)
    answers = Column(JSON, nullable=True, default=lambda: [])
    correct_answers = Column(JSON, nullable=True, default=lambda: [])

    explanation = Column(Text, nullable=True)
    source_fragment = Column(Text, nullable=True)

    order_idx = Column(Integer, default=0)
    points = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    quiz = relationship("Quiz", back_populates="questions")
    student_answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")


class QuizAttempt(Base):
    """
    Попытка прохождения викторины учеником.

    Так как ученики проходят викторины без регистрации, отдельной таблицы students
    пока не требуется. Имя и фамилия ученика сохраняются прямо в попытке прохождения.

    Одна викторина может иметь много попыток от разных учеников.
    Один и тот же ученик также может проходить викторину несколько раз,
    если это разрешено настройкой max_attempts в Quiz.

    Основные поля:
    - id: уникальный идентификатор попытки.
    - quiz_id: идентификатор викторины, которую проходит ученик.
    - student_name: имя ученика.
    - student_surname: фамилия ученика.
    - score: набранное количество баллов.
    - max_score: максимальное количество баллов за викторину.
    - attempt_number: номер попытки.
    - started_at: дата и время начала прохождения.
    - finished_at: дата и время завершения прохождения.
    - duration_seconds: фактическое время прохождения в секундах.

    Связи:
    - quiz: викторина, которую проходил ученик.
    - answers: ответы ученика в рамках этой попытки.

    Примечание:
    Эта таблица заменяет простую таблицу results, потому что результат — это
    не свойство викторины, а отдельная попытка конкретного ученика.
    """

    __tablename__ = "quiz_attempts"

    id = Column(String, primary_key=True, default=generate_uuid)

    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)

    student_name = Column(String, nullable=False)
    student_surname = Column(String, nullable=True)

    score = Column(Integer, default=0)
    max_score = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("quiz_id", "student_name", "student_surname", "attempt_number",
                         name="uq_attempt_per_student"),
    )

    attempt_number = Column(Integer, default=1)

    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    quiz = relationship("Quiz", back_populates="attempts")
    answers = relationship("StudentAnswer", back_populates="attempt", cascade="all, delete-orphan")


class StudentAnswer(Base):
    """
    Ответ ученика на конкретный вопрос в рамках одной попытки прохождения.

    Эта таблица хранит не только итоговый балл ученика, но и детальную информацию
    по каждому вопросу: что именно выбрал или написал ученик, был ли ответ верным,
    сколько баллов он получил.

    Основные поля:
    - id: уникальный идентификатор ответа.
    - attempt_id: идентификатор попытки прохождения.
    - question_id: идентификатор вопроса.
    - answer: ответ ученика в JSON-формате.
    - is_correct: правильно ли ученик ответил.
    - points_received: сколько баллов получено за этот вопрос.
    - created_at: дата и время сохранения ответа.

    Связи:
    - attempt: попытка прохождения, к которой относится ответ.
    - question: вопрос, на который был дан ответ.

    Примеры answer:
    - для single_choice: "a"
    - для multiple_choice: ["a", "c"]
    - для short_answer: "Париж"
    - для open_answer: "Развёрнутый текст ответа ученика"

    Примечание:
    Благодаря этой таблице можно показывать учителю подробную аналитику:
    какие вопросы вызвали сложности, где ученики чаще ошибались,
    какие ответы давали конкретные ученики.
    """

    __tablename__ = "student_answers"

    id = Column(String, primary_key=True, default=generate_uuid)

    attempt_id = Column(String, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)

    answer = Column(JSON, nullable=True)
    is_correct = Column(Boolean, nullable=True)

    points_received = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)

    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("Question", back_populates="student_answers")


class Material(Base):
    """
    Постоянный учебный материал в библиотеке.

    Эта таблица хранит материалы, которые можно использовать для генерации викторин.
    Материалом может быть учебник, PDF-файл, DOCX-документ, презентация, текст,
    ссылка на источник или системный предзагруженный материал.

    Материалы могут быть:
    - системными, доступными всем пользователям;
    - пользовательскими, загруженными конкретным учителем.

    Основные поля:
    - id: уникальный идентификатор материала.
    - teacher_id: идентификатор учителя-владельца материала.
      Может быть NULL, если материал системный.
    - title: название материала.
    - source_type: тип источника, например pdf, docx, txt, url, manual_text.
    - original_filename: исходное имя файла, если материал был загружен как файл.
    - stored_path: путь к сохранённому файлу на диске или в файловом хранилище.
    - text_content: полный извлечённый текст материала, если его удобно хранить целиком.
    - is_system: является ли материал системным.
    - meta: дополнительные метаданные в JSON-формате.
    - created_at: дата и время создания материала.
    - updated_at: дата и время последнего обновления материала.

    Связи:
    - teacher: учитель-владелец материала.
    - blocks: структурные блоки материала.

    Примечание:
    Если материал большой, его удобнее хранить не только целиком в text_content,
    но и разбивать на блоки в MaterialBlock. Это поможет выбирать релевантные
    фрагменты для генерации вопросов.
    """

    __tablename__ = "materials"

    id = Column(String, primary_key=True, default=generate_uuid)

    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True, index=True)

    title = Column(String, nullable=False)

    source_type = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    stored_path = Column(String, nullable=True)

    text_content = Column(Text, nullable=True)

    is_system = Column(Boolean, default=False)

    meta = Column(JSON, default=lambda: {})

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    teacher = relationship("Teacher", back_populates="materials")
    blocks = relationship("MaterialBlock", back_populates="material", cascade="all, delete-orphan")


class MaterialBlock(Base):
    """
    Отдельный структурный блок постоянного материала.

    Эта таблица хранит материал, разбитый на небольшие части:
    абзацы, страницы, слайды, таблицы, изображения с OCR или другие смысловые блоки.

    Разбиение на блоки полезно для генерации викторин, потому что модель может
    получать не весь учебник целиком, а только нужные фрагменты.

    Основные поля:
    - id: уникальный идентификатор блока.
    - material_id: идентификатор материала, которому принадлежит блок.
    - block_type: тип блока, например text, paragraph, page, slide, table, image_ocr.
    - content: текстовое содержимое блока.
    - page_num: номер страницы, если источник постраничный.
    - slide_num: номер слайда, если источник — презентация.
    - order_idx: порядок блока внутри материала.
    - image_path: путь к изображению, если блок связан с картинкой.
    - meta: дополнительные метаданные в JSON-формате.
    - created_at: дата и время создания блока.

    Связи:
    - material: материал, которому принадлежит блок.

    Пример:
    Один PDF-учебник может быть сохранён как Material,
    а каждая его страница или смысловой абзац — как отдельный MaterialBlock.
    """

    __tablename__ = "material_blocks"

    id = Column(String, primary_key=True, default=generate_uuid)

    material_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)

    block_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    page_num = Column(Integer, nullable=True)
    slide_num = Column(Integer, nullable=True)
    order_idx = Column(Integer, default=0)

    image_path = Column(String, nullable=True)

    meta = Column(JSON, default=lambda: {})

    created_at = Column(DateTime, default=utcnow)

    material = relationship("Material", back_populates="blocks")


class QuizMaterial(Base):
    """
    Связующая таблица между викторинами и материалами.

    Эта таблица показывает, на основе каких постоянных материалов была создана
    конкретная викторина.

    Нужна для связи многие-ко-многим:
    - одна викторина может быть создана на основе нескольких материалов;
    - один материал может использоваться в разных викторинах.

    Основные поля:
    - quiz_id: идентификатор викторины.
    - material_id: идентификатор материала.
    - created_at: дата и время создания связи.

    Пример:
    Викторина по теме "Вторая мировая война" может быть создана на основе:
    - главы учебника;
    - презентации учителя;
    - дополнительной статьи.

    Примечание:
    Составной primary key из quiz_id и material_id защищает от повторного
    добавления одной и той же связи.
    """

    __tablename__ = "quiz_materials"

    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), primary_key=True)
    material_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True)

    created_at = Column(DateTime, default=utcnow)


class TemporaryUpload(Base):
    """
    Временная загрузка файла или текста учителем.

    Эта таблица используется для материалов, которые учитель загрузил только
    для генерации конкретной викторины и пока не сохранил в постоянную библиотеку.

    Например, учитель может загрузить PDF, DOCX, презентацию или вставить текст.
    Система извлекает из него текст, разбивает на блоки и использует для генерации
    вопросов. После создания викторины временную загрузку можно удалить или
    перенести в Material.

    Основные поля:
    - id: уникальный идентификатор временной загрузки.
    - teacher_id: идентификатор учителя, который загрузил файл.
    - original_filename: исходное имя загруженного файла.
    - file_type: тип файла или источника, например pdf, docx, pptx, txt, manual_text.
    - stored_path: путь к временному файлу на диске или в файловом хранилище.
    - status: статус обработки, например:
        - uploaded: файл загружен;
        - processing: файл обрабатывается;
        - processed: текст успешно извлечён;
        - failed: произошла ошибка;
        - used: материал уже использован для генерации.
    - extracted_text: извлечённый текст из файла.
    - error_message: текст ошибки, если обработка завершилась неудачно.
    - meta: дополнительные метаданные в JSON-формате.
    - created_at: дата и время создания временной загрузки.
    - expires_at: дата и время, после которого загрузку можно автоматически удалить.

    Связи:
    - teacher: учитель, загрузивший материал.
    - blocks: блоки, полученные из временной загрузки.

    Примечание:
    Временные загрузки не стоит хранить бесконечно. Их можно регулярно очищать
    по expires_at, например раз в сутки.
    """

    __tablename__ = "temporary_uploads"

    id = Column(String, primary_key=True, default=generate_uuid)

    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True, index=True)

    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    stored_path = Column(String, nullable=True)

    status = Column(String, default="uploaded")

    extracted_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    meta = Column(JSON, default=lambda: {})

    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, default=default_expires_at)

    teacher = relationship("Teacher", back_populates="temporary_uploads")
    blocks = relationship("TemporaryBlock", back_populates="upload", cascade="all, delete-orphan")


class TemporaryBlock(Base):
    """
    Отдельный блок временно загруженного материала.

    Эта таблица похожа на MaterialBlock, но используется только для временных
    загрузок. Например, когда учитель загрузил файл, система может разбить его
    на страницы, абзацы или слайды и сохранить эти части как TemporaryBlock.

    Основные поля:
    - id: уникальный идентификатор блока.
    - upload_id: идентификатор временной загрузки.
    - block_type: тип блока, например text, paragraph, page, slide, table, image_ocr.
    - content: текстовое содержимое блока.
    - page_num: номер страницы, если источник постраничный.
    - slide_num: номер слайда, если источник — презентация.
    - order_idx: порядок блока внутри временной загрузки.
    - image_path: путь к изображению, если блок связан с картинкой.
    - meta: дополнительные метаданные в JSON-формате.
    - created_at: дата и время создания блока.

    Связи:
    - upload: временная загрузка, которой принадлежит блок.

    Примечание:
    После создания викторины TemporaryBlock можно удалить вместе с TemporaryUpload
    или перенести в MaterialBlock, если учитель решил сохранить материал в библиотеку.
    """

    __tablename__ = "temporary_blocks"

    id = Column(String, primary_key=True, default=generate_uuid)

    upload_id = Column(String, ForeignKey("temporary_uploads.id", ondelete="CASCADE"), nullable=False, index=True)

    block_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    page_num = Column(Integer, nullable=True)
    slide_num = Column(Integer, nullable=True)
    order_idx = Column(Integer, default=0)

    image_path = Column(String, nullable=True)

    meta = Column(JSON, default=lambda: {})

    created_at = Column(DateTime, default=utcnow)

    upload = relationship("TemporaryUpload", back_populates="blocks")


Index("idx_questions_quiz_order", Question.quiz_id, Question.order_idx)
Index("idx_material_blocks_material_order", MaterialBlock.material_id, MaterialBlock.order_idx)
Index("idx_temp_blocks_upload_order", TemporaryBlock.upload_id, TemporaryBlock.order_idx)