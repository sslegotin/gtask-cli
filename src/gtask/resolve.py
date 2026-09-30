"""Turn user-typed references (ids, id prefixes, list titles) into API objects."""

from collections.abc import Iterable

from .api import TasksClient
from .errors import AmbiguousError, NotFoundError


def short_ids(ids: Iterable[str], minimum: int = 4) -> dict[str, str]:
    """Shortest prefix of each id that is unique within `ids`, at least `minimum` long."""
    all_ids = list(ids)
    result = {}
    for candidate in all_ids:
        length = minimum
        while length < len(candidate) and any(
            other != candidate and other.startswith(candidate[:length]) for other in all_ids
        ):
            length += 1
        result[candidate] = candidate[:length]
    return result


def _by_id(candidates: list[dict], ref: str) -> list[dict]:
    if not ref:
        return []
    exact = [c for c in candidates if c["id"] == ref]
    if exact:
        return exact
    return [c for c in candidates if c["id"].startswith(ref)]


def resolve_list(client: TasksClient, ref: str | None, default_id: str | None = None) -> dict:
    lists = client.list_tasklists()
    if ref is None:
        if default_id:
            for tasklist in lists:
                if tasklist["id"] == default_id:
                    return tasklist
            raise NotFoundError(
                f"Default list {default_id} no longer exists. Run: gtask lists default LIST"
            )
        if not lists:
            raise NotFoundError("No task lists found in this account")
        return lists[0]
    matches = _by_id(lists, ref) or [t for t in lists if t["title"].lower() == ref.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundError(f"No task list matches {ref!r}")
    listing = "\n".join(f"  {t['id']}  {t['title']}" for t in matches)
    raise AmbiguousError(f"{ref!r} matches several lists:\n{listing}")


def find_task(client: TasksClient, tasklist: dict, ref: str) -> dict:
    tasks = client.list_tasks(tasklist["id"], show_completed=True, show_hidden=True)
    matches = _by_id(tasks, ref)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundError(f"No task matches {ref!r} in list {tasklist['title']!r}")
    listing = "\n".join(f"  {t['id']}  {t['title']}" for t in matches)
    raise AmbiguousError(f"{ref!r} matches several tasks in {tasklist['title']!r}:\n{listing}")


def resolve_task(
    client: TasksClient,
    ref: str,
    list_ref: str | None = None,
    default_id: str | None = None,
) -> tuple[dict, dict]:
    if list_ref is not None:
        tasklist = resolve_list(client, list_ref, default_id)
        return tasklist, find_task(client, tasklist, ref)
    matches: list[tuple[dict, dict]] = []
    for tasklist in client.list_tasklists():
        tasks = client.list_tasks(tasklist["id"], show_completed=True, show_hidden=True)
        matches.extend((tasklist, task) for task in _by_id(tasks, ref))
    exact = [(lst, task) for lst, task in matches if task["id"] == ref]
    if exact:
        matches = exact
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundError(f"No task matches {ref!r} in any list")
    listing = "\n".join(
        f"  {task['id']}  [{lst['title']}] {task['title']}" for lst, task in matches
    )
    raise AmbiguousError(f"{ref!r} matches several tasks:\n{listing}")
