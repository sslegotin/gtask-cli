"""Thin typed client for the Google Tasks REST API v1.

The session is injected so tests can pass an in-memory fake. Any object with
`request(method, url, params=..., json=...)` returning a requests-like response works.
"""

from .errors import ApiError, AuthError

BASE_URL = "https://tasks.googleapis.com/tasks/v1"
LOGIN_HINT = "Not logged in or token expired. Run: gtask login"


def _flag(value: bool) -> str:
    return "true" if value else "false"


class TasksClient:
    def __init__(self, session) -> None:
        self._session = session

    # ---- transport --------------------------------------------------------

    def _request(self, method: str, path: str, params: dict | None = None, json: dict | None = None):
        response = self._session.request(method, BASE_URL + path, params=params or {}, json=json)
        if response.status_code == 401:
            raise AuthError(LOGIN_HINT)
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except Exception:
                message = response.text or "unknown error"
            raise ApiError(response.status_code, message)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def _paginate(self, path: str, params: dict) -> list[dict]:
        params = dict(params, maxResults=100)
        items: list[dict] = []
        while True:
            page = self._request("GET", path, params=params)
            items.extend(page.get("items", []))
            token = page.get("nextPageToken")
            if not token:
                return items
            params["pageToken"] = token

    # ---- task lists -------------------------------------------------------

    def list_tasklists(self) -> list[dict]:
        return self._paginate("/users/@me/lists", {})

    def get_tasklist(self, list_id: str) -> dict:
        return self._request("GET", f"/users/@me/lists/{list_id}")

    def create_tasklist(self, title: str) -> dict:
        return self._request("POST", "/users/@me/lists", json={"title": title})

    def patch_tasklist(self, list_id: str, title: str) -> dict:
        return self._request("PATCH", f"/users/@me/lists/{list_id}", json={"title": title})

    def delete_tasklist(self, list_id: str) -> None:
        self._request("DELETE", f"/users/@me/lists/{list_id}")

    # ---- tasks ------------------------------------------------------------

    def list_tasks(
        self,
        list_id: str,
        *,
        show_completed: bool = True,
        show_hidden: bool = False,
        due_min: str | None = None,
        due_max: str | None = None,
    ) -> list[dict]:
        params = {"showCompleted": _flag(show_completed), "showHidden": _flag(show_hidden)}
        if due_min:
            params["dueMin"] = due_min
        if due_max:
            params["dueMax"] = due_max
        return self._paginate(f"/lists/{list_id}/tasks", params)

    def get_task(self, list_id: str, task_id: str) -> dict:
        return self._request("GET", f"/lists/{list_id}/tasks/{task_id}")

    def create_task(
        self, list_id: str, body: dict, *, parent: str | None = None, previous: str | None = None
    ) -> dict:
        params = {}
        if parent:
            params["parent"] = parent
        if previous:
            params["previous"] = previous
        return self._request("POST", f"/lists/{list_id}/tasks", params=params, json=body)

    def patch_task(self, list_id: str, task_id: str, body: dict) -> dict:
        return self._request("PATCH", f"/lists/{list_id}/tasks/{task_id}", json=body)

    def update_task(self, list_id: str, task_id: str, body: dict) -> dict:
        return self._request("PUT", f"/lists/{list_id}/tasks/{task_id}", json=body)

    def delete_task(self, list_id: str, task_id: str) -> None:
        self._request("DELETE", f"/lists/{list_id}/tasks/{task_id}")

    def move_task(
        self,
        list_id: str,
        task_id: str,
        *,
        parent: str | None = None,
        previous: str | None = None,
        destination_list: str | None = None,
    ) -> dict:
        params = {}
        if parent:
            params["parent"] = parent
        if previous:
            params["previous"] = previous
        if destination_list:
            params["destinationTasklist"] = destination_list
        return self._request("POST", f"/lists/{list_id}/tasks/{task_id}/move", params=params)

    def clear_tasks(self, list_id: str) -> None:
        self._request("POST", f"/lists/{list_id}/clear")
