from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import hashlib

from app.db.database import get_db_session
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    """Хеширует пароль через SHA-256 (для хакатона достаточно)"""
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/register")
def register(data: RegisterRequest):
    """Регистрация нового учителя"""
    with get_db_session() as session:
        # Проверяем, нет ли уже такого email
        existing = session.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        
        # Создаём пользователя
        user = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
        )
        session.add(user)
        session.flush()  # получаем id внутри сессии
        
        # Сохраняем данные до выхода из with
        saved_user_id = user.id
        saved_name = user.name
        saved_email = user.email
        
        session.commit()
    
    return {
        "ok": True,
        "user_id": saved_user_id,
        "name": saved_name,
        "email": saved_email
    }


@router.post("/login")
def login(data: LoginRequest):
    """Вход учителя по email и паролю"""
    with get_db_session() as session:
        user = session.query(User).filter(User.email == data.email).first()
        
        if not user or user.password_hash != hash_password(data.password):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")
        
        # Сохраняем данные до выхода из with
        saved_user_id = user.id
        saved_name = user.name
        saved_email = user.email
    
    return {
        "ok": True,
        "user_id": saved_user_id,
        "name": saved_name,
        "email": saved_email
    }