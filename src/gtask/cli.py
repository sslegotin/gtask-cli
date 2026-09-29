"""Command-line interface. Only glue lives here: parsing, output mode, exit codes."""

import functools
import json as jsonlib
import os
from pathlib import Path
from typing import Annotated

import requests
import typer
from google.auth.exceptions import RefreshError

from . import config
from .api import TasksClient
from .auth import LOGIN_HINT, make_session
from .auth import login as auth_login
from .auth import logout as auth_logout
from .dates import parse_due, to_api
from .errors import GtaskError, UsageError
from .render import render_lists, render_task, render_tasks
from .resolve import find_task, resolve_list, resolve_task

app = typer.Typer(
    help="Google Tasks from the command line, for humans and AI agents.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
lists_app = typer.Typer(help="Manage task lists. Without a subcommand, shows them.")
app.add_typer(lists_app, name="lists")

JsonOpt = Annotated[bool, typer.Option("--json", help="Print JSON instead of text.")]
ListOpt = Annotated[
    str | None,
    typer.Option("-l", "--list", metavar="LIST", help="Task list: id, id prefix, or title."),
]
YesOpt = Annotated[bool, typer.Option("-y", "--yes", help="Skip the confirmation prompt.")]
TaskArg = Annotated[str, typer.Argument(metavar="TASK", help="Task id or unique id prefix.")]
TasksArg = Annotated[
    list[str], typer.Argument(metavar="TASK...", help="Task ids or unique id prefixes.")
]
ListArg = Annotated[str, typer.Argument(metavar="LIST", help="Task list id, id prefix, or title.")]


def handle_errors(fn):
    """Map exceptions to stderr messages and exit codes. Applied to every command."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except GtaskError as exc:
            typer.echo(f"error: {exc.message}", err=True)
            raise typer.Exit(exc.exit_code)
        except RefreshError:
            typer.echo(f"error: {LOGIN_HINT}", err=True)
            raise typer.Exit(3)
        except requests.ConnectionError as exc:
            typer.echo(f"error: network failure: {exc}", err=True)
            raise typer.Exit(1)
        except (typer.Exit, typer.Abort, KeyboardInterrupt):
            raise
        except Exception as exc:
            if os.environ.get("GTASK_DEBUG"):
                raise
            typer.echo(f"error: unexpected: {exc!r}", err=True)
            raise typer.Exit(1)

    return wrapper


def _json(ctx: typer.Context, flag: bool) -> bool:
    return flag or bool(ctx.obj and ctx.obj.get("json"))


def emit(data, as_json: bool, text: str) -> None:
    if as_json:
        typer.echo(jsonlib.dumps(data, indent=2, ensure_ascii=False))
    else:
        typer.echo(text)


def client() -> TasksClient:
    return TasksClient(make_session())


@app.callback()
def main(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Google Tasks from the command line, for humans and AI agents."""
    ctx.obj = {"json": json_}


# ---- auth -----------------------------------------------------------------


@app.command()
@handle_errors
def login(
    ctx: typer.Context,
    credentials: Annotated[
        Path | None,
        typer.Option(
            "--credentials",
            exists=True,
            dir_okay=False,
            readable=True,
            help="OAuth client JSON downloaded from Google Cloud console. Stored for next time.",
        ),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Log in to Google Tasks through the browser."""
    auth_login(credentials)
    emit({"logged_in": True}, _json(ctx, json_), f"Logged in. Token saved to {config.token_path()}")


@app.command()
@handle_errors
def logout(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Forget the stored token (the OAuth client file is kept)."""
    auth_logout()
    emit({"logged_in": False}, _json(ctx, json_), "Logged out.")


@app.command()
@handle_errors
def status(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Show config location, login state, and the default list."""
    secret, token = config.client_secret_path(), config.token_path()
    default = config.get_default_list()
    data = {
        "config_dir": str(config.config_dir()),
        "client_secret": secret.exists(),
        "token": token.exists(),
        "default_list": default,
    }
    text = "\n".join(
        [
            f"config dir:     {data['config_dir']}",
            f"client secret:  {'present' if data['client_secret'] else 'missing'} ({secret})",
            f"token:          {'present' if data['token'] else 'missing'} ({token})",
            f"default list:   {default or '(first list)'}",
        ]
    )
    emit(data, _json(ctx, json_), text)


# ---- task lists -------------------------------------------------------------


@lists_app.callback(invoke_without_command=True)
@handle_errors
def lists_main(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Show task lists (default marked with *), or run a subcommand."""
    if json_:
        ctx.obj["json"] = True
    if ctx.invoked_subcommand is not None:
        return
    lists = client().list_tasklists()
    emit(lists, _json(ctx, json_), render_lists(lists, config.get_default_list()))


@lists_app.command("create")
@handle_errors
def lists_create(ctx: typer.Context, title: str, json_: JsonOpt = False) -> None:
    """Create a task list."""
    tasklist = client().create_tasklist(title)
    emit(tasklist, _json(ctx, json_), f"Created list {tasklist['id']}  {tasklist['title']}")


@lists_app.command("rename")
@handle_errors
def lists_rename(ctx: typer.Context, list_ref: ListArg, title: str, json_: JsonOpt = False) -> None:
    """Rename a task list."""
    api = client()
    tasklist = resolve_list(api, list_ref, config.get_default_list())
    tasklist = api.patch_tasklist(tasklist["id"], title)
    emit(tasklist, _json(ctx, json_), f"Renamed list {tasklist['id']}  {tasklist['title']}")


@lists_app.command("delete")
@handle_errors
def lists_delete(
    ctx: typer.Context, list_ref: ListArg, yes: YesOpt = False, json_: JsonOpt = False
) -> None:
    """Delete a task list and every task in it."""
    api = client()
    tasklist = resolve_list(api, list_ref, config.get_default_list())
    as_json = _json(ctx, json_)
    if not yes and not as_json:
        typer.confirm(f"Delete list {tasklist['title']!r} and ALL its tasks?", abort=True)
    api.delete_tasklist(tasklist["id"])
    emit(
        {"deleted": [tasklist["id"]]},
        as_json,
        f"Deleted list {tasklist['id']}  {tasklist['title']}",
    )


@lists_app.command("default")
@handle_errors
def lists_default(ctx: typer.Context, list_ref: ListArg, json_: JsonOpt = False) -> None:
    """Set the list used when -l/--list is omitted."""
    tasklist = resolve_list(client(), list_ref)
    config.set_default_list(tasklist["id"])
    emit(
        {"default_list": tasklist["id"]},
        _json(ctx, json_),
        f"Default list set to {tasklist['id']}  {tasklist['title']}",
    )


# ---- reading tasks ----------------------------------------------------------

DateOptHelp = "YYYY-MM-DD, today, tomorrow, or +Nd."


@app.command()
@handle_errors
def ls(
    ctx: typer.Context,
    list_ref: ListOpt = None,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Include completed tasks.")] = False,
    flat: Annotated[bool, typer.Option("--flat", help="No tree indentation; API order.")] = False,
    due_before: Annotated[
        str | None,
        typer.Option(
            "--due-before", metavar="DATE", help=f"Only tasks due on or before DATE. {DateOptHelp}"
        ),
    ] = None,
    due_after: Annotated[
        str | None,
        typer.Option(
            "--due-after", metavar="DATE", help=f"Only tasks due on or after DATE. {DateOptHelp}"
        ),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """List tasks in a list (open tasks only unless --all)."""
    due_min = to_api(parse_due(due_after)) if due_after else None
    due_max = to_api(parse_due(due_before)) if due_before else None
    api = client()
    tasklist = resolve_list(api, list_ref, config.get_default_list())
    tasks = api.list_tasks(
        tasklist["id"], show_completed=all_, show_hidden=all_, due_min=due_min, due_max=due_max
    )
    emit(tasks, _json(ctx, json_), render_tasks(tasks, flat=flat))


@app.command()
@handle_errors
def show(
    ctx: typer.Context, task_ref: TaskArg, list_ref: ListOpt = None, json_: JsonOpt = False
) -> None:
    """Show one task in detail."""
    tasklist, task = resolve_task(client(), task_ref, list_ref, config.get_default_list())
    emit(task, _json(ctx, json_), render_task(task, tasklist["title"]))


# ---- writing tasks ----------------------------------------------------------

NotesOpt = Annotated[
    str | None, typer.Option("-n", "--notes", help="Notes text. An empty string clears them.")
]
DueOpt = Annotated[str | None, typer.Option("-d", "--due", metavar="DATE", help=DateOptHelp)]
WRITABLE = ("id", "title", "notes", "status", "due", "completed")


def _put_body(task: dict, remove: set[str], **changes) -> dict:
    """Full-replacement body for PUT: writable fields of `task` minus `remove`, plus `changes`.

    The Tasks API does not reliably clear a field from a PATCH with null, so clearing
    goes through PUT with the field absent.
    """
    body = {key: task[key] for key in WRITABLE if key in task and key not in remove}
    body.update(changes)
    return body


@app.command()
@handle_errors
def add(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="Task title.")],
    list_ref: ListOpt = None,
    notes: NotesOpt = None,
    due: DueOpt = None,
    parent: Annotated[
        str | None,
        typer.Option(
            "-p", "--parent", metavar="TASK", help="Create as a subtask of TASK (same list)."
        ),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option("--after", metavar="TASK", help="Place right after TASK (same list)."),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Add a task to the default list (or -l LIST)."""
    body: dict = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = to_api(parse_due(due))
    api = client()
    tasklist = resolve_list(api, list_ref, config.get_default_list())
    previous = find_task(api, tasklist, after) if after else None
    if parent:
        parent_id = find_task(api, tasklist, parent)["id"]
    elif previous is not None:
        parent_id = previous.get("parent")
    else:
        parent_id = None
    task = api.create_task(
        tasklist["id"], body, parent=parent_id, previous=previous["id"] if previous else None
    )
    emit(task, _json(ctx, json_), f"Added {task['id']}  {task['title']}")


@app.command()
@handle_errors
def update(
    ctx: typer.Context,
    task_ref: TaskArg,
    list_ref: ListOpt = None,
    title: Annotated[str | None, typer.Option("--title", help="New title.")] = None,
    notes: NotesOpt = None,
    due: DueOpt = None,
    no_due: Annotated[bool, typer.Option("--no-due", help="Remove the due date.")] = False,
    json_: JsonOpt = False,
) -> None:
    """Change a task's title, notes, or due date."""
    if due and no_due:
        raise UsageError("--due and --no-due are mutually exclusive")
    if title is None and notes is None and not due and not no_due:
        raise UsageError("Nothing to update: give --title, --notes, --due, or --no-due")
    changes: dict = {}
    remove: set[str] = set()
    if title is not None:
        changes["title"] = title
    if notes is not None:
        if notes == "":
            remove.add("notes")
        else:
            changes["notes"] = notes
    if due:
        changes["due"] = to_api(parse_due(due))
    if no_due:
        remove.add("due")
    api = client()
    tasklist, task = resolve_task(api, task_ref, list_ref, config.get_default_list())
    if remove:
        task = api.update_task(tasklist["id"], task["id"], _put_body(task, remove, **changes))
    else:
        task = api.patch_task(tasklist["id"], task["id"], changes)
    emit(task, _json(ctx, json_), f"Updated {task['id']}  {task['title']}")


# ---- completion, deletion, clearing ----------------------------------------


def _resolve_all(
    api: TasksClient, refs: list[str], list_ref: str | None
) -> list[tuple[dict, dict]]:
    """Resolve every reference before any write, so a bad one aborts the whole command."""
    default = config.get_default_list()
    return [resolve_task(api, ref, list_ref, default) for ref in refs]


@app.command()
@handle_errors
def done(
    ctx: typer.Context, task_refs: TasksArg, list_ref: ListOpt = None, json_: JsonOpt = False
) -> None:
    """Mark tasks completed."""
    api = client()
    results = [
        api.patch_task(tasklist["id"], task["id"], {"status": "completed"})
        for tasklist, task in _resolve_all(api, task_refs, list_ref)
    ]
    emit(
        results, _json(ctx, json_), "\n".join(f"Completed {t['id']}  {t['title']}" for t in results)
    )


@app.command()
@handle_errors
def undone(
    ctx: typer.Context, task_refs: TasksArg, list_ref: ListOpt = None, json_: JsonOpt = False
) -> None:
    """Reopen completed tasks."""
    api = client()
    results = [
        api.update_task(
            tasklist["id"], task["id"], _put_body(task, {"completed"}, status="needsAction")
        )
        for tasklist, task in _resolve_all(api, task_refs, list_ref)
    ]
    emit(
        results, _json(ctx, json_), "\n".join(f"Reopened {t['id']}  {t['title']}" for t in results)
    )


@app.command()
@handle_errors
def delete(
    ctx: typer.Context,
    task_refs: TasksArg,
    list_ref: ListOpt = None,
    yes: YesOpt = False,
    json_: JsonOpt = False,
) -> None:
    """Delete tasks (subtasks go with their parent)."""
    api = client()
    pairs = _resolve_all(api, task_refs, list_ref)
    as_json = _json(ctx, json_)
    if not yes and not as_json:
        listing = "\n".join(f"  {task['id']}  {task['title']}" for _, task in pairs)
        typer.confirm(f"Delete {len(pairs)} task(s):\n{listing}\nProceed?", abort=True)
    for tasklist, task in pairs:
        api.delete_task(tasklist["id"], task["id"])
    emit(
        {"deleted": [task["id"] for _, task in pairs]},
        as_json,
        "\n".join(f"Deleted {task['id']}  {task['title']}" for _, task in pairs),
    )


@app.command()
@handle_errors
def clear(ctx: typer.Context, list_ref: ListOpt = None, json_: JsonOpt = False) -> None:
    """Hide all completed tasks in a list (the app's 'Delete all completed tasks')."""
    api = client()
    tasklist = resolve_list(api, list_ref, config.get_default_list())
    api.clear_tasks(tasklist["id"])
    emit(
        {"cleared": tasklist["id"]},
        _json(ctx, json_),
        f"Cleared completed tasks from {tasklist['title']}",
    )


# ---- moving -------------------------------------------------------------------


@app.command()
@handle_errors
def move(
    ctx: typer.Context,
    task_ref: TaskArg,
    list_ref: ListOpt = None,
    parent: Annotated[
        str | None,
        typer.Option("-p", "--parent", metavar="TASK", help="Make it a subtask of TASK."),
    ] = None,
    top: Annotated[bool, typer.Option("--top", help="Make it a top-level task.")] = False,
    after: Annotated[
        str | None, typer.Option("--after", metavar="TASK", help="Place right after TASK.")
    ] = None,
    first: Annotated[bool, typer.Option("--first", help="Place first among its siblings.")] = False,
    to: Annotated[
        str | None, typer.Option("--to", metavar="LIST", help="Move to another list.")
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Reposition a task: nest, unnest, reorder, or move it to another list."""
    if parent and top:
        raise UsageError("--parent and --top are mutually exclusive")
    if after and first:
        raise UsageError("--after and --first are mutually exclusive")
    if not any([parent, top, after, first, to]):
        raise UsageError("Nothing to do: give --parent/--top, --after/--first, and/or --to LIST")
    api = client()
    default = config.get_default_list()
    tasklist, task = resolve_task(api, task_ref, list_ref, default)
    destination = resolve_list(api, to, default) if to else tasklist
    previous = find_task(api, destination, after) if after else None
    if parent:
        parent_id = find_task(api, destination, parent)["id"]
    elif top:
        parent_id = None
    elif previous is not None:
        parent_id = previous.get("parent")  # stay a sibling of --after
    elif to:
        parent_id = None
    else:
        parent_id = task.get("parent")  # --first alone keeps the current nesting
    moved = api.move_task(
        tasklist["id"],
        task["id"],
        parent=parent_id,
        previous=previous["id"] if previous else None,
        destination_list=destination["id"] if to else None,
    )
    emit(moved, _json(ctx, json_), f"Moved {moved['id']}  {moved['title']}")
