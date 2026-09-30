"""Opt-in smoke test against the real API. Creates and deletes its own task list."""

import os
import uuid

import pytest

from gtask.api import TasksClient
from gtask.auth import make_session
from gtask.config import token_path

pytestmark = pytest.mark.skipif(
    not os.environ.get("GTASK_LIVE") or not token_path().exists(),
    reason="set GTASK_LIVE=1 and run `gtask login` first",
)


@pytest.fixture
def config_dir():
    """Override the autouse conftest fixture so the real token is used."""
    return token_path().parent


def test_live_roundtrip():
    api = TasksClient(make_session())
    tasklist = api.create_tasklist(f"gtask-live-{uuid.uuid4().hex[:8]}")
    try:
        parent = api.create_task(
            tasklist["id"], {"title": "parent", "notes": "n", "due": "2026-10-05T00:00:00.000Z"}
        )
        child = api.create_task(tasklist["id"], {"title": "child"}, parent=parent["id"])
        assert child["parent"] == parent["id"]

        assert (
            api.patch_task(tasklist["id"], parent["id"], {"title": "parent2"})["title"] == "parent2"
        )

        put = api.update_task(
            tasklist["id"],
            parent["id"],
            {"id": parent["id"], "title": "parent3", "status": "needsAction"},
        )
        assert "due" not in put and "notes" not in put, "PUT without a field should clear it"

        done = api.patch_task(tasklist["id"], child["id"], {"status": "completed"})
        assert done.get("completed")
        reopened = api.update_task(
            tasklist["id"],
            child["id"],
            {"id": child["id"], "title": "child", "status": "needsAction"},
        )
        assert "completed" not in reopened

        moved = api.move_task(tasklist["id"], child["id"])  # no parent => top level
        assert "parent" not in moved

        # Documents whether dueMax is inclusive. parent3 no longer has a due date, so re-add one:
        api.patch_task(tasklist["id"], parent["id"], {"due": "2026-10-05T00:00:00.000Z"})
        due_filtered = api.list_tasks(
            tasklist["id"], due_min="2026-10-05T00:00:00.000Z", due_max="2026-10-05T00:00:00.000Z"
        )
        assert [t["id"] for t in due_filtered] == [parent["id"]], (
            "expected dueMax to be inclusive; if this fails see plan Task 16 step 7"
        )

        assert {t["id"] for t in api.list_tasks(tasklist["id"])} == {parent["id"], child["id"]}
        api.delete_task(tasklist["id"], child["id"])
        assert [t["id"] for t in api.list_tasks(tasklist["id"])] == [parent["id"]]
    finally:
        api.delete_tasklist(tasklist["id"])
