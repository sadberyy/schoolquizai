from app.db.database import Base, engine
from app.db import models  # noqa: F401


def init_db():
    Base.metadata.create_all(bind=engine)
    print("База данных успешно инициализирована.")


if __name__ == "__main__":
    init_db()