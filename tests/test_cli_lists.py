import json

from gtask import config


def seed(fake):
    fake.add_list("My Tasks", id="Lalpha0000000000")
    fake.add_list("Work", id="Lbeta00000000000")


def test_lists_human_marks_default(run, fake):
    seed(fake)
    config.set_default_list("Lbeta00000000000")
    result = run("lists")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == ["  Lalp  My Tasks", "* Lbet  Work"]


def test_lists_json_before_and_after(run, fake):
    seed(fake)
    for args in (["lists", "--json"], ["--json", "lists"]):
        result = run(*args)
        assert result.exit_code == 0
        assert [lst["title"] for lst in json.loads(result.stdout)] == ["My Tasks", "Work"]


def test_lists_create(run, fake):
    result = run("lists", "create", "Groceries")
    assert result.exit_code == 0
    assert result.output.startswith("Created list L001")
    assert [lst["title"] for lst in fake.lists.values()] == ["Groceries"]
    result = run("lists", "--json", "create", "More")
    assert json.loads(result.stdout)["title"] == "More"


def test_lists_rename_by_title(run, fake):
    seed(fake)
    result = run("lists", "rename", "work", "Job")
    assert result.exit_code == 0 and "Renamed list Lbeta00000000000  Job" in result.output
    assert fake.lists["Lbeta00000000000"]["title"] == "Job"


def test_lists_delete_confirms(run, fake):
    seed(fake)
    result = run("lists", "delete", "Work", input="n\n")
    assert result.exit_code == 1 and "Lbeta00000000000" in fake.lists
    result = run("lists", "delete", "Work", input="y\n")
    assert result.exit_code == 0 and "Lbeta00000000000" not in fake.lists
    assert "ALL its tasks" in result.output


def test_lists_delete_yes_and_json_skip_prompt(run, fake):
    seed(fake)
    result = run("lists", "delete", "Work", "--yes")
    assert result.exit_code == 0 and "Deleted list" in result.output
    result = run("lists", "delete", "Lalpha", "--json")
    assert json.loads(result.stdout) == {"deleted": ["Lalpha0000000000"]}
    assert fake.lists == {}


def test_lists_default_writes_config(run, fake):
    seed(fake)
    result = run("lists", "default", "Lbeta")
    assert result.exit_code == 0 and "Default list set to Lbeta00000000000  Work" in result.output
    assert config.get_default_list() == "Lbeta00000000000"
    result = run("lists", "default", "my tasks", "--json")
    assert json.loads(result.stdout) == {"default_list": "Lalpha0000000000"}


def test_not_found_and_ambiguous_exit_4(run, fake):
    seed(fake)
    result = run("lists", "rename", "Nope", "x")
    assert result.exit_code == 4 and "error: No task list matches 'Nope'" in result.output
    result = run("lists", "rename", "L", "x")
    assert result.exit_code == 4 and "matches several lists" in result.output


def test_api_errors_map_to_exit_codes(run, fake):
    fake.next_error = (401, "Invalid Credentials")
    result = run("lists")
    assert result.exit_code == 3 and "gtask login" in result.output
    fake.next_error = (500, "Backend Error")
    result = run("lists")
    assert result.exit_code == 1 and "error: API error 500: Backend Error" in result.output


def test_not_logged_in_exits_3(run):
    # No `fake` fixture: the real session factory runs and finds no token file.
    result = run("lists")
    assert result.exit_code == 3
    assert "error: Not logged in. Run: gtask login" in result.output
