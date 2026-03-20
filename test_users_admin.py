"""
tests/test_users_admin.py
--------------------------
Tests for admin-only user management endpoints.
Also tests the RBAC boundary: regular users must be refused.
"""

import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.conftest import auth_headers, login_user, register_user


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_admin(db: Session, email="admin@test.com", password="Admin1234") -> tuple[str, str]:
    """
    Directly insert an admin user into the DB (bypassing the register endpoint
    which always creates regular users) and return credentials.
    """
    admin = User(
        email=email,
        full_name="Admin User",
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()
    return email, password


# ── List users (admin only) ───────────────────────────────────────────────────

class TestListUsers:

    def test_admin_can_list_users(self, client, db):
        email, password = make_admin(db)
        register_user(client, email="alice@test.com")

        admin_token, _ = login_user(client, email=email, password=password)
        resp = client.get("/api/v1/users", headers=auth_headers(admin_token))

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    def test_regular_user_cannot_list_users(self, client):
        register_user(client)
        token, _ = login_user(client)
        resp = client.get("/api/v1/users", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list_users(self, client):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 403


# ── Get user by ID (admin only) ───────────────────────────────────────────────

class TestGetUser:

    def test_admin_can_get_user_by_id(self, client, db):
        email, password = make_admin(db)
        register_user(client, email="bob@test.com")

        admin_token, _ = login_user(client, email=email, password=password)
        # get admin's own ID (id=1 in fresh DB)
        users_resp = client.get("/api/v1/users", headers=auth_headers(admin_token))
        user_id = users_resp.json()["items"][0]["id"]

        resp = client.get(f"/api/v1/users/{user_id}", headers=auth_headers(admin_token))
        assert resp.status_code == 200

    def test_get_nonexistent_user_returns_404(self, client, db):
        email, password = make_admin(db)
        admin_token, _ = login_user(client, email=email, password=password)
        resp = client.get("/api/v1/users/99999", headers=auth_headers(admin_token))
        assert resp.status_code == 404

    def test_regular_user_cannot_get_user_by_id(self, client, db):
        make_admin(db)
        register_user(client)
        token, _ = login_user(client)
        resp = client.get("/api/v1/users/1", headers=auth_headers(token))
        assert resp.status_code == 403


# ── Delete user (admin only) ──────────────────────────────────────────────────

class TestDeleteUser:

    def test_admin_can_delete_user(self, client, db):
        email, password = make_admin(db)
        register_user(client, email="victim@test.com")
        admin_token, _ = login_user(client, email=email, password=password)

        # find the victim's id
        users = client.get("/api/v1/users", headers=auth_headers(admin_token)).json()
        victim = next(u for u in users["items"] if u["email"] == "victim@test.com")

        resp = client.delete(f"/api/v1/users/{victim['id']}", headers=auth_headers(admin_token))
        assert resp.status_code == 204

        # Confirm gone
        resp2 = client.get(f"/api/v1/users/{victim['id']}", headers=auth_headers(admin_token))
        assert resp2.status_code == 404

    def test_admin_cannot_delete_self(self, client, db):
        """Prevent admins from locking themselves out."""
        email, password = make_admin(db)
        admin_token, _ = login_user(client, email=email, password=password)

        me = client.get("/api/v1/auth/me", headers=auth_headers(admin_token)).json()
        resp = client.delete(f"/api/v1/users/{me['id']}", headers=auth_headers(admin_token))
        assert resp.status_code == 400
        assert "cannot delete" in resp.json()["detail"].lower()

    def test_regular_user_cannot_delete_users(self, client, db):
        make_admin(db)
        register_user(client)
        token, _ = login_user(client)
        resp = client.delete("/api/v1/users/1", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_delete_nonexistent_user_returns_404(self, client, db):
        email, password = make_admin(db)
        admin_token, _ = login_user(client, email=email, password=password)
        resp = client.delete("/api/v1/users/99999", headers=auth_headers(admin_token))
        assert resp.status_code == 404


# ── Security helpers (unit-level) ─────────────────────────────────────────────

class TestSecurity:

    def test_health_endpoint_is_public(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_request_id_header_present(self, client):
        """Every response must carry an X-Request-ID header (from middleware)."""
        resp = client.get("/health")
        assert "x-request-id" in resp.headers

    def test_password_not_in_register_response(self, client):
        resp = register_user(client)
        body = resp.json()
        assert "password" not in body
        assert "hashed_password" not in body
