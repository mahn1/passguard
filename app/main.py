from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
from app.routers import auth, entries, tools

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="PassGuard",
    description="Генератор, проверка надёжности и зашифрованное хранилище паролей",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(tools.router)
app.include_router(entries.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health", tags=["Служебное"])
def health() -> dict[str, str]:
    return {"status": "ok"}
