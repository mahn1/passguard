from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app import demo
from app.config import get_settings
from app.deps import DB, CurrentUser
from app.models import User
from app.ratelimit import demo_limit, login_limit, register_limit
from app.schemas import Credentials, Token, UserOut
from app.security import create_token, hash_password, verify_password
from app.strength import check

router = APIRouter(prefix="/api/auth", tags=["Авторизация"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(register_limit)],
)
def register(data: Credentials, db: DB) -> Token:
    if data.username.lower().startswith(demo.PREFIX):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Имена с префиксом demo- зарезервированы")
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Такое имя пользователя уже занято")
    report = check(data.password)
    if report.score < 2:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Мастер-пароль слишком слабый ({report.label}). " + "; ".join(report.suggestions[:2]),
        )
    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return Token(access_token=create_token(user.id))


@router.post("/login", response_model=Token, dependencies=[Depends(login_limit)])
def login(data: Credentials, db: DB) -> Token:
    user = db.scalar(select(User).where(User.username == data.username))
    # одинаковый ответ для неверного логина и пароля, чтобы не подсказывать, какие имена заняты
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверное имя пользователя или пароль")
    return Token(access_token=create_token(user.id))


@router.post(
    "/demo",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(demo_limit)],
    summary="Демо-аккаунт с примерами записей (только в демо-режиме)",
)
def demo_login(db: DB) -> Token:
    if not get_settings().demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Демо-режим выключен")
    return Token(access_token=create_token(demo.create_demo_user(db).id))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
