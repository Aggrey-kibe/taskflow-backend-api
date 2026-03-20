"""
tests/test_tasks.py
-------------------
Tests for: create · list · get · patch · delete tasks
Covers: ownership isolation, pagination, status filtering, partial updates.
"""

import pytest
from tests.conftest import auth_headers, login_user, register_user


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_task(client, token, **overrides):
    payload = {
        "title": "Default Task",
        "description": "A test task",
        "status": "todo",
        **overrides,
    }
    return client.post("/api/v1/tasks", json=payload, headers=auth_headers(token))


def setup_user(client, email="alice@test.com", password="Test1234"):
    register_user(client, email=email, password=password, full_name="Alice")
    return login_user(client, email=email, password=password)


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreateTask:

    def test_create_task_success(self, client):
        token, _ = setup_user(client)
        resp = create_task(client, token, title="Write unit tests")
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Write unit tests"
        assert body["status"] == "todo"
        assert "id" in body
        assert "owner_id" in body

    def test_create_task_with_due_date(self, client):
        token, _ = setup_user(client)
        resp = create_task(client, token, due_date="2026-12-31T00:00:00Z")
        assert resp.status_code == 201
        assert resp.json()["due_date"] is not None

    def test_create_task_requires_auth(self, client):
        resp = client.post("/api/v1/tasks", json={"title": "No auth"})
        assert resp.status_code == 403

    def test_create_task_empty_title_fails(self, client):
        token, _ = setup_user(client)
        resp = create_task(client, token, title="")
        assert resp.status_code == 422

    def test_create_task_invalid_status(self, client):
        token, _ = setup_user(client)
        resp = create_task(client, token, status="flying")
        assert resp.status_code == 422


# ── List ──────────────────────────────────────────────────────────────────────

class TestListTasks:

    def test_list_returns_only_own_tasks(self, client):
        """Users must NOT see each other's tasks."""
        token_a, _ = setup_user(client, email="a@test.com")
        token_b, _ = setup_user(client, email="b@test.com")

        create_task(client, token_a, title="Alice task")
        create_task(client, token_b, title="Bob task")

        resp = client.get("/api/v1/tasks", headers=auth_headers(token_a))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "Alice task"

    def test_list_pagination(self, client):
        token, _ = setup_user(client)
        for i in range(5):
            create_task(client, token, title=f"Task {i}")

        resp = client.get("/api/v1/tasks?page=1&page_size=2", headers=auth_headers(token))
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 2

    def test_list_filter_by_status(self, client):
        token, _ = setup_user(client)
        create_task(client, token, title="Todo task", status="todo")
        create_task(client, token, title="Done task", status="done")

        resp = client.get("/api/v1/tasks?status=done", headers=auth_headers(token))
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "done"

    def test_list_empty_for_new_user(self, client):
        token, _ = setup_user(client)
        resp = client.get("/api/v1/tasks", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── Get by ID ─────────────────────────────────────────────────────────────────

class TestGetTask:

    def test_get_own_task(self, client):
        token, _ = setup_user(client)
        task_id = create_task(client, token).json()["id"]
        resp = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == task_id

    def test_get_other_users_task_returns_403(self, client):
        token_a, _ = setup_user(client, email="a@test.com")
        token_b, _ = setup_user(client, email="b@test.com")
        task_id = create_task(client, token_a).json()["id"]

        resp = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers(token_b))
        assert resp.status_code == 403

    def test_get_nonexistent_task_returns_404(self, client):
        token, _ = setup_user(client)
        resp = client.get("/api/v1/tasks/99999", headers=auth_headers(token))
        assert resp.status_code == 404


# ── Patch (partial update) ────────────────────────────────────────────────────

class TestUpdateTask:

    def test_update_status_only(self, client):
        token, _ = setup_user(client)
        task_id = create_task(client, token, title="My task").json()["id"]

        resp = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"status": "done"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["title"] == "My task"  # unchanged

    def test_update_multiple_fields(self, client):
        token, _ = setup_user(client)
        task_id = create_task(client, token).json()["id"]

        resp = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Renamed", "status": "in_progress"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Renamed"
        assert body["status"] == "in_progress"

    def test_update_other_users_task_returns_403(self, client):
        token_a, _ = setup_user(client, email="a@test.com")
        token_b, _ = setup_user(client, email="b@test.com")
        task_id = create_task(client, token_a).json()["id"]

        resp = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Hijacked"},
            headers=auth_headers(token_b),
        )
        assert resp.status_code == 403


# ── Delete ────────────────────────────────────────────────────────────────────

class TestDeleteTask:

    def test_delete_own_task(self, client):
        token, _ = setup_user(client)
        task_id = create_task(client, token).json()["id"]

        resp = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers(token))
        assert resp.status_code == 204

        # Confirm it's gone
        get_resp = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers(token))
        assert get_resp.status_code == 404

    def test_delete_other_users_task_returns_403(self, client):
        token_a, _ = setup_user(client, email="a@test.com")
        token_b, _ = setup_user(client, email="b@test.com")
        task_id = create_task(client, token_a).json()["id"]

        resp = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers(token_b))
        assert resp.status_code == 403

    def test_delete_nonexistent_task_returns_404(self, client):
        token, _ = setup_user(client)
        resp = client.delete("/api/v1/tasks/99999", headers=auth_headers(token))
        assert resp.status_code == 404
