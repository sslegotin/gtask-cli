import pytest

from gtask.api import TasksClient
from gtask.errors import AmbiguousError, NotFoundError
from gtask.resolve import find_task, resolve_list, resolve_task, short_ids
from tests.fake_session import FakeSession


def test_short_ids_minimum_and_uniqueness():
    assert short_ids(["abcdefgh", "abcxyz12", "zzzzzzzz"]) == {
        "abcdefgh": "abcd",
        "abcxyz12": "abcx",
        "zzzzzzzz": "zzzz",
    }
    assert short_ids(["MTIzNDU2", "MTIzNDU3"]) == {"MTIzNDU2": "MTIzNDU2", "MTIzNDU3": "MTIzNDU3"}
    assert short_ids(["abc", "abcdef"]) == {"abc": "abc", "abcdef": "abcd"}
    assert short_ids([]) == {}


@pytest.fixture
def session():
    s = FakeSession()
    s.add_list("My Tasks", id="Lalpha0000000000")
    s.add_list("Work", id="Lbeta00000000000")
    s.add_list("Groceries", id="Lbetaxxxxxxxxxxx")
    return s


@pytest.fixture
def client(session):
    return TasksClient(session)


def test_resolve_list_none_uses_default_or_first(client):
    assert resolve_list(client, None)["title"] == "My Tasks"
    assert resolve_list(client, None, default_id="Lbeta00000000000")["title"] == "Work"


def test_resolve_list_missing_default_is_not_found(client):
    with pytest.raises(NotFoundError) as exc:
        resolve_list(client, None, default_id="gone")
    assert "gtask lists default" in exc.value.message


def test_resolve_list_no_lists_at_all():
    client = TasksClient(FakeSession())
    with pytest.raises(NotFoundError):
        resolve_list(client, None)


def test_resolve_list_by_id_prefix_and_title(client):
    assert resolve_list(client, "Lbeta00000000000")["title"] == "Work"
    assert resolve_list(client, "Lalpha")["title"] == "My Tasks"
    assert resolve_list(client, "work")["title"] == "Work"
    assert resolve_list(client, "GROCERIES")["title"] == "Groceries"


def test_resolve_list_exact_id_beats_prefix(client, session):
    session.add_list("Sub", id="Lalpha")
    assert resolve_list(client, "Lalpha")["title"] == "Sub"


def test_resolve_list_ambiguous_and_missing(client):
    with pytest.raises(AmbiguousError) as exc:
        resolve_list(client, "Lbeta")
    assert "Work" in exc.value.message and "Groceries" in exc.value.message
    with pytest.raises(NotFoundError):
        resolve_list(client, "Nope")
    with pytest.raises(NotFoundError):
        resolve_list(client, "")


def test_find_task_in_known_list(client, session):
    work = session.lists["Lbeta00000000000"]
    session.add_task(work["id"], "report", id="Tabc111")
    session.add_task(work["id"], "old", id="Tabc222", status="completed", hidden=True)
    assert find_task(client, work, "Tabc1")["title"] == "report"
    assert find_task(client, work, "Tabc222")["title"] == "old"  # hidden tasks are searchable
    with pytest.raises(AmbiguousError):
        find_task(client, work, "Tabc")
    with pytest.raises(NotFoundError) as exc:
        find_task(client, work, "zzz")
    assert "Work" in exc.value.message


def test_resolve_task_searches_all_lists_without_list_ref(client, session):
    session.add_task("Lalpha0000000000", "home thing", id="Thome")
    session.add_task("Lbeta00000000000", "work thing", id="Twork")
    tasklist, task = resolve_task(client, "Twor")
    assert tasklist["title"] == "Work" and task["title"] == "work thing"


def test_resolve_task_ambiguous_across_lists_names_both(client, session):
    session.add_task("Lalpha0000000000", "a", id="Tsame1")
    session.add_task("Lbeta00000000000", "b", id="Tsame2")
    with pytest.raises(AmbiguousError) as exc:
        resolve_task(client, "Tsame")
    assert "My Tasks" in exc.value.message and "Work" in exc.value.message


def test_resolve_task_exact_id_wins_across_lists(client, session):
    session.add_task("Lalpha0000000000", "short", id="Tsame")
    session.add_task("Lbeta00000000000", "long", id="Tsame2")
    assert resolve_task(client, "Tsame")[1]["title"] == "short"


def test_resolve_task_with_list_ref_limits_search(client, session):
    session.add_task("Lalpha0000000000", "a", id="Tsame1")
    session.add_task("Lbeta00000000000", "b", id="Tsame2")
    tasklist, task = resolve_task(client, "Tsame", list_ref="work")
    assert task["title"] == "b"
    with pytest.raises(NotFoundError):
        resolve_task(client, "Tsame1", list_ref="work")
