from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.generator import MAX_LENGTH, MIN_LENGTH


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    created_at: datetime


class GenerateParams(BaseModel):
    length: int = Field(16, ge=MIN_LENGTH, le=MAX_LENGTH)
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True
    exclude_ambiguous: bool = False
    count: int = Field(1, ge=1, le=10)


class PasswordIn(BaseModel):
    password: str = Field(max_length=256)


class StrengthOut(BaseModel):
    score: int
    label: str
    entropy_bits: float
    crack_time_offline: str
    crack_time_online: str
    warnings: list[str]
    suggestions: list[str]


class EntryBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    login: str = Field("", max_length=200)
    url: str = Field("", max_length=500)
    notes: str = Field("", max_length=5000)

    @field_validator("title", "login", "url")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class EntryCreate(EntryBase):
    password: str = Field(min_length=1, max_length=256)


class EntryUpdate(BaseModel):
    """Частичное обновление: передаются только изменённые поля."""

    title: str | None = Field(None, min_length=1, max_length=100)
    login: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=5000)
    password: str | None = Field(None, min_length=1, max_length=256)


class EntryOut(EntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    strength_score: int
    created_at: datetime
    updated_at: datetime
    password_changed_at: datetime


class EntryWithPassword(EntryOut):
    password: str


class AuditOut(BaseModel):
    total: int
    weak: list[EntryOut]
    reused: list[list[EntryOut]]
    old: list[EntryOut]
    health: int  # 0–100: доля записей без проблем
