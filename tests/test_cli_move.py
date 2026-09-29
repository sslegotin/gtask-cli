import json


def seed(fake):
    fake.add_list("My Tasks", id="Lalpha0000000000")
    fake.add_list("Work", id="Lbeta00000000000")
    fake.add_task("Lbeta00000000000", "Report", id="Trep00000")
    fake.add_task("Lbeta00000000000", "Outline", id="Tout00000", parent="Trep00000")
    fake.add_task("Lbeta00000000000", "Slides", id="Tsli00000", parent="Trep00000")
    fake.add_task("Lbeta00000000000", "Loose", id="Tloo00000")


def work_children(fake, parent):
    tasks = [t for t in fake.tasks["Lbeta00000000000"].values() if t.get("parent") == parent]
    return [t["title"] for t in sorted(tasks, key=lambda t: t["position"])]


def test_move_parent_nests(run, fake):
    seed(fake)
    result = run("move", "Tloo", "-p", "Trep")
    assert result.exit_code == 0 and "Moved Tloo00000  Loose" in result.output
    assert fake.calls[-1][2] == {"parent": "Trep00000"}
    assert work_children(fake, "Trep00000") == ["Loose", "Outline", "Slides"]


def test_move_top_unnests(run, fake):
    seed(fake)
    result = run("move", "Tsli", "--top", "--json")
    assert "parent" not in json.loads(result.stdout)
    assert fake.calls[-1][2] == {}
    assert work_children(fake, None) == ["Slides", "Report", "Loose"]


def test_move_after_adopts_previous_parent(run, fake):
    seed(fake)
    result = run("move", "Tloo", "--after", "Tout")
    assert result.exit_code == 0, result.output
    assert fake.calls[-1][2] == {"parent": "Trep00000", "previous": "Tout00000"}
    assert work_children(fake, "Trep00000") == ["Outline", "Loose", "Slides"]


def test_move_first_keeps_parent(run, fake):
    seed(fake)
    result = run("move", "Tsli", "--first")
    assert result.exit_code == 0
    assert fake.calls[-1][2] == {"parent": "Trep00000"}
    assert work_children(fake, "Trep00000") == ["Slides", "Outline"]


def test_move_to_other_list_carries_subtasks(run, fake):
    seed(fake)
    result = run("move", "Trep", "--to", "My Tasks")
    assert result.exit_code == 0, result.output
    assert fake.calls[-1][2] == {"destinationTasklist": "Lalpha0000000000"}
    assert set(fake.tasks["Lalpha0000000000"]) == {"Trep00000", "Tout00000", "Tsli00000"}
    assert list(fake.tasks["Lbeta00000000000"]) == ["Tloo00000"]


def test_move_to_with_parent_resolved_in_destination(run, fake):
    seed(fake)
    fake.add_task("Lalpha0000000000", "Home", id="Thome0000")
    result = run("move", "Tloo", "--to", "Lalpha", "-p", "Thome")
    assert result.exit_code == 0, result.output
    assert fake.calls[-1][2] == {"parent": "Thome0000", "destinationTasklist": "Lalpha0000000000"}
    assert fake.tasks["Lalpha0000000000"]["Tloo00000"]["parent"] == "Thome0000"


def test_move_usage_errors(run, fake):
    seed(fake)
    assert run("move", "Tloo", "-p", "Trep", "--top").exit_code == 2
    assert run("move", "Tloo", "--after", "Tout", "--first").exit_code == 2
    result = run("move", "Tloo")
    assert result.exit_code == 2 and "Nothing to do" in result.output
    assert fake.calls == []
