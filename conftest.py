"""
tests/conftest.py
-----------------
Shared pytest fixtures.

Uses an in-memory SQLite database so tests require no running Postgres.
SQLite covers all the logic we need to test (auth, CRUD, RBAC).
The `client` fixture provides a fully-wired TestClient with the DB
dependency overridden — every test gets a fresh, isolated database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Override DATABASE_URL before the app loads settings
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-1234")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# ── In-memory SQLite engine ───────────────────────────────────────────────────
SQLITE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + threading
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def db():
    """
    Each test function gets:
    - A fresh schema (all tables created)
    - A clean session
    - Full teardown after the test
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """
    FastAPI TestClient with the real `get_db` dependency swapped out
    for our in-memory SQLite session.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # session lifecycle managed by the `db` fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Convenience helpers used by multiple test modules ─────────────────────────

def register_user(client, email="user@test.com", password="Test1234", full_name="Test User"):
    """Register a user and return the response JSON."""
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": full_name,
        "password": password,
    })
    return resp


def login_user(client, email="user@test.com", password="Test1234"):
    """Login and return (access_token, refresh_token)."""
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    data = resp.json()
    return data.get("access_token"), data.get("refresh_token")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
