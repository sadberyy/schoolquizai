from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import hashlib

from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token
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


class AuthUserResponse(BaseModel):
    ok: bool = True
    access_token: str
    user_id: str
    name: str
    email: str


class MeResponse(BaseModel):
    user_id: str
    name: str
    email: str


def hash_password(password: str) -> str:
    """Хеширует пароль через SHA-256 (для хакатона достаточно)"""
    return hashlib.sha256(password.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _auth_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
        name=user.name,
        email=user.email,
    )


@router.post("/register", response_model=AuthUserResponse)
def register(data: RegisterRequest):
    """Регистрация нового учителя"""
    email = _normalize_email(data.email)
    name = data.name.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Введите имя")
    if not email:
        raise HTTPException(status_code=400, detail="Введите email")
    if not data.password:
        raise HTTPException(status_code=400, detail="Введите пароль")

    with get_db_session() as session:
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

        user = User(
            name=name,
            email=email,
            password_hash=hash_password(data.password),
        )
        session.add(user)
        session.flush()
        saved_user_id = user.id
        saved_name = user.name
        saved_email = user.email
        session.commit()

    return AuthUserResponse(
        access_token=create_access_token(saved_user_id),
        user_id=saved_user_id,
        name=saved_name,
        email=saved_email,
    )


@router.post("/login", response_model=AuthUserResponse)
def login(data: LoginRequest):
    """Вход учителя по email и паролю"""
    email = _normalize_email(data.email)

    with get_db_session() as session:
        user = session.query(User).filter(User.email == email).first()

        if not user or user.password_hash != hash_password(data.password):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        saved_user_id = user.id
        saved_name = user.name
        saved_email = user.email

    return AuthUserResponse(
        access_token=create_access_token(saved_user_id),
        user_id=saved_user_id,
        name=saved_name,
        email=saved_email,
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUser = Depends(get_current_user)):
    return MeResponse(
        user_id=current_user.id,
        name=current_user.name,
        email=current_user.email,
    )
