# gtask: Google Tasks CLI — Design Spec

Date: 2026-09-29
Status: approved for planning

## 1. Purpose

A small command-line tool, `gtask`, that lets a person and an AI coding
agent (Claude Code, invoking it through a shell) create, read, update,
delete, complete, and reorganize tasks in the person's Google Tasks
account. Human-readable output by default; `--json` for machine use.

Secondary goals:

- Shareable with colleagues and friends, who install it from GitHub or
  receive a standalone binary. Each user supplies their own Google OAuth
  client (see §3 and the setup guide).
- A newcomer to the Google ecosystem can get from zero to a working login
  by following `docs/google-setup.md`.

Non-goals for v1: multiple simultaneous accounts, assigned tasks
(Chat/Docs/Spaces), recurring-task semantics, offline cache, shell
completion, MCP server mode.

## 2. Stack

- Python 3.12+, Poetry-managed project (`pyproject.toml`, poetry-core
  build backend, PEP 621 `[project]` table), `src/` layout.
- Runtime deps: `typer`, `google-auth`, `google-auth-oauthlib`,
  `requests` (pulled by google-auth's `AuthorizedSession`).
- Dev deps: `pytest`, `ruff`. Bundle group: `pyinstaller`.
- Google Tasks REST API v1 is called directly over HTTPS; no
  `google-api-python-client`.
- Entry point: `[project.scripts] gtask = "gtask.cli:app"`.

## 3. Authentication

Google Tasks data is private, so plain API keys do not work; OAuth 2.0
"installed app" flow is used with scope
`https://www.googleapis.com/auth/tasks`.

Files, all under the config dir (`$GTASK_CONFIG_DIR`, else
`$XDG_CONFIG_HOME/gtask`, else `~/.config/gtask`):

| File                 | Content                                              | Mode |
|----------------------|------------------------------------------------------|------|
| `client_secret.json` | OAuth client downloaded from Google Cloud console    | 600  |
| `token.json`         | Access + refresh token as written by google-auth     | 600  |
| `config.toml`        | `default_list = "<tasklist id>"` (optional)          | 644  |

Flow:

- `gtask login [--credentials FILE]`: if `FILE` is given, it is copied to
  `client_secret.json` (overwriting). Then `InstalledAppFlow.run_local_server(port=0)`
  opens the browser, the person consents, and the token is saved. If no
  client secret exists and none is given, exit 3 with a pointer to the
  setup guide.
- Every other command builds an `AuthorizedSession` from `token.json`.
  google-auth refreshes the access token transparently. If the token file
  is missing or the refresh is rejected (`invalid_grant`, e.g. the 7-day
  expiry for consent screens still in "Testing"), print
  `Not logged in or token expired. Run: gtask login` to stderr, exit 3.
- `gtask logout` deletes `token.json` only.
- `gtask status` prints config dir, whether client secret and token exist,
  and the default list (title + id) if set. Never fails on missing auth.

The setup guide (`docs/google-setup.md`) walks through: create Cloud
project → enable "Google Tasks API" → Google Auth Platform wizard (App
information, Audience = External, Contact, Finish) → Audience tab: add
own email as test user *or* publish to production (skipping verification
shows a one-time "unverified app" screen but removes the 7-day token
expiry) → Clients tab → Create client → Desktop app → download JSON →
`gtask login --credentials ~/Downloads/client_secret_*.json`. It states
plainly that for a Desktop-type client the "secret" is not treated as
secret by Google, and that every friend repeats these steps for their
own project.

## 4. Module layout

```
src/gtask/
  __init__.py     version
  cli.py          typer app; argument parsing, --json switch, exit codes
  api.py          TasksClient: one method per REST endpoint, returns dicts
  auth.py         config-dir paths for auth files, login/logout, session factory
  config.py       config dir resolution, config.toml read/write
  resolve.py      LIST / TASK reference resolution
  dates.py        due-date parsing and formatting
  render.py       human output: tables, tree, single-task view
  errors.py       GtaskError hierarchy with exit codes
docs/google-setup.md
scripts/build-binary.sh
tests/
```

Dependency direction: `cli → (resolve, render, dates, auth, config) → api → errors`.
`api` never imports `cli`; `render` never calls the network.

### api.py

`TasksClient(session)` where `session` is anything with
`request(method, url, params=..., json=...) -> response` (a
`requests.Session`-like object). Base URL `https://tasks.googleapis.com/tasks/v1`.

| Method                                              | HTTP                                            |
|-----------------------------------------------------|-------------------------------------------------|
| `list_tasklists()`                                  | GET `/users/@me/lists` (paginated, all pages)   |
| `get_tasklist(id)`                                  | GET `/users/@me/lists/{id}`                     |
| `create_tasklist(title)`                            | POST `/users/@me/lists`                         |
| `patch_tasklist(id, title)`                         | PATCH `/users/@me/lists/{id}`                   |
| `delete_tasklist(id)`                               | DELETE `/users/@me/lists/{id}`                  |
| `list_tasks(list_id, show_completed, show_hidden, due_min, due_max)` | GET `/lists/{l}/tasks` (all pages, maxResults=100) |
| `get_task(list_id, task_id)`                        | GET `/lists/{l}/tasks/{t}`                      |
| `create_task(list_id, body, parent=None, previous=None)` | POST `/lists/{l}/tasks?parent&previous`     |
| `patch_task(list_id, task_id, body)`                | PATCH `/lists/{l}/tasks/{t}`                    |
| `delete_task(list_id, task_id)`                     | DELETE `/lists/{l}/tasks/{t}`                   |
| `move_task(list_id, task_id, parent=None, previous=None, destination_list=None)` | POST `/lists/{l}/tasks/{t}/move` |
| `clear_tasks(list_id)`                              | POST `/lists/{l}/clear`                         |

Non-2xx responses raise `ApiError(status, message)` where `message` is
`error.message` from the JSON body when present. 401 raises `AuthError`.

### resolve.py

- `resolve_list(client, ref, config) -> tasklist dict`
  Order: exact id match → unique id prefix → case-insensitive exact title
  match. `ref=None` means the configured default list; if none is
  configured, the first list returned by the API (Google's "My Tasks").
  Ambiguous prefix → `AmbiguousError` listing candidates. Not found →
  `NotFoundError`. Both exit 4.
- `resolve_task(client, ref, list_ref) -> (tasklist dict, task dict)`
  Exact id or unique prefix. If `list_ref` is given, only that list is
  searched (`show_completed=True, show_hidden=True`). If not, every list
  is searched. Same error semantics; the ambiguity message shows each
  candidate's list title and task title.
- `short_ids(ids, minimum=4) -> dict[id, prefix]`: shortest prefix that is
  unique within the given set, at least `minimum` chars. Used by render.

### dates.py

`parse_due(text) -> date`: accepts `YYYY-MM-DD`, `today`, `tomorrow`,
`+Nd` (N days from today). Anything else → `UsageError` (exit 2).
`to_api(date) -> str` produces `YYYY-MM-DDT00:00:00.000Z`.
`from_api(str) -> str` returns the `YYYY-MM-DD` portion.

### render.py

- `render_lists(lists, default_id)`: columns `ID  TITLE`, `*` marker on
  the default.
- `render_tasks(tasks)`: builds parent → children tree from `parent`
  fields, ordered by `position`; prints `ID  [ ]|[x]  DUE  TITLE`, children
  indented two spaces per level. `--flat` skips indentation and prints in
  API order. A note marker `+` after the title when `notes` is non-empty.
- `render_task(task, list_title)`: multi-line view: title, list, status,
  due, completed date, parent short id, full id, notes, webViewLink.

### cli.py

Global option `--json` (also on every subcommand; typer callback stores
it in a context object). In JSON mode the command prints exactly one
JSON document to stdout and nothing else. Human text goes to stdout;
all errors go to stderr.

## 5. Commands

```
gtask login [--credentials FILE]
gtask logout
gtask status

gtask lists                              # all task lists
gtask lists create TITLE
gtask lists rename LIST TITLE
gtask lists delete LIST [--yes]          # confirm unless --yes or --json
gtask lists default LIST                 # write default_list to config.toml

gtask ls [-l LIST] [--all] [--flat] [--due-before DATE] [--due-after DATE]
gtask show TASK [-l LIST]
gtask add TITLE [-l LIST] [-n NOTES] [-d DUE] [-p PARENT] [--after TASK]
gtask update TASK [-l LIST] [--title T] [-n NOTES] [-d DUE | --no-due]
gtask done TASK... [-l LIST]
gtask undone TASK... [-l LIST]
gtask delete TASK... [-l LIST] [--yes]   # confirm unless --yes or --json
gtask move TASK [-l LIST] [-p PARENT | --top] [--after TASK | --first] [--to LIST]
gtask clear [-l LIST]                    # clears completed tasks
```

Semantics:

- `ls` default: open tasks only (`showCompleted=false`); `--all` includes
  completed. `--due-before/--due-after` accept the same forms as `-d`.
- `add`: `-p PARENT` resolves within the target list; `--after` likewise.
  Body: `title`, optional `notes`, optional `due`.
- `update`: only the given fields are sent (PATCH). `--no-due` sends
  `"due": null`... Google ignores null on PATCH, so `--no-due` is
  implemented as a full PUT of the task with `due` removed. `-n ""`
  clears notes the same way.
- `done` / `undone`: PATCH `status` to `completed` / `needsAction`.
  `undone` also clears `completed`. Multiple TASK args are resolved
  first, then applied; any resolution failure aborts before writes.
- `delete`: interactive `y/N` confirmation listing the titles, skipped
  with `--yes` or in `--json` mode.
- `move`: `--to LIST` uses `destinationTasklist`; parent/after
  references resolve within the destination list when `--to` is given,
  otherwise within the task's current list. `--top` = omit parent,
  `--first` = omit previous. With neither position flag and no `--to`,
  the command errors with usage (exit 2).
- `lists delete` warns that all tasks in the list are deleted.

JSON output shapes:

| Command                 | stdout                                            |
|-------------------------|---------------------------------------------------|
| `lists`, `ls`           | JSON array of API objects                         |
| `lists create/rename`, `show`, `add`, `update`, `move` | the API object |
| `done`, `undone`        | JSON array of the updated API objects             |
| `delete`, `lists delete`| `{"deleted": ["<id>", ...]}`                      |
| `clear`                 | `{"cleared": "<list id>"}`                        |
| `lists default`         | `{"default_list": "<id>"}`                        |
| `status`                | `{"config_dir", "client_secret", "token", "default_list"}` |
| `login`                 | `{"logged_in": true}`                             |
| `logout`                | `{"logged_in": false}`                            |

Exit codes: 0 success; 1 API error or unexpected failure; 2 usage error;
3 login required; 4 reference not found or ambiguous.

## 6. Error handling

`errors.py` defines `GtaskError(exit_code, message)` with subclasses
`UsageError(2)`, `AuthError(3)`, `NotFoundError(4)`, `AmbiguousError(4)`,
`ApiError(1)`. `cli.py` wraps every command: catch `GtaskError`, print
`error: <message>` to stderr, exit with its code. Any other exception
prints `error: unexpected: <repr>` and exits 1 (full traceback only with
`GTASK_DEBUG=1`). Network failures (`requests.ConnectionError`) map to
exit 1 with a short message.

## 7. Testing

- `tests/fake_session.py`: in-memory implementation of the twelve
  endpoints (dict-backed task lists and tasks, ids generated, `position`
  maintained, `parent` handling, pagination when >100 items). Exposes
  `request()` matching the `TasksClient` contract.
- Unit tests: `dates`, `resolve` (prefix, title, ambiguity, cross-list
  search), `render` (tree ordering, short ids), `config`.
- Command tests: `typer.testing.CliRunner` with `GTASK_CONFIG_DIR` set
  to a tmp dir and the session factory monkeypatched to return the fake.
  Cover every command in both human and JSON modes, confirmation
  prompts, and exit codes.
- `tests/test_live.py`: skipped unless `GTASK_LIVE=1` and a token exists;
  creates a temporary task list, exercises add/update/move/done/delete,
  deletes the list.
- `poetry run pytest` must run offline in well under a second.

## 8. Distribution

- Local dev install: `uv tool install --editable .` (or
  `pipx install --editable .`). Poetry stays the dev tool.
- Friends with Python: `uv tool install git+https://github.com/<user>/gtask`
  (or `git+ssh://...` for a private repo). README documents installing
  uv first.
- Friends without Python: `scripts/build-binary.sh` runs
  `poetry install --with bundle && poetry run pyinstaller --onefile --name gtask src/gtask/__main__.py`
  and reports `dist/gtask`. README notes: one build per OS/CPU, and the
  macOS quarantine workaround (`xattr -d com.apple.quarantine gtask`).
- README has a short "Using gtask from an AI agent" section: always pass
  `--json`, never rely on short ids across calls, use exit codes.

## 9. Open items deliberately deferred

- Recurring/assigned tasks are shown as returned; `move` on them may fail
  with Google's error, which is surfaced as-is.
- Shell completion, MCP server, multiple profiles: later versions.
