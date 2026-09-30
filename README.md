# gtask

Google Tasks from the command line, for humans and AI agents.

```
$ gtask ls
Tmil  [ ]  2026-10-01  Buy milk
Trep  [ ]              Report +
Tout  [ ]                Outline
$ gtask done Tout
Completed Tout00000  Outline
$ gtask add "Call bank" -d tomorrow -n "ask about the fee"
```

## Install

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`brew install uv`
or `curl -LsSf https://astral.sh/uv/install.sh | sh`). `pipx` works the same
way if you prefer it.

From GitHub:

```bash
uv tool install git+https://github.com/sslegotin/gtask-cli
```

From a checkout, tracking your edits:

```bash
uv tool install --editable .
```

Standalone binary (no Python needed on the target machine; one build per OS
and CPU):

```bash
scripts/build-binary.sh        # writes dist/gtask
```

On macOS a downloaded binary may be blocked by Gatekeeper; fix with
`xattr -d com.apple.quarantine gtask`.

## First-time setup

gtask needs its own Google OAuth client. Follow
[docs/google-setup.md](docs/google-setup.md) (about ten minutes), then:

```bash
gtask login --credentials ~/Downloads/client_secret_*.json
```

## Usage

```
gtask login [--credentials FILE]     gtask logout     gtask status

gtask lists                          show task lists (* = default)
gtask lists create TITLE
gtask lists rename LIST TITLE
gtask lists delete LIST [--yes]
gtask lists default LIST             list used when -l is omitted

gtask ls [-l LIST] [--all] [--flat] [--due-before DATE] [--due-after DATE]
gtask show TASK [-l LIST]
gtask add TITLE [-l LIST] [-n NOTES] [-d DUE] [-p PARENT] [--after TASK]
gtask update TASK [-l LIST] [--title T] [-n NOTES] [-d DUE | --no-due]
gtask done TASK...      gtask undone TASK...      gtask delete TASK... [--yes]
gtask move TASK [-p PARENT | --top] [--after TASK | --first] [--to LIST]
gtask clear [-l LIST]                hide completed tasks
```

`gtask <command> --help` has the details.

- **LIST** is an id, a unique id prefix, or a list title (case-insensitive).
- **TASK** is an id or a unique id prefix. `ls` prints the shortest unique
  prefix, so you can type what you see. Without `-l`, tasks are looked up in
  every list.
- **DATE** is `YYYY-MM-DD`, `today`, `tomorrow`, or `+3d`. Google Tasks stores
  dates only, no times.
- `+` after a title in `ls` means the task has notes; `gtask show` prints them.

## JSON mode and exit codes

Add `--json` to any command (before or after the subcommand) to get the raw
API objects on stdout. Errors always go to stderr as `error: <message>`.

| Exit code | Meaning |
|-----------|---------|
| 0 | success |
| 1 | API error, network failure, or unexpected error |
| 2 | usage error (bad flag, bad date, missing argument) |
| 3 | login required (`gtask login`) |
| 4 | reference not found or ambiguous |

Set `GTASK_DEBUG=1` to see full tracebacks. Set `GTASK_CONFIG_DIR` to use a
different config directory (default `$XDG_CONFIG_HOME/gtask` if set, else
`~/.config/gtask`).

## Using gtask from an AI agent

- Always pass `--json`; parse stdout, check the exit code, read stderr on
  failure.
- Use full ids from JSON output in later calls. Short prefixes are for people
  and can change as tasks come and go.
- `delete` and `lists delete` never prompt in `--json` mode.
- `done`, `undone`, `delete` accept several TASK arguments and resolve all of
  them before changing anything.

## Development

```bash
poetry install
poetry run pytest          # offline, uses an in-memory fake of the API
poetry run ruff check src tests
GTASK_LIVE=1 poetry run pytest tests/test_live.py   # needs a real login
```

Design notes live in `docs/superpowers/specs/`.
