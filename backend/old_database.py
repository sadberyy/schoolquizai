import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager

LIBRARY_DB_PATH = "../data/library.db"  # постоянная база (учебники)
TEMP_DB_PATH = "../data/temp_uploads.db"  # временная база (материалы учителя)

os.makedirs("../data", exist_ok=True)

Base = declarative_base()

# Здесь можно импортировать модели Document и Block
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    meta = Column(JSON, default={})

    blocks = relationship("Block", back_populates="document", cascade="all, delete-orphan")


class Block(Base):
    __tablename__ = "blocks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    block_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    page_num = Column(Integer, nullable=True)
    slide_num = Column(Integer, nullable=True)
    order_idx = Column(Integer, default=0)
    image_path = Column(String, nullable=True)
    meta = Column(JSON, default={})

    document = relationship("Document", back_populates="blocks")


# создание двух бд

def create_engine_and_session(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


library_engine, LibrarySession = create_engine_and_session(LIBRARY_DB_PATH)
temp_engine, TempSession = create_engine_and_session(TEMP_DB_PATH)


# =========================
# КОНТЕКСТНЫЕ МЕНЕДЖЕРЫ (удобно использовать)
# =========================

@contextmanager
def get_library_session():
    """Сессия для постоянной базы (предустановленные материалы)"""
    session = LibrarySession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_temp_session():
    """Сессия для временной базы (материалы учителя)"""
    session = TempSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# утилиты для временной бд

def clear_temp_database():
    """Полностью очищает временную базу (вызывать после создания викторины)"""
    with get_temp_session() as session:
        session.query(Block).delete()
        session.query(Document).delete()
        session.commit()
    print("[INFO] Временная база данных очищена")


def get_temp_documents_count() -> int:
    """Сколько документов сейчас во временной базе"""
    with get_temp_session() as session:
        return session.query(Document).count()


# инициализация бд

def init_databases():
    """Создаёт обе базы данных и таблицы"""
    print(f"Постоянная база: {LIBRARY_DB_PATH}")
    print(f"Временная база:  {TEMP_DB_PATH}")
    print("Базы данных успешно инициализированы.")


if __name__ == "__main__":
    init_databases()