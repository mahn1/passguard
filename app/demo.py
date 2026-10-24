"""Демо-аккаунты для публичной версии: создаются одним кликом и удаляются через сутки."""

import secrets
from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.generator import GeneratorOptions, generate
from app.models import Entry, User, utcnow
from app.security import encrypt, fingerprint, hash_password
from app.strength import check

PREFIX = "demo-"

# Набор подобран так, чтобы аудит показал все виды проблем: слабые, повторы и старый пароль
SAMPLES = [
    ("GitHub", "demo-user", "https://github.com", None, 0),
    ("Почта", "demo@example.com", "https://mail.example.com", "Masha1995", 0),
    ("VK", "+7 900 000-00-00", "https://vk.com", "Kotik2024!", 0),
    ("Госуслуги", "demo@example.com", "https://gosuslugi.ru", "Kotik2024!", 0),
    ("Wi-Fi дома", "", "", "qwerty123", 0),
    ("Банк", "demo@example.com", "https://bank.example.com", None, 200),
]


def _cleanup(db: Session) -> None:
    limit = utcnow() - timedelta(hours=get_settings().demo_ttl_hours)
    for user in db.scalars(select(User).where(User.username.startswith(PREFIX))):
        # SQLite отдаёт время без часового пояса — считаем его UTC
        created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=UTC)
        if created < limit:
            db.delete(user)


def create_demo_user(db: Session) -> User:
    _cleanup(db)
    user = User(username=PREFIX + secrets.token_hex(3), password_hash=hash_password(secrets.token_urlsafe(32)))
    db.add(user)
    db.flush()
    for title, login, url, password, age_days in SAMPLES:
        password = password or generate(GeneratorOptions(length=20))
        db.add(
            Entry(
                owner_id=user.id,
                title=title,
                login=login,
                url=url,
                password_encrypted=encrypt(password),
                password_fingerprint=fingerprint(user.id, password),
                strength_score=check(password).score,
                password_changed_at=utcnow() - timedelta(days=age_days),
            )
        )
    db.commit()
    return user
