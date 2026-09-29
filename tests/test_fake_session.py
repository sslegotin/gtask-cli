from tests.fake_session import BASE, FakeSession


def get(session, path, **params):
    return session.request("GET", BASE + path, params=params)


def test_lists_crud():
    s = FakeSession()
    created = s.request("POST", BASE + "/users/@me/lists", json={"title": "Work"}).json()
    assert created["title"] == "Work" and created["id"].startswith("L001")
    assert get(s, "/users/@me/lists").json()["items"] == [created]
    renamed = s.request("PATCH", BASE + f"/users/@me/lists/{created['id']}", json={"title": "W"}).json()
    assert renamed["title"] == "W"
    assert s.request("DELETE", BASE + f"/users/@me/lists/{created['id']}").status_code == 204
    assert "items" not in get(s, "/users/@me/lists").json()
    assert s.request("GET", BASE + f"/users/@me/lists/{created['id']}").status_code == 404


def test_task_insert_order_and_previous():
    s = FakeSession()
    lst = s.add_list("Inbox")
    a = s.request("POST", BASE + f"/lists/{lst['id']}/tasks", json={"title": "a"}).json()
    b = s.request("POST", BASE + f"/lists/{lst['id']}/tasks", json={"title": "b"}).json()
    c = s.request(
        "POST", BASE + f"/lists/{lst['id']}/tasks", params={"previous": b["id"]}, json={"title": "c"}
    ).json()
    titles = [t["title"] for t in get(s, f"/lists/{lst['id']}/tasks").json()["items"]]
    assert titles == ["b", "c", "a"]  # newest first unless previous given
    pos = {t["title"]: t["position"] for t in s.tasks[lst["id"]].values()}
    assert pos["b"] < pos["c"] < pos["a"]


def test_task_filters():
    s = FakeSession()
    lst = s.add_list("Inbox")
    s.add_task(lst["id"], "open", due="2026-10-01T00:00:00.000Z")
    s.add_task(lst["id"], "done", status="completed")
    s.add_task(lst["id"], "hidden", status="completed", hidden=True)
    s.add_task(lst["id"], "later", due="2026-10-20T00:00:00.000Z")
    path = f"/lists/{lst['id']}/tasks"

    def names(response):
        return sorted(t["title"] for t in response.json().get("items", []))

    assert names(get(s, path)) == ["done", "later", "open"]
    assert names(get(s, path, showCompleted="false")) == ["later", "open"]
    assert names(get(s, path, showHidden="true")) == ["done", "hidden", "later", "open"]
    assert names(get(s, path, dueMin="2026-10-02T00:00:00.000Z")) == ["later"]
    assert names(get(s, path, dueMax="2026-10-01T00:00:00.000Z")) == ["open"]


def test_pagination():
    s = FakeSession()
    lst = s.add_list("Inbox")
    for i in range(5):
        s.add_task(lst["id"], f"t{i}")
    s.page_size = 2
    first = get(s, f"/lists/{lst['id']}/tasks", maxResults=100).json()
    assert len(first["items"]) == 2 and first["nextPageToken"]
    second = get(s, f"/lists/{lst['id']}/tasks", maxResults=100, pageToken=first["nextPageToken"]).json()
    assert len(second["items"]) == 2
    third = get(s, f"/lists/{lst['id']}/tasks", maxResults=100, pageToken=second["nextPageToken"]).json()
    assert len(third["items"]) == 1 and "nextPageToken" not in third


def test_patch_put_and_completed_handling():
    s = FakeSession()
    lst = s.add_list("Inbox")
    t = s.add_task(lst["id"], "x", notes="n", due="2026-10-01T00:00:00.000Z")
    original_position = t["position"]
    url = BASE + f"/lists/{lst['id']}/tasks/{t['id']}"
    done = s.request("PATCH", url, json={"status": "completed"}).json()
    assert done["completed"] and done["notes"] == "n"
    reopened = s.request("PATCH", url, json={"status": "needsAction"}).json()
    assert "completed" in reopened  # fake does not clear it; CLI must
    put = s.request("PUT", url, json={"id": t["id"], "title": "y", "status": "needsAction"}).json()
    assert put["title"] == "y" and "notes" not in put and "due" not in put and "completed" not in put
    assert put["position"] == original_position


def test_delete_removes_subtasks():
    s = FakeSession()
    lst = s.add_list("Inbox")
    parent = s.add_task(lst["id"], "p")
    s.add_task(lst["id"], "child", parent=parent["id"])
    assert s.request("DELETE", BASE + f"/lists/{lst['id']}/tasks/{parent['id']}").status_code == 204
    assert s.tasks[lst["id"]] == {}


def test_move_within_and_between_lists():
    s = FakeSession()
    a = s.add_list("A")
    b = s.add_list("B")
    p = s.add_task(a["id"], "p")
    c = s.add_task(a["id"], "c")
    moved = s.request(
        "POST", BASE + f"/lists/{a['id']}/tasks/{c['id']}/move", params={"parent": p["id"]}
    ).json()
    assert moved["parent"] == p["id"]
    moved = s.request(
        "POST",
        BASE + f"/lists/{a['id']}/tasks/{p['id']}/move",
        params={"destinationTasklist": b["id"]},
    ).json()
    assert "parent" not in moved
    assert set(s.tasks[b["id"]]) == {p["id"], c["id"]} and s.tasks[a["id"]] == {}


def test_clear_hides_completed():
    s = FakeSession()
    lst = s.add_list("Inbox")
    s.add_task(lst["id"], "done", status="completed")
    s.add_task(lst["id"], "open")
    assert s.request("POST", BASE + f"/lists/{lst['id']}/clear").status_code == 204
    hidden = [t["title"] for t in s.tasks[lst["id"]].values() if t.get("hidden")]
    assert hidden == ["done"]


def test_next_error_and_unknown_routes():
    s = FakeSession()
    s.next_error = (500, "kaboom")
    r = get(s, "/users/@me/lists")
    assert r.status_code == 500 and r.json()["error"]["message"] == "kaboom"
    assert get(s, "/users/@me/lists").status_code == 200  # one-shot
    assert get(s, "/nope").status_code == 404
    assert s.calls[-1] == ("GET", "/nope", {}, None)
