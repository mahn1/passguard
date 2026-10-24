import os

# Ключи и база задаются до импорта приложения: тесты не трогают .env и файл БД
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ENCRYPTION_KEY"] = "q2t3QYt4oDdNbrDqpThI0b8tZbEJV8zG6EGgW8ElH2k="
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.db import Base, engine
from app.main import app

STRONG = "Lavka-Sinyaya#2077"


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    for limiter in ratelimit.ALL:
        limiter.reset()
    with TestClient(app) as c:
        yield c


def register(client: TestClient, username: str = "alice", password: str = STRONG) -> dict[str, str]:
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register(client)
