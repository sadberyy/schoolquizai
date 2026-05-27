from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_access_token
from app.db.database import get_db_session
from app.db.models import Quiz, User

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    email: str


def _load_user(user_id: str) -> CurrentUser | None:
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return CurrentUser(id=user.id, name=user.name, email=user.email)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    user_id = verify_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Недействительный или просроченный токен")

    user = _load_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser | None:
    if credentials is None:
        return None

    user_id = verify_access_token(credentials.credentials)
    if not user_id:
        return None

    return _load_user(user_id)


def require_quiz_owner(quiz_id: str, teacher_id: str) -> Quiz:
    with get_db_session() as session:
        quiz = session.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Викторина не найдена")
        if quiz.teacher_id != teacher_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой викторине")
        return quiz
