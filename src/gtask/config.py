"""Config directory resolution and the tiny config.toml."""

import json
import os
import tomllib
from pathlib import Path


def config_dir() -> Path:
    override = os.environ.get("GTASK_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "gtask"


def client_secret_path() -> Path:
    return config_dir() / "client_secret.json"


def token_path() -> Path:
    return config_dir() / "token.json"


def config_path() -> Path:
    return config_dir() / "config.toml"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text())


def save_config(cfg: dict) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    # json.dumps of a str is a valid TOML basic string (same escape rules for our needs).
    lines = [f"{key} = {json.dumps(value)}" for key, value in cfg.items()]
    config_path().write_text("\n".join(lines) + "\n")


def get_default_list() -> str | None:
    return load_config().get("default_list")


def set_default_list(list_id: str) -> None:
    cfg = load_config()
    cfg["default_list"] = list_id
    save_config(cfg)
