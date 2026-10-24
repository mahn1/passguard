from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models import Entry, utcnow
from app.schemas import AuditOut, EntryCreate, EntryOut, EntryUpdate, EntryWithPassword
from app.security import decrypt, encrypt, fingerprint
from app.strength import check

router = APIRouter(prefix="/api/entries", tags=["Хранилище"])

OLD_AFTER = timedelta(days=180)
SORTS = {
    "title": Entry.title.asc(),
    "updated": Entry.updated_at.desc(),
    "weakest": Entry.strength_score.asc(),
}


def _get_owned(db: DB, user_id: int, entry_id: int) -> Entry:
    entry = db.get(Entry, entry_id)
    # чужие записи отдаём как «не найдено», чтобы не раскрывать, что такой id существует
    if not entry or entry.owner_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись не найдена")
    return entry


def _set_password(entry: Entry, user_id: int, password: str) -> None:
    entry.password_encrypted = encrypt(password)
    entry.password_fingerprint = fingerprint(user_id, password)
    entry.strength_score = check(password).score
    entry.password_changed_at = utcnow()


def _with_password(entry: Entry) -> EntryWithPassword:
    return EntryWithPassword(**EntryOut.model_validate(entry).model_dump(), password=decrypt(entry.password_encrypted))


@router.get("", response_model=list[EntryOut])
def list_entries(
    db: DB,
    user: CurrentUser,
    q: str = Query("", max_length=100, description="Поиск по названию, логину и адресу"),
    sort: str = Query("title", pattern="^(title|updated|weakest)$"),
) -> list[Entry]:
    stmt = select(Entry).where(Entry.owner_id == user.id).order_by(SORTS[sort], Entry.id)
    entries = list(db.scalars(stmt))
    # Фильтруем в Python: LIKE в SQLite не учитывает регистр кириллицы, а записей у одного человека немного
    needle = q.strip().casefold()
    if needle:
        entries = [e for e in entries if any(needle in field.casefold() for field in (e.title, e.login, e.url))]
    return entries


@router.post("", response_model=EntryWithPassword, status_code=status.HTTP_201_CREATED)
def create_entry(data: EntryCreate, db: DB, user: CurrentUser) -> EntryWithPassword:
    entry = Entry(owner_id=user.id, **data.model_dump(exclude={"password"}))
    _set_password(entry, user.id, data.password)
    db.add(entry)
    db.commit()
    return _with_password(entry)


@router.get("/audit", response_model=AuditOut)
def audit(db: DB, user: CurrentUser) -> AuditOut:
    entries = list(db.scalars(select(Entry).where(Entry.owner_id == user.id).order_by(Entry.title)))
    groups: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        groups[e.password_fingerprint].append(e)
    reused = [g for g in groups.values() if len(g) > 1]

    now = datetime.now(UTC)

    def changed_at(e: Entry) -> datetime:
        # SQLite возвращает время без часового пояса — считаем его UTC
        return e.password_changed_at if e.password_changed_at.tzinfo else e.password_changed_at.replace(tzinfo=UTC)

    weak = [e for e in entries if e.strength_score < 3]
    old = [e for e in entries if now - changed_at(e) > OLD_AFTER]
    problems = {e.id for e in weak} | {e.id for g in reused for e in g} | {e.id for e in old}
    health = round(100 * (len(entries) - len(problems)) / len(entries)) if entries else 100

    return AuditOut(
        total=len(entries),
        weak=[EntryOut.model_validate(e) for e in weak],
        reused=[[EntryOut.model_validate(e) for e in g] for g in reused],
        old=[EntryOut.model_validate(e) for e in old],
        health=health,
    )


@router.get("/{entry_id}", response_model=EntryWithPassword)
def get_entry(entry_id: int, db: DB, user: CurrentUser) -> EntryWithPassword:
    return _with_password(_get_owned(db, user.id, entry_id))


@router.patch("/{entry_id}", response_model=EntryWithPassword)
def update_entry(entry_id: int, data: EntryUpdate, db: DB, user: CurrentUser) -> EntryWithPassword:
    entry = _get_owned(db, user.id, entry_id)
    changes = data.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    for field, value in changes.items():
        if value is not None:
            setattr(entry, field, value.strip() if isinstance(value, str) and field != "notes" else value)
    if password is not None:
        _set_password(entry, user.id, password)
    db.commit()
    return _with_password(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, db: DB, user: CurrentUser) -> Response:
    db.delete(_get_owned(db, user.id, entry_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
