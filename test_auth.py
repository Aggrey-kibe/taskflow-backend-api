"""
tests/test_auth.py
------------------
Tests for:  register · login · token refresh · /me · upgrade to premium

Each test is fully isolated — fresh DB per function via conftest fixtures.
"""

import pytest
from tests.conftest import auth_headers, login_user, register_user


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegister:

    def test_register_success(self, client):
        resp = register_user(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "user@test.com"
        assert body["role"] == "user"
        assert body["subscription_plan"] == "free"
        assert "hashed_password" not in body  # must never be exposed

    def test_register_duplicate_email(self, client):
        register_user(client)
        resp = register_user(client)  # same email again
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"].lower()

    def test_register_weak_password_no_digit(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "x@test.com", "full_name": "X", "password": "onlyletters"
        })
        assert resp.status_code == 422

    def test_register_weak_password_too_short(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "x@test.com", "full_name": "X", "password": "Ab1"
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email", "full_name": "X", "password": "Valid1234"
        })
        assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:

    def test_login_success(self, client):
        register_user(client)
        resp = client.post("/api/v1/auth/login", json={
            "email": "user@test.com", "password": "Test1234"
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        register_user(client)
        resp = client.post("/api/v1/auth/login", json={
            "email": "user@test.com", "password": "WrongPass9"
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "ghost@test.com", "password": "Test1234"
        })
        assert resp.status_code == 401

    def test_login_returns_generic_error(self, client):
        """Both wrong email and wrong password must return the same message
        to prevent user enumeration attacks."""
        resp_no_user = client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com", "password": "Test1234"
        })
        register_user(client)
        resp_bad_pass = client.post("/api/v1/auth/login", json={
            "email": "user@test.com", "password": "WrongPass9"
        })
        assert resp_no_user.json()["detail"] == resp_bad_pass.json()["detail"]


# ── Token refresh ─────────────────────────────────────────────────────────────

class TestRefresh:

    def test_refresh_success(self, client):
        register_user(client)
        _, refresh_token = login_user(client)
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_refresh_with_access_token_fails(self, client):
        """Access tokens must not be accepted as refresh tokens."""
        register_user(client)
        access_token, _ = login_user(client)
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    def test_refresh_with_garbage_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.token"})
        assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

class TestMe:

    def test_me_authenticated(self, client):
        register_user(client)
        token, _ = login_user(client)
        resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "user@test.com"

    def test_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 403  # HTTPBearer returns 403 when header absent

    def test_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401


# ── Upgrade ───────────────────────────────────────────────────────────────────

class TestUpgrade:

    def test_upgrade_to_premium(self, client):
        register_user(client)
        token, _ = login_user(client)
        resp = client.post("/api/v1/auth/upgrade", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["subscription_plan"] == "premium"
        assert "upgraded_at" in body

    def test_upgrade_requires_auth(self, client):
        resp = client.post("/api/v1/auth/upgrade")
        assert resp.status_code == 403
