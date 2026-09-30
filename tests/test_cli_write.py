import json

from gtask import config


def seed(fake):
    fake.add_list("My Tasks", id="Lalpha0000000000")
    fake.add_list("Work", id="Lbeta00000000000")
    fake.add_task("Lbeta00000000000", "Report", id="Trep00000", notes="draft it")
    fake.add_task("Lbeta00000000000", "Outline", id="Tout00000", parent="Trep00000")
    fake.add_task("Lbeta00000000000", "Slides", id="Tsli00000", parent="Trep00000")


def test_add_to_default_list(run, fake):
    seed(fake)
    result = run("add", "Buy milk")
    assert result.exit_code == 0, result.output
    assert result.output.startswith("Added T")
    [task] = fake.tasks["Lalpha0000000000"].values()
    assert task["title"] == "Buy milk" and "notes" not in task and "due" not in task
    assert fake.calls[-1][:2] == ("POST", "/lists/Lalpha0000000000/tasks")
    assert fake.calls[-1][2] == {}


def test_add_with_all_fields_json(run, fake):
    seed(fake)
    config.set_default_list("Lbeta00000000000")
    result = run("add", "Charts", "-n", "bar and line", "-d", "2026-10-05", "-p", "Trep", "--json")
    assert result.exit_code == 0, result.output
    task = json.loads(result.stdout)
    assert task["title"] == "Charts" and task["notes"] == "bar and line"
    assert task["due"] == "2026-10-05T00:00:00.000Z" and task["parent"] == "Trep00000"
    assert fake.calls[-1][2] == {"parent": "Trep00000"}


def test_add_after_adopts_previous_parent(run, fake):
    seed(fake)
    result = run("add", "Review", "-l", "work", "--after", "Tout")
    assert result.exit_code == 0, result.output
    assert fake.calls[-1][2] == {"parent": "Trep00000", "previous": "Tout00000"}
    order = [
        t["title"]
        for t in sorted(
            (t for t in fake.tasks["Lbeta00000000000"].values() if t.get("parent") == "Trep00000"),
            key=lambda t: t["position"],
        )
    ]
    assert order == ["Outline", "Review", "Slides"]


def test_add_parent_must_be_in_target_list(run, fake):
    seed(fake)
    result = run("add", "x", "-p", "Trep")  # default list is My Tasks
    assert result.exit_code == 4 and "in list 'My Tasks'" in result.output


def test_add_bad_due_is_usage_error_without_api_calls(run, fake):
    seed(fake)
    result = run("add", "x", "-d", "2026-13-45")
    assert result.exit_code == 2 and "Invalid date" in result.output
    assert fake.calls == []


def test_update_title_uses_patch(run, fake):
    seed(fake)
    result = run("update", "Trep", "--title", "Final report")
    assert result.exit_code == 0 and "Updated Trep00000  Final report" in result.output
    method, _path, _, body = fake.calls[-1]
    assert (method, body) == ("PATCH", {"title": "Final report"})
    assert fake.tasks["Lbeta00000000000"]["Trep00000"]["notes"] == "draft it"


def test_update_due_and_notes_json(run, fake):
    seed(fake)
    result = run("update", "Tout", "-d", "tomorrow", "-n", "call first", "--json")
    task = json.loads(result.stdout)
    assert task["notes"] == "call first" and task["due"].endswith("T00:00:00.000Z")


def test_update_clear_notes_and_due_uses_put(run, fake):
    seed(fake)
    fake.tasks["Lbeta00000000000"]["Trep00000"]["due"] = "2026-10-05T00:00:00.000Z"
    result = run("update", "Trep", "-n", "", "--no-due", "--title", "R")
    assert result.exit_code == 0, result.output
    method, _, _, body = fake.calls[-1]
    assert method == "PUT"
    assert body == {"id": "Trep00000", "title": "R", "status": "needsAction"}
    stored = fake.tasks["Lbeta00000000000"]["Trep00000"]
    assert "notes" not in stored and "due" not in stored and stored["position"]


def test_update_conflicting_or_empty_is_usage_error(run, fake):
    seed(fake)
    result = run("update", "Trep", "-d", "today", "--no-due")
    assert result.exit_code == 2 and "mutually exclusive" in result.output
    result = run("update", "Trep")
    assert result.exit_code == 2 and "Nothing to update" in result.output
    assert fake.calls == []
