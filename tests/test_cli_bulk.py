import json


def seed(fake):
    fake.add_list("My Tasks", id="Lalpha0000000000")
    fake.add_list("Work", id="Lbeta00000000000")
    fake.add_task("Lalpha0000000000", "Milk", id="Tmilk0000")
    fake.add_task("Lbeta00000000000", "Report", id="Trep00000")
    fake.add_task("Lbeta00000000000", "Outline", id="Tout00000", parent="Trep00000")
    fake.add_task("Lbeta00000000000", "Old", id="Told00000", status="completed")


def test_done_multiple_across_lists(run, fake):
    seed(fake)
    result = run("done", "Tmilk", "Tout")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == ["Completed Tmilk0000  Milk", "Completed Tout00000  Outline"]
    assert fake.tasks["Lalpha0000000000"]["Tmilk0000"]["status"] == "completed"
    assert fake.tasks["Lbeta00000000000"]["Tout00000"]["completed"]
    assert fake.calls[-1][:2] == ("PATCH", "/lists/Lbeta00000000000/tasks/Tout00000")
    assert fake.calls[-1][3] == {"status": "completed"}


def test_done_json_returns_updated_objects(run, fake):
    seed(fake)
    data = json.loads(run("done", "Tmilk", "--json").stdout)
    assert [t["status"] for t in data] == ["completed"]


def test_undone_clears_completed_via_put(run, fake):
    seed(fake)
    result = run("undone", "Told")
    assert result.exit_code == 0 and "Reopened Told00000  Old" in result.output
    method, _, _, body = fake.calls[-1]
    assert method == "PUT" and body == {"id": "Told00000", "title": "Old", "status": "needsAction"}
    stored = fake.tasks["Lbeta00000000000"]["Told00000"]
    assert stored["status"] == "needsAction" and "completed" not in stored


def test_delete_confirms_and_lists_titles(run, fake):
    seed(fake)
    result = run("delete", "Tmilk", "Told", input="n\n")
    assert result.exit_code == 1
    assert "Milk" in result.output and "Old" in result.output
    assert "Tmilk0000" in fake.tasks["Lalpha0000000000"]
    result = run("delete", "Tmilk", "Told", input="y\n")
    assert result.exit_code == 0
    assert "Tmilk0000" not in fake.tasks["Lalpha0000000000"]
    assert "Told00000" not in fake.tasks["Lbeta00000000000"]


def test_delete_yes_and_json_skip_prompt(run, fake):
    seed(fake)
    result = run("delete", "Tmilk", "--yes")
    assert result.exit_code == 0 and result.output.strip() == "Deleted Tmilk0000  Milk"
    result = run("delete", "Told", "--json")
    assert json.loads(result.stdout) == {"deleted": ["Told00000"]}


def test_delete_resolves_all_before_writing(run, fake):
    seed(fake)
    result = run("delete", "Tmilk", "T", "--yes")  # "T" is ambiguous
    assert result.exit_code == 4 and "matches several tasks" in result.output
    assert "Tmilk0000" in fake.tasks["Lalpha0000000000"]
    assert not any(call[0] == "DELETE" for call in fake.calls)


def test_delete_with_list_scopes_lookup(run, fake):
    seed(fake)
    result = run("delete", "Tmilk", "-l", "work", "--yes")
    assert result.exit_code == 4 and "in list 'Work'" in result.output


def test_clear_default_and_named_list(run, fake):
    seed(fake)
    result = run("clear", "-l", "work")
    assert result.exit_code == 0 and "Cleared completed tasks from Work" in result.output
    assert fake.tasks["Lbeta00000000000"]["Told00000"]["hidden"] is True
    assert "hidden" not in fake.tasks["Lbeta00000000000"]["Trep00000"]
    assert json.loads(run("clear", "--json").stdout) == {"cleared": "Lalpha0000000000"}
