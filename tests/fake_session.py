"""In-memory stand-in for the Google Tasks REST API.

Implements the session contract TasksClient needs: request(method, url, params, json).
Only the behaviour the CLI depends on is modelled; see the docstrings for where it
deliberately mirrors real API quirks.
"""

import json as jsonlib
import re

BASE = "https://tasks.googleapis.com/tasks/v1"
_UPDATED = "2026-01-01T00:00:00.000Z"


class FakeResponse:
    def __init__(self, status_code: int, body=None) -> None:
        self.status_code = status_code
        self.text = "" if body is None else jsonlib.dumps(body)
        self.content = self.text.encode()

    def json(self):
        return jsonlib.loads(self.text)


def _error(status: int, message: str) -> FakeResponse:
    return FakeResponse(status, {"error": {"code": status, "message": message}})


class FakeSession:
    def __init__(self) -> None:
        self.lists: dict[str, dict] = {}
        self.tasks: dict[str, dict[str, dict]] = {}
        self.calls: list[tuple] = []
        self.next_error: tuple[int, str] | None = None
        self.page_size: int | None = None
        self._counter = 0

    # ---- seeding helpers -------------------------------------------------

    def add_list(self, title: str, id: str | None = None) -> dict:
        list_id = id or self._new_id("L")
        self.lists[list_id] = {"kind": "tasks#taskList", "id": list_id, "title": title, "updated": _UPDATED}
        self.tasks[list_id] = {}
        return self.lists[list_id]

    def add_task(self, list_id: str, title: str, id: str | None = None, **fields) -> dict:
        task_id = id or self._new_id("T")
        task = {"kind": "tasks#task", "id": task_id, "title": title, "status": "needsAction", "updated": _UPDATED}
        task.update(fields)
        if task["status"] == "completed":
            task.setdefault("completed", _UPDATED)
        task["position"] = "~"  # sorts after digits: seeded tasks append in call order
        self.tasks[list_id][task_id] = task
        self._renumber(list_id)
        return task

    def _new_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}{self._counter:03d}" + "x" * 16

    # ---- ordering ---------------------------------------------------------

    def _renumber(self, list_id: str) -> None:
        """Assign zero-padded positions per sibling group, keeping relative order.

        A task with position "" sorts first, which is how "insert at top" is expressed.
        """
        by_parent: dict[str | None, list[dict]] = {}
        for task in sorted(self.tasks[list_id].values(), key=lambda t: t.get("position", "")):
            by_parent.setdefault(task.get("parent"), []).append(task)
        for siblings in by_parent.values():
            for index, task in enumerate(siblings):
                task["position"] = f"{index:020d}"

    def _place(self, list_id: str, task: dict, parent: str | None, previous: str | None) -> None:
        if parent:
            task["parent"] = parent
        else:
            task.pop("parent", None)
        if previous:
            # One char longer than previous: sorts right after it, before the next sibling.
            task["position"] = self.tasks[list_id][previous]["position"] + "1"
        else:
            task["position"] = ""
        self._renumber(list_id)

    def _page(self, items: list[dict], params: dict) -> FakeResponse:
        size = int(params.get("maxResults", 20))
        if self.page_size:
            size = min(size, self.page_size)
        start = int(params.get("pageToken", 0))
        chunk = items[start : start + size]
        body: dict = {"kind": "tasks#tasks"}
        if chunk:
            body["items"] = chunk
        if start + size < len(items):
            body["nextPageToken"] = str(start + size)
        return FakeResponse(200, body)

    # ---- dispatch ---------------------------------------------------------

    def request(self, method: str, url: str, params=None, json=None) -> FakeResponse:
        params = dict(params or {})
        path = url[len(BASE):]
        self.calls.append((method, path, params, json))
        if self.next_error:
            status, message = self.next_error
            self.next_error = None
            return _error(status, message)
        for pattern, handler in _ROUTES:
            if m := re.fullmatch(pattern, path):
                return handler(self, method, m.groupdict(), params, json)
        return _error(404, f"no route for {path}")

    def _tasklists(self, method, g, params, body):
        if method == "GET":
            return self._page(list(self.lists.values()), params)
        if method == "POST":
            return FakeResponse(200, self.add_list(body["title"]))
        return _error(405, "method not allowed")

    def _tasklist(self, method, g, params, body):
        lst = self.lists.get(g["l"])
        if not lst:
            return _error(404, "Not Found")
        if method == "GET":
            return FakeResponse(200, lst)
        if method in ("PATCH", "PUT"):
            lst["title"] = body["title"]
            return FakeResponse(200, lst)
        if method == "DELETE":
            del self.lists[g["l"]]
            del self.tasks[g["l"]]
            return FakeResponse(204)
        return _error(405, "method not allowed")

    def _tasks(self, method, g, params, body):
        tasks = self.tasks.get(g["l"])
        if tasks is None:
            return _error(404, "Not Found")
        if method == "GET":
            items = sorted(tasks.values(), key=lambda t: (t.get("parent") or "", t["position"]))
            if params.get("showCompleted", "true") == "false":
                items = [t for t in items if t["status"] != "completed"]
            if params.get("showHidden", "false") == "false":
                items = [t for t in items if not t.get("hidden")]
            if "dueMin" in params:
                items = [t for t in items if t.get("due") and t["due"] >= params["dueMin"]]
            if "dueMax" in params:
                items = [t for t in items if t.get("due") and t["due"] <= params["dueMax"]]
            return self._page(items, params)
        if method == "POST":
            parent, previous = params.get("parent"), params.get("previous")
            if (parent and parent not in tasks) or (previous and previous not in tasks):
                return _error(400, "Invalid task id")
            fields = {k: v for k, v in body.items() if k != "title"}
            task = self.add_task(g["l"], body.get("title", ""), **fields)
            self._place(g["l"], task, parent, previous)
            return FakeResponse(200, task)
        return _error(405, "method not allowed")

    def _task(self, method, g, params, body):
        tasks = self.tasks.get(g["l"])
        if tasks is None or g["t"] not in tasks:
            return _error(404, "Not Found")
        task = tasks[g["t"]]
        if method == "GET":
            return FakeResponse(200, task)
        if method == "PATCH":
            task.update(body)
        elif method == "PUT":
            readonly = ("kind", "id", "parent", "position", "updated")
            keep = {k: task[k] for k in readonly if k in task}
            task.clear()
            task.update(keep)
            task.update(body)
        elif method == "DELETE":
            for child_id in [c["id"] for c in tasks.values() if c.get("parent") == g["t"]]:
                del tasks[child_id]
            del tasks[g["t"]]
            self._renumber(g["l"])
            return FakeResponse(204)
        else:
            return _error(405, "method not allowed")
        if task.get("status") == "completed":
            task.setdefault("completed", _UPDATED)
        return FakeResponse(200, task)

    def _move(self, method, g, params, body):
        source = self.tasks.get(g["l"])
        if method != "POST" or source is None or g["t"] not in source:
            return _error(404, "Not Found")
        dest_id = params.get("destinationTasklist", g["l"])
        if dest_id not in self.lists:
            return _error(404, "Not Found")
        task = source[g["t"]]
        if dest_id != g["l"]:
            dest = self.tasks[dest_id]
            for child_id in [c["id"] for c in source.values() if c.get("parent") == g["t"]]:
                dest[child_id] = source.pop(child_id)
            dest[g["t"]] = source.pop(g["t"])
            self._renumber(g["l"])
        parent, previous = params.get("parent"), params.get("previous")
        if (parent and parent not in self.tasks[dest_id]) or (previous and previous not in self.tasks[dest_id]):
            return _error(400, "Invalid task id")
        self._place(dest_id, task, parent, previous)
        return FakeResponse(200, task)

    def _clear(self, method, g, params, body):
        tasks = self.tasks.get(g["l"])
        if method != "POST" or tasks is None:
            return _error(404, "Not Found")
        for task in tasks.values():
            if task["status"] == "completed":
                task["hidden"] = True
        return FakeResponse(204)


_ROUTES = [
    (r"/users/@me/lists", FakeSession._tasklists),
    (r"/users/@me/lists/(?P<l>[^/]+)", FakeSession._tasklist),
    (r"/lists/(?P<l>[^/]+)/tasks", FakeSession._tasks),
    (r"/lists/(?P<l>[^/]+)/tasks/(?P<t>[^/]+)/move", FakeSession._move),
    (r"/lists/(?P<l>[^/]+)/tasks/(?P<t>[^/]+)", FakeSession._task),
    (r"/lists/(?P<l>[^/]+)/clear", FakeSession._clear),
]
