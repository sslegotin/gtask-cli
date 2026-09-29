import pytest

from gtask.api import BASE_URL, TasksClient
from gtask.errors import ApiError, AuthError
from tests.fake_session import BASE, FakeSession


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return TasksClient(session)


def test_base_url_matches_fake():
    assert BASE_URL == BASE


def test_tasklist_methods(client, session):
    created = client.create_tasklist("Work")
    assert client.list_tasklists() == [created]
    assert client.get_tasklist(created["id"]) == created
    assert client.patch_tasklist(created["id"], "W")["title"] == "W"
    assert client.delete_tasklist(created["id"]) is None
    assert client.list_tasklists() == []
    assert session.calls[0][:2] == ("POST", "/users/@me/lists")
    assert session.calls[-2][:2] == ("DELETE", f"/users/@me/lists/{created['id']}")


def test_list_tasks_params_and_pagination(client, session):
    lst = session.add_list("Inbox")
    for i in range(150):
        session.add_task(lst["id"], f"t{i}")
    tasks = client.list_tasks(lst["id"], show_completed=False, show_hidden=True, due_min="a", due_max="b")
    _, path, params, _ = session.calls[-1]
    assert path == f"/lists/{lst['id']}/tasks"
    assert params["showCompleted"] == "false" and params["showHidden"] == "true"
    assert params["dueMin"] == "a" and params["dueMax"] == "b" and params["maxResults"] == 100
    # dueMin/dueMax filtered everything (no dues), so exercise pagination separately:
    assert tasks == []
    tasks = client.list_tasks(lst["id"])
    assert len(tasks) == 150
    assert session.calls[-1][2]["pageToken"] == "100"


def test_list_tasks_default_params(client, session):
    lst = session.add_list("Inbox")
    client.list_tasks(lst["id"])
    params = session.calls[-1][2]
    assert params == {"showCompleted": "true", "showHidden": "false", "maxResults": 100}


def test_task_methods(client, session):
    lst = session.add_list("Inbox")
    parent = client.create_task(lst["id"], {"title": "p"})
    child = client.create_task(lst["id"], {"title": "c", "notes": "n"}, parent=parent["id"])
    assert session.calls[-1][2] == {"parent": parent["id"]}
    assert child["parent"] == parent["id"] and child["notes"] == "n"
    assert client.get_task(lst["id"], child["id"]) == child
    assert client.patch_task(lst["id"], child["id"], {"status": "completed"})["status"] == "completed"
    put = client.update_task(lst["id"], child["id"], {"id": child["id"], "title": "c2", "status": "needsAction"})
    assert put["title"] == "c2" and "notes" not in put
    assert session.calls[-1][0] == "PUT"
    moved = client.move_task(lst["id"], child["id"], parent=None, previous=parent["id"])
    assert "parent" not in moved and session.calls[-1][2] == {"previous": parent["id"]}
    other = session.add_list("Other")
    client.move_task(lst["id"], child["id"], destination_list=other["id"])
    assert session.calls[-1][2] == {"destinationTasklist": other["id"]}
    assert client.delete_task(other["id"], child["id"]) is None
    assert client.clear_tasks(lst["id"]) is None
    assert session.calls[-1][:2] == ("POST", f"/lists/{lst['id']}/clear")


def test_api_error_uses_message_from_body(client, session):
    session.next_error = (403, "Insufficient Permission")
    with pytest.raises(ApiError) as exc:
        client.list_tasklists()
    assert exc.value.status == 403
    assert exc.value.message == "API error 403: Insufficient Permission"


def test_401_is_auth_error(client, session):
    session.next_error = (401, "Invalid Credentials")
    with pytest.raises(AuthError) as exc:
        client.list_tasklists()
    assert "gtask login" in exc.value.message


def test_not_found_is_api_error_404(client, session):
    with pytest.raises(ApiError) as exc:
        client.get_tasklist("nope")
    assert exc.value.status == 404
