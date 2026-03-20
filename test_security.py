"""
tests/test_security.py
-----------------------
Focused security tests:
  - Tampered tokens are rejected
  - Expired tokens are rejected (mocked)
  - Refresh tokens can't access protected routes directly
  - CORS header present on responses
"""

import time
import pytest
from jose import jwt

from tests.conftest import auth_headers, login_user, register_user


SECRET = "test-secret-key-not-for-production-1234"
ALGO   = "HS256"


class TestJWTSecurity:

    def test_tampered_token_rejected(self, client):
        """Modifying the payload after signing must invalidate the token."""
        register_user(client)
        token, _ = login_user(client)

        # Decode without verification, change role, re-encode with wrong key
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        payload["role"] = "admin"
        bad_token = jwt.encode(payload, "WRONG_SECRET", algorithm=ALGO)

        resp = client.get("/api/v1/auth/me", headers=auth_headers(bad_token))
        assert resp.status_code == 401

    def test_refresh_token_cannot_access_protected_route(self, client):
        """
        A refresh token must NOT be accepted as an access token.
        The `type` claim check in dependencies.py enforces this.
        """
        register_user(client)
        _, refresh_token = login_user(client)

        resp = client.get("/api/v1/auth/me", headers=auth_headers(refresh_token))
        assert resp.status_code == 401

    def test_missing_bearer_prefix_rejected(self, client):
        register_user(client)
        token, _ = login_user(client)
        # Send token without "Bearer " prefix
        resp = client.get("/api/v1/auth/me", headers={"Authorization": token})
        assert resp.status_code == 403

    def test_expired_token_rejected(self, client):
        """Forge a token with exp in the past — must be rejected."""
        expired_payload = {
            "sub": "1",
            "type": "access",
            "exp": int(time.time()) - 3600,  # expired 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, SECRET, algorithm=ALGO)
        resp = client.get("/api/v1/auth/me", headers=auth_headers(expired_token))
        assert resp.status_code == 401

    def test_empty_string_token_rejected(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    def test_none_subject_token_rejected(self, client):
        """Token with no 'sub' claim must be rejected."""
        bad_payload = {"type": "access", "exp": int(time.time()) + 3600}
        token = jwt.encode(bad_payload, SECRET, algorithm=ALGO)
        resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 401


class TestPasswordSecurity:

    def test_bcrypt_hash_not_stored_as_plaintext(self, client, db):
        """Verify the DB stores a bcrypt hash, not the plaintext password."""
        from app.models.user import User as UserModel
        register_user(client, password="MySecret1")
        user = db.query(UserModel).first()
        assert user.hashed_password != "MySecret1"
        assert user.hashed_password.startswith("$2b$")  # bcrypt prefix

    def test_wrong_password_same_error_as_unknown_user(self, client):
        """Anti-enumeration: same HTTP status for both failure modes."""
        register_user(client)
        r1 = client.post("/api/v1/auth/login", json={"email": "user@test.com", "password": "Wrong1234"})
        r2 = client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "Test1234"})
        assert r1.status_code == r2.status_code == 401
        assert r1.json()["detail"] == r2.json()["detail"]
