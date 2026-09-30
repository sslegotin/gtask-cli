from gtask.render import order_tree, render_lists, render_task, render_tasks


def test_render_lists_marks_default_and_shortens_ids():
    lists = [{"id": "Lalpha00000", "title": "My Tasks"}, {"id": "Lbeta000000", "title": "Work"}]
    out = render_lists(lists, default_id="Lbeta000000")
    assert out.splitlines() == ["  Lalp  My Tasks", "* Lbet  Work"]


def test_render_lists_empty():
    assert render_lists([]) == "(no task lists)"


def make(id, title, **fields):
    return {"id": id, "title": title, "status": "needsAction", "position": "0", **fields}


def test_order_tree_nests_children_by_position():
    tasks = [
        make("c2", "second child", parent="p1", position="1"),
        make("p2", "second parent", position="1"),
        make("c1", "first child", parent="p1", position="0"),
        make("p1", "first parent", position="0"),
    ]
    assert [(t["id"], d) for t, d in order_tree(tasks)] == [
        ("p1", 0),
        ("c1", 1),
        ("c2", 1),
        ("p2", 0),
    ]


def test_render_tasks_orphan_child_at_top_level():
    tasks = [make("c1", "orphan", parent="gone", position="0")]
    assert render_tasks(tasks) == "c1  [ ]              orphan"


def test_render_tasks_columns_marks_and_indent():
    tasks = [
        make("Tparent00", "Parent", due="2026-10-05T00:00:00.000Z", notes="details"),
        make("Tchild000", "Child", parent="Tparent00", status="completed"),
    ]
    assert render_tasks(tasks).splitlines() == [
        "Tpar  [ ]  2026-10-05  Parent +",
        "Tchi  [x]                Child",
    ]


def test_render_tasks_flat_keeps_api_order_without_indent():
    tasks = [
        make("Tchild000", "Child", parent="Tparent00"),
        make("Tparent00", "Parent"),
    ]
    assert render_tasks(tasks, flat=True).splitlines() == [
        "Tchi  [ ]              Child",
        "Tpar  [ ]              Parent",
    ]


def test_render_tasks_empty():
    assert render_tasks([]) == "(no tasks)"


def test_render_task_details():
    task = make(
        "Tabc",
        "Write report",
        due="2026-10-05T00:00:00.000Z",
        notes="line one\nline two",
        parent="Tpar",
        webViewLink="https://tasks.google.com/x",
    )
    out = render_task(task, "Work")
    assert out.splitlines() == [
        "title:   Write report",
        "list:    Work",
        "status:  open",
        "due:     2026-10-05",
        "parent:  Tpar",
        "id:      Tabc",
        "link:    https://tasks.google.com/x",
        "",
        "line one",
        "line two",
    ]


def test_render_task_completed_minimal():
    task = make("Tabc", "Done thing", status="completed", completed="2026-09-20T10:00:00.000Z")
    out = render_task(task, "Work")
    assert out.splitlines() == [
        "title:   Done thing",
        "list:    Work",
        "status:  completed 2026-09-20",
        "due:     -",
        "id:      Tabc",
    ]
