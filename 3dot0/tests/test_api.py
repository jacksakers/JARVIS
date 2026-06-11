"""
Tests for the FastAPI REST API endpoints.
Uses the in-memory DB and TestClient from conftest.py.
No LLM or background worker is started.
"""
import pytest
from sqlmodel import Session, select

from app.models import FeedItem, FeedItemType, JournalEntry, Routine, Task, TaskStatus, TriggerType, User


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── /api/v1/users ─────────────────────────────────────────────────────────────

class TestUsersAPI:
    def test_list_users(self, client, primary_user):
        resp = client.get("/api/v1/users/")
        assert resp.status_code == 200
        data = resp.json()
        assert any(u["name"] == primary_user.name for u in data)

    def test_get_primary_user(self, client, primary_user):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["is_primary"] is True


# ── /api/v1/routines ──────────────────────────────────────────────────────────

class TestRoutinesAPI:
    def test_create_routine(self, client, primary_user):
        payload = {
            "name": "Morning Briefing",
            "description": "Daily AM summary",
            "trigger_type": "cron",
            "trigger_value": "0 6 * * *",
            "system_prompt": "Generate a morning briefing.",
            "allowed_skill_names": '["get_system_time"]',
            "active": True,
        }
        resp = client.post("/api/v1/routines/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Morning Briefing"
        assert data["trigger_type"] == "cron"

    def test_list_routines(self, client, primary_user, session):
        routine = Routine(
            user_id=primary_user.id,
            name="Test Routine",
            trigger_type=TriggerType.manual,
        )
        session.add(routine)
        session.commit()

        resp = client.get("/api/v1/routines/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_routine(self, client, primary_user, session):
        routine = Routine(user_id=primary_user.id, name="Old Name")
        session.add(routine)
        session.commit()
        session.refresh(routine)

        resp = client.patch(
            f"/api/v1/routines/{routine.id}",
            json={"name": "New Name", "active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["active"] is False

    def test_delete_routine(self, client, primary_user, session):
        routine = Routine(user_id=primary_user.id, name="To Delete")
        session.add(routine)
        session.commit()
        session.refresh(routine)

        resp = client.delete(f"/api/v1/routines/{routine.id}")
        assert resp.status_code == 204

        resp = client.get(f"/api/v1/routines/{routine.id}")
        assert resp.status_code == 404

    def test_get_nonexistent_routine(self, client):
        resp = client.get("/api/v1/routines/99999")
        assert resp.status_code == 404


# ── /api/v1/tasks ─────────────────────────────────────────────────────────────

class TestTasksAPI:
    def test_submit_task(self, client):
        resp = client.post("/api/v1/tasks/", json={"prompt": "Research Python async."})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "queued"
        assert data["prompt"] == "Research Python async."

    def test_list_tasks(self, client, primary_user, session):
        task = Task(user_id=primary_user.id, prompt="Test task", status=TaskStatus.queued)
        session.add(task)
        session.commit()

        resp = client.get("/api/v1/tasks/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_tasks_by_status(self, client, primary_user, session):
        task = Task(user_id=primary_user.id, prompt="Done task", status=TaskStatus.done)
        session.add(task)
        session.commit()

        resp = client.get("/api/v1/tasks/?status=done")
        assert resp.status_code == 200
        for t in resp.json():
            assert t["status"] == "done"

    def test_cancel_queued_task(self, client, primary_user, session):
        task = Task(user_id=primary_user.id, prompt="To cancel", status=TaskStatus.queued)
        session.add(task)
        session.commit()
        session.refresh(task)

        resp = client.delete(f"/api/v1/tasks/{task.id}")
        assert resp.status_code == 204

    def test_cancel_running_task_rejected(self, client, primary_user, session):
        task = Task(user_id=primary_user.id, prompt="Running task", status=TaskStatus.running)
        session.add(task)
        session.commit()
        session.refresh(task)

        resp = client.delete(f"/api/v1/tasks/{task.id}")
        assert resp.status_code == 409


# ── /api/v1/feed ──────────────────────────────────────────────────────────────

class TestFeedAPI:
    def test_list_feed_empty(self, client):
        resp = client.get("/api/v1/feed/")
        assert resp.status_code == 200

    def test_mark_as_read(self, client, primary_user, session):
        item = FeedItem(
            user_id=primary_user.id,
            type=FeedItemType.report,
            title="Test Report",
            content_markdown="# Hello",
            content_html="<h1>Hello</h1>",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        resp = client.post(f"/api/v1/feed/{item.id}/read")
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    def test_mark_all_read(self, client, primary_user, session):
        for i in range(3):
            item = FeedItem(
                user_id=primary_user.id,
                title=f"Item {i}",
                content_markdown="content",
                content_html="<p>content</p>",
            )
            session.add(item)
        session.commit()

        resp = client.post("/api/v1/feed/read-all")
        assert resp.status_code == 200
        assert resp.json()["marked_read"] >= 3

    def test_filter_unread_only(self, client, primary_user, session):
        item = FeedItem(
            user_id=primary_user.id,
            title="Unread",
            content_markdown="md",
            content_html="<p>md</p>",
            is_read=False,
        )
        session.add(item)
        session.commit()

        resp = client.get("/api/v1/feed/?unread_only=true")
        assert resp.status_code == 200
        for f in resp.json():
            assert f["is_read"] is False


# ── /api/v1/journal ───────────────────────────────────────────────────────────

class TestJournalAPI:
    def test_create_journal_entry(self, client):
        resp = client.post("/api/v1/journal/", json={"content": "Today was productive."})
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Today was productive."
        assert data["processed"] is False

    def test_list_journal_entries(self, client, primary_user, session):
        entry = JournalEntry(user_id=primary_user.id, content="Test entry.")
        session.add(entry)
        session.commit()

        resp = client.get("/api/v1/journal/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_journal_entry(self, client, primary_user, session):
        entry = JournalEntry(user_id=primary_user.id, content="Delete me.")
        session.add(entry)
        session.commit()
        session.refresh(entry)

        resp = client.delete(f"/api/v1/journal/{entry.id}")
        assert resp.status_code == 204
