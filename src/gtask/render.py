"""Human-readable output. Never touches the network."""

from collections import defaultdict

from .dates import from_api
from .resolve import short_ids


def render_lists(lists: list[dict], default_id: str | None = None) -> str:
    if not lists:
        return "(no task lists)"
    ids = short_ids([tasklist["id"] for tasklist in lists])
    width = max(len(short) for short in ids.values())
    lines = []
    for tasklist in lists:
        mark = "*" if tasklist["id"] == default_id else " "
        lines.append(f"{mark} {ids[tasklist['id']]:<{width}}  {tasklist['title']}")
    return "\n".join(lines)


def order_tree(tasks: list[dict]) -> list[tuple[dict, int]]:
    """Depth-first order with depth, children sorted by position.

    A task whose parent is not in `tasks` (e.g. the parent is completed and was
    filtered out) is treated as a root so it is never silently dropped.
    """
    present = {task["id"] for task in tasks}
    children: dict[str | None, list[dict]] = defaultdict(list)
    for task in tasks:
        parent = task.get("parent")
        children[parent if parent in present else None].append(task)
    for group in children.values():
        group.sort(key=lambda task: task.get("position", ""))
    ordered: list[tuple[dict, int]] = []

    def walk(parent_id: str | None, depth: int) -> None:
        for task in children.get(parent_id, []):
            ordered.append((task, depth))
            walk(task["id"], depth + 1)

    walk(None, 0)
    return ordered


def render_tasks(tasks: list[dict], flat: bool = False) -> str:
    if not tasks:
        return "(no tasks)"
    ids = short_ids([task["id"] for task in tasks])
    width = max(len(short) for short in ids.values())
    rows = [(task, 0) for task in tasks] if flat else order_tree(tasks)
    lines = []
    for task, depth in rows:
        mark = "[x]" if task.get("status") == "completed" else "[ ]"
        due = from_api(task.get("due"))
        note = " +" if task.get("notes") else ""
        indent = "  " * depth
        lines.append(
            f"{ids[task['id']]:<{width}}  {mark}  {due:<10}  {indent}{task.get('title', '')}{note}"
        )
    return "\n".join(lines)


def render_task(task: dict, list_title: str) -> str:
    if task.get("status") == "completed":
        status = f"completed {from_api(task.get('completed'))}".rstrip()
    else:
        status = "open"
    rows = [
        ("title", task.get("title", "")),
        ("list", list_title),
        ("status", status),
        ("due", from_api(task.get("due")) or "-"),
    ]
    if task.get("parent"):
        rows.append(("parent", task["parent"]))
    rows.append(("id", task["id"]))
    if task.get("webViewLink"):
        rows.append(("link", task["webViewLink"]))
    lines = [f"{key + ':':<8} {value}" for key, value in rows]
    if task.get("notes"):
        lines.append("")
        lines.extend(task["notes"].splitlines())
    return "\n".join(lines)
