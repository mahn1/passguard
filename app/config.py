"""Настройки приложения из переменных окружения или файла .env."""

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{(ROOT / 'passguard.db').as_posix()}"
    secret_key: str = ""  # подпись JWT и HMAC-отпечатков паролей
    encryption_key: str = ""  # ключ Fernet для шифрования паролей в хранилище
    token_ttl_minutes: int = 60 * 12
    demo_mode: bool = False  # публичное демо: вход без регистрации и плашка «не храните настоящие пароли»
    demo_ttl_hours: int = 24  # через сколько удалять демо-аккаунты
    # Включать только за Cloudflare: тогда IP клиента берётся из CF-Connecting-IP, иначе заголовок легко подделать
    trust_cloudflare: bool = False


def _ensure_keys(settings: Settings) -> Settings:
    """При первом запуске генерирует ключи и сохраняет их в .env, чтобы данные читались после перезапуска."""
    new_lines = []
    if not settings.secret_key:
        settings.secret_key = secrets.token_urlsafe(48)
        new_lines.append(f"SECRET_KEY={settings.secret_key}")
    if not settings.encryption_key:
        settings.encryption_key = Fernet.generate_key().decode()
        new_lines.append(f"ENCRYPTION_KEY={settings.encryption_key}")
    if new_lines:
        try:
            with ENV_FILE.open("a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            log.warning("Сгенерированы ключи и записаны в %s. Не теряйте этот файл и не публикуйте его.", ENV_FILE)
        except OSError:
            # на хостинге каталог может быть только для чтения: ключи живут до перезапуска, как и временная база
            log.warning("Ключи сгенерированы, но %s недоступен для записи — они действуют до перезапуска.", ENV_FILE)
    return settings


@lru_cache
def get_settings() -> Settings:
    return _ensure_keys(Settings())
