"""Tests for the SQLModel database models."""
import json

import pytest

from app.models import (
    FeedItem,
    FeedItemType,
    JournalEntry,
    Routine,
    Skill,
    Task,
    TaskStatus,
    TriggerType,
    User,
)


class TestUserModel:
    def test_create_user(self, session):
        user = User(name="Alice", is_primary=True)
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.id is not None
        assert user.name == "Alice"
        assert user.is_primary is True

    def test_get_preferences_default(self, session):
        user = User(name="Bob")
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.get_preferences() == {}

    def test_get_preferences_json(self, session):
        prefs = {"timezone": "UTC", "language": "en"}
        user = User(name="Carol", preferences=json.dumps(prefs))
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.get_preferences() == prefs


class TestRoutineModel:
    def test_create_routine(self, session, primary_user):
        routine = Routine(
            user_id=primary_user.id,
            name="Morning Briefing",
            trigger_type=TriggerType.cron,
            trigger_value="0 6 * * *",
            system_prompt="Generate a morning briefing.",
            allowed_skill_names='["get_system_time"]',
        )
        session.add(routine)
        session.commit()
        session.refresh(routine)

        assert routine.id is not None
        assert routine.active is True
        assert routine.get_allowed_skills() == ["get_system_time"]

    def test_get_allowed_skills_empty(self, session, primary_user):
        routine = Routine(user_id=primary_user.id, name="All Skills Routine")
        session.add(routine)
        session.commit()
        session.refresh(routine)

        assert routine.get_allowed_skills() == []

    def test_get_allowed_skills_invalid_json(self, session, primary_user):
        routine = Routine(
            user_id=primary_user.id,
            name="Bad Routine",
            allowed_skill_names="not-json",
        )
        session.add(routine)
        session.commit()
        session.refresh(routine)

        # Should return [] gracefully
        assert routine.get_allowed_skills() == []


class TestTaskModel:
    def test_task_default_status(self, session, primary_user):
        task = Task(user_id=primary_user.id, prompt="Test task")
        session.add(task)
        session.commit()
        session.refresh(task)

        assert task.status == TaskStatus.queued
        assert task.error_message is None
        assert task.started_at is None

    def test_task_status_transitions(self, session, primary_user):
        from datetime import datetime, timezone

        task = Task(user_id=primary_user.id, prompt="Transition task")
        session.add(task)
        session.commit()

        task.status = TaskStatus.running
        task.started_at = datetime.now(timezone.utc)
        session.add(task)
        session.commit()
        session.refresh(task)

        assert task.status == TaskStatus.running
        assert task.started_at is not None


class TestFeedItemModel:
    def test_create_feed_item(self, session, primary_user):
        item = FeedItem(
            user_id=primary_user.id,
            type=FeedItemType.report,
            title="Test Report",
            content_markdown="# Test\nHello world.",
            content_html="<h1>Test</h1><p>Hello world.</p>",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        assert item.id is not None
        assert item.is_read is False
        assert item.type == FeedItemType.report


class TestJournalEntryModel:
    def test_create_journal_entry(self, session, primary_user):
        entry = JournalEntry(
            user_id=primary_user.id,
            content="Today I thought about the project.",
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        assert entry.id is not None
        assert entry.processed is False


class TestSkillModel:
    def test_create_skill(self, session):
        skill = Skill(
            module_name="CalculatorSkill",
            name="calculate",
            description="Evaluates maths expressions.",
            tool_schema='{"type": "function"}',
        )
        session.add(skill)
        session.commit()
        session.refresh(skill)

        assert skill.id is not None
        assert skill.get_schema() == {"type": "function"}
        assert skill.tool_schema == '{"type": "function"}'
