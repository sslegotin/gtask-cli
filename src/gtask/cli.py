"""Command-line interface. Only glue lives here: parsing, output mode, exit codes."""

import functools
import json as jsonlib
import os
from pathlib import Path
from typing import Annotated, Optional

import requests
import typer
from google.auth.exceptions import RefreshError

from . import config
from .api import TasksClient
from .auth import LOGIN_HINT, login as auth_login, logout as auth_logout, make_session
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
    Optional[str],
    typer.Option("-l", "--list", metavar="LIST", help="Task list: id, id prefix, or title."),
]
YesOpt = Annotated[bool, typer.Option("-y", "--yes", help="Skip the confirmation prompt.")]
TaskArg = Annotated[str, typer.Argument(metavar="TASK", help="Task id or unique id prefix.")]
TasksArg = Annotated[
    list[str], typer.Argument(metavar="TASK...", help="Task ids or unique id prefixes.")
]


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
        Optional[Path],
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
