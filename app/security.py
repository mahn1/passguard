"""Хеширование паролей пользователей, JWT, шифрование записей хранилища."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt учитывает только первые 72 байта — режем явно, чтобы поведение было предсказуемым
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def create_token(user_id: int) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.token_ttl_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("не удалось расшифровать запись: сменился ключ шифрования?") from exc


def fingerprint(user_id: int, password: str) -> str:
    """Отпечаток пароля для поиска повторов. Привязан к пользователю, поэтому разные люди не сравниваются."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"{user_id}:{password}".encode(), hashlib.sha256).hexdigest()
