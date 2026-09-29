import json

from gtask import config


def seed(fake):
    fake.add_list("My Tasks", id="Lalpha0000000000")
    fake.add_list("Work", id="Lbeta00000000000")
    fake.add_task("Lalpha0000000000", "Buy milk", id="Tmilk0000", due="2026-10-01T00:00:00.000Z")
    fake.add_task("Lalpha0000000000", "Old", id="Told00000", status="completed")
    fake.add_task("Lalpha0000000000", "Cleared", id="Tgone0000", status="completed", hidden=True)
    fake.add_task("Lbeta00000000000", "Report", id="Trep00000", notes="draft it")
    fake.add_task("Lbeta00000000000", "Outline", id="Tout00000", parent="Trep00000")


def test_ls_default_list_open_only(run, fake):
    seed(fake)
    result = run("ls")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == ["Tmil  [ ]  2026-10-01  Buy milk"]
    params = fake.calls[-1][2]
    assert params["showCompleted"] == "false" and params["showHidden"] == "false"


def test_ls_all_includes_completed_and_hidden(run, fake):
    seed(fake)
    result = run("ls", "--all")
    titles = [line.split("  ")[-1] for line in result.output.splitlines()]
    assert sorted(titles) == ["Buy milk", "Cleared", "Old"]


def test_ls_other_list_tree_and_json(run, fake):
    seed(fake)
    result = run("ls", "-l", "work")
    assert result.output.splitlines() == [
        "Trep  [ ]              Report +",
        "Tout  [ ]                Outline",
    ]
    result = run("ls", "-l", "Lbeta", "--json")
    data = json.loads(result.stdout)
    assert [t["id"] for t in data] == ["Trep00000", "Tout00000"]
    assert data[1]["parent"] == "Trep00000"


def test_ls_flat(run, fake):
    seed(fake)
    result = run("ls", "-l", "work", "--flat")
    assert result.output.splitlines() == [
        "Trep  [ ]              Report +",
        "Tout  [ ]              Outline",
    ]


def test_ls_uses_configured_default(run, fake):
    seed(fake)
    config.set_default_list("Lbeta00000000000")
    result = run("ls")
    assert "Report" in result.output and "Buy milk" not in result.output


def test_ls_due_filters_sent_as_api_dates(run, fake):
    seed(fake)
    result = run("ls", "--due-after", "2026-09-30", "--due-before", "2026-10-01")
    assert result.exit_code == 0
    params = fake.calls[-1][2]
    assert params["dueMin"] == "2026-09-30T00:00:00.000Z"
    assert params["dueMax"] == "2026-10-01T00:00:00.000Z"
    assert "Buy milk" in result.output


def test_ls_bad_date_is_usage_error_without_api_calls(run, fake):
    seed(fake)
    result = run("ls", "--due-before", "someday")
    assert result.exit_code == 2
    assert "error: Invalid date 'someday'" in result.output
    assert fake.calls == []


def test_ls_empty(run, fake):
    fake.add_list("Empty")
    assert run("ls").output.strip() == "(no tasks)"
    assert json.loads(run("ls", "--json").stdout) == []


def test_show_by_prefix_across_lists(run, fake):
    seed(fake)
    result = run("show", "Tout")
    assert result.exit_code == 0
    assert result.output.splitlines()[:3] == ["title:   Outline", "list:    Work", "status:  open"]
    assert "parent:  Trep00000" in result.output
    result = run("show", "Trep", "--json")
    assert json.loads(result.stdout)["notes"] == "draft it"


def test_show_hidden_task_is_reachable(run, fake):
    seed(fake)
    result = run("show", "Tgone")
    assert result.exit_code == 0 and "status:  completed" in result.output


def test_show_not_found_and_ambiguous(run, fake):
    seed(fake)
    result = run("show", "Tzzz")
    assert result.exit_code == 4 and "error: No task matches 'Tzzz' in any list" in result.output
    result = run("show", "T")
    assert result.exit_code == 4 and "matches several tasks" in result.output
    assert "[Work] Report" in result.output


def test_show_with_list_limits_search(run, fake):
    seed(fake)
    result = run("show", "Tout", "-l", "My Tasks")
    assert result.exit_code == 4 and "in list 'My Tasks'" in result.output
