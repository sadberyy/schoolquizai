import uuid
from datetime import datetime, timezone

from sqlalchemy.engine import Engine
from sqlalchemy import (
    event,
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


# Включаем поддержку внешних ключей для SQLite при каждом подключении
@event.listens_for(Engine, "connect")
def _fk_pragma_on_connect(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# users - учителя (регистрация и вход)
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)                # имя учителя
    email = Column(String, unique=True, nullable=False)  # почта для входа
    password_hash = Column(String, nullable=False)       # хеш пароля

    quizzes = relationship("Quiz", back_populates="teacher", cascade="all, delete-orphan")


# quizzes - настройки викторины (не вопросы)
class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True, default=generate_uuid)
    teacher_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    title = Column(String, nullable=False)                # тема
    subject = Column(String, nullable=True)               # предмет
    grade = Column(String, nullable=True)                 # класс
    difficulty = Column(String, nullable=True)            # easy / medium / hard
    full_time_seconds = Column(Integer, nullable=True)    # общее время на викторину
    question_time_seconds = Column(Integer, nullable=True) # время на один вопрос
    max_attempts = Column(Integer, default=1)             # число попыток
    status = Column(String, default="draft")              # draft / published

    teacher = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="quiz", cascade="all, delete-orphan")


# questions - сгенерированные и отредактированные вопросы
class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=generate_uuid)
    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)

    question_text = Column(Text, nullable=False)           # текст вопроса
    question_type = Column(String, nullable=False)         # single_choice / multiple_choice / true_false
    answers = Column(JSON, nullable=True)                  # варианты ответов
    correct_answers = Column(JSON, nullable=True)          # правильные ответы
    explanation = Column(Text, nullable=True)              # пояснение
    source_fragment = Column(Text, nullable=True)          # источник (для учителя)
    points = Column(Integer, default=1)                    # баллы за правильный ответ
    order_idx = Column(Integer, default=0)                 # порядок внутри викторины

    quiz = relationship("Quiz", back_populates="questions")


# results - результаты прохождения учениками
class Result(Base):
    __tablename__ = "results"

    id = Column(String, primary_key=True, default=generate_uuid)
    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)

    student_name = Column(String, nullable=False)          # имя/фамилия или название команды
    score = Column(Integer, default=0)                     # набранные баллы
    max_score = Column(Integer, nullable=True)             # максимально возможные баллы
    attempt_number = Column(Integer, default=1)            # номер попытки
    duration_seconds = Column(Integer, nullable=True)      # время прохождения в секундах

    quiz = relationship("Quiz", back_populates="results")