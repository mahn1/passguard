from datetime import timedelta

import pytest

from app.config import get_settings
from app.db import SessionLocal
from app.models import User, utcnow
from tests.conftest import STRONG


@pytest.fixture
def demo_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)


def test_demo_disabled_by_default(client):
    assert client.get("/api/config").json() == {"demo_mode": False}
    assert client.post("/api/auth/demo").status_code == 404


def test_demo_account_has_sample_data(client, demo_mode):
    assert client.get("/api/config").json() == {"demo_mode": True}
    r = client.post("/api/auth/demo")
    assert r.status_code == 201
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/auth/me", headers=auth).json()["username"].startswith("demo-")
    assert len(client.get("/api/entries", headers=auth).json()) == 6
    audit = client.get("/api/entries/audit", headers=auth).json()
    assert audit["weak"] and audit["reused"] and audit["old"]


def test_old_demo_accounts_are_removed(client, demo_mode):
    client.post("/api/auth/demo")
    with SessionLocal() as db:
        old = db.query(User).one()
        old.created_at = utcnow() - timedelta(hours=25)
        db.commit()
        old_id = old.id

    client.post("/api/auth/demo")
    with SessionLocal() as db:
        assert db.get(User, old_id) is None
        assert db.query(User).count() == 1


def test_demo_prefix_is_reserved(client):
    r = client.post("/api/auth/register", json={"username": "demo-admin", "password": STRONG})
    assert r.status_code == 422


def test_login_rate_limit(client):
    body = {"username": "nobody", "password": "Wrong-Password#1"}
    codes = [client.post("/api/auth/login", json=body).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def login_codes(client, ips):
    body = {"username": "nobody", "password": "Wrong-Password#1"}
    return [client.post("/api/auth/login", json=body, headers={"CF-Connecting-IP": ip}).status_code for ip in ips]


def test_cloudflare_header_ignored_by_default(client):
    # без доверия к прокси подделанный заголовок не помогает обойти лимит
    assert login_codes(client, [f"10.0.0.{i}" for i in range(11)])[-1] == 429


def test_cloudflare_header_separates_clients(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "trust_cloudflare", True)
    assert login_codes(client, ["1.1.1.1"] * 10 + ["2.2.2.2"])[-1] == 401
    assert login_codes(client, ["1.1.1.1"])[-1] == 429
