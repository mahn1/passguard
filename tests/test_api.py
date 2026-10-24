from datetime import timedelta

from app.db import SessionLocal
from app.models import Entry, utcnow
from tests.conftest import STRONG, register

GOOD = "Xr7#pLq9!vTz2mWk"


def add(client, auth, **data):
    payload = {"title": "Сайт", "password": GOOD} | data
    r = client.post("/api/entries", json=payload, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# --- авторизация ---


def test_register_login_me(client):
    register(client, "bob")
    r = client.post("/api/auth/login", json={"username": "bob", "password": STRONG})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["username"] == "bob"


def test_register_rejects_weak_password(client):
    r = client.post("/api/auth/register", json={"username": "bob", "password": "qwerty123"})
    assert r.status_code == 422


def test_register_duplicate(client, auth):
    r = client.post("/api/auth/register", json={"username": "alice", "password": STRONG})
    assert r.status_code == 409


def test_login_wrong_password(client, auth):
    r = client.post("/api/auth/login", json={"username": "alice", "password": "Wrong-Password#1"})
    assert r.status_code == 401
    r2 = client.post("/api/auth/login", json={"username": "nobody", "password": STRONG})
    assert r2.json() == r.json()  # не выдаём, существует ли пользователь


def test_entries_require_auth(client):
    assert client.get("/api/entries").status_code == 401
    assert client.get("/api/entries", headers={"Authorization": "Bearer garbage"}).status_code == 401


# --- инструменты ---


def test_generate_endpoint(client):
    r = client.post("/api/tools/generate", json={"length": 24, "count": 3})
    assert r.status_code == 200
    items = r.json()["passwords"]
    assert len(items) == 3
    assert all(len(i["password"]) == 24 and i["strength"]["score"] == 4 for i in items)


def test_generate_rejects_no_sets(client):
    r = client.post("/api/tools/generate", json={"lower": False, "upper": False, "digits": False, "symbols": False})
    assert r.status_code == 422


def test_check_endpoint(client):
    r = client.post("/api/tools/check", json={"password": "123456"})
    assert r.status_code == 200
    assert r.json()["score"] == 0


# --- CRUD ---


def test_crud_cycle(client, auth):
    created = add(client, auth, title="  GitHub ", login="mahni", url="https://github.com")
    assert created["title"] == "GitHub"
    assert created["password"] == GOOD
    entry_id = created["id"]

    listed = client.get("/api/entries", headers=auth).json()
    assert [e["id"] for e in listed] == [entry_id]
    assert "password" not in listed[0]  # в списке пароли не отдаются

    r = client.patch(f"/api/entries/{entry_id}", json={"password": "123456", "notes": "рабочий"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["password"] == "123456"
    assert r.json()["strength_score"] == 0
    assert r.json()["title"] == "GitHub"

    assert client.delete(f"/api/entries/{entry_id}", headers=auth).status_code == 204
    assert client.get(f"/api/entries/{entry_id}", headers=auth).status_code == 404


def test_password_is_encrypted_at_rest(client, auth):
    entry_id = add(client, auth)["id"]
    with SessionLocal() as db:
        stored = db.get(Entry, entry_id).password_encrypted
    assert GOOD not in stored


def test_search_and_sort(client, auth):
    add(client, auth, title="Почта Яндекс", password="123456")
    add(client, auth, title="GitHub", login="mahni")
    add(client, auth, title="Госуслуги", url="https://gosuslugi.ru")

    def titles(**params):
        return [e["title"] for e in client.get("/api/entries", params=params, headers=auth).json()]

    assert titles(q="ПОЧТА") == ["Почта Яндекс"]  # регистр кириллицы не важен
    assert titles(q="mahni") == ["GitHub"]
    assert titles(q="gosuslugi") == ["Госуслуги"]
    assert titles(sort="weakest")[0] == "Почта Яндекс"
    assert client.get("/api/entries", params={"sort": "bad"}, headers=auth).status_code == 422


def test_users_are_isolated(client, auth):
    entry_id = add(client, auth)["id"]
    other = register(client, "mallory")
    assert client.get("/api/entries", headers=other).json() == []
    assert client.get(f"/api/entries/{entry_id}", headers=other).status_code == 404
    assert client.patch(f"/api/entries/{entry_id}", json={"title": "x"}, headers=other).status_code == 404
    assert client.delete(f"/api/entries/{entry_id}", headers=other).status_code == 404


def test_validation(client, auth):
    r = client.post("/api/entries", json={"title": "", "password": "x"}, headers=auth)
    assert r.status_code == 422


# --- аудит ---


def test_audit(client, auth):
    assert client.get("/api/entries/audit", headers=auth).json()["health"] == 100

    add(client, auth, title="VK", password="Same-Pass-2024!")
    add(client, auth, title="Mail", password="Same-Pass-2024!")
    add(client, auth, title="Bank", password="123456")
    old_id = add(client, auth, title="Old")["id"]
    add(client, auth, title="Good", password="t9$Kq!Lm2#Vw8@Zr")
    with SessionLocal() as db:
        db.get(Entry, old_id).password_changed_at = utcnow() - timedelta(days=200)
        db.commit()

    audit = client.get("/api/entries/audit", headers=auth).json()
    assert audit["total"] == 5
    assert "Bank" in {e["title"] for e in audit["weak"]}
    assert [sorted(e["title"] for e in g) for g in audit["reused"]] == [["Mail", "VK"]]
    assert [e["title"] for e in audit["old"]] == ["Old"]
    assert audit["health"] == 20


def test_same_password_different_users_not_reused(client, auth):
    add(client, auth, password="Shared-Pass-77!")
    other = register(client, "bob")
    add(client, other, password="Shared-Pass-77!")
    assert client.get("/api/entries/audit", headers=auth).json()["reused"] == []
