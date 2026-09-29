"""OAuth 2.0 installed-app login, token persistence, and the authorized HTTP session."""

import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config
from .errors import AuthError

SCOPES = ["https://www.googleapis.com/auth/tasks"]
LOGIN_HINT = "Not logged in or token expired. Run: gtask login"


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(path, 0o600)


def install_client_secret(source: Path) -> Path:
    destination = config.client_secret_path()
    _write_private(destination, Path(source).read_text())
    return destination


def login(credentials_file: Path | None = None) -> None:
    if credentials_file is not None:
        install_client_secret(credentials_file)
    secret = config.client_secret_path()
    if not secret.exists():
        raise AuthError(
            f"No OAuth client found at {secret}.\n"
            "Follow docs/google-setup.md to create one, then run: "
            "gtask login --credentials <downloaded client_secret json>"
        )
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    except ValueError as exc:
        raise AuthError(f"{secret} is not a valid OAuth client file: {exc}") from exc
    creds = flow.run_local_server(port=0)
    save_token(creds)


def save_token(creds) -> None:
    _write_private(config.token_path(), creds.to_json())


def logout() -> bool:
    path = config.token_path()
    if path.exists():
        path.unlink()
        return True
    return False


def load_credentials() -> Credentials:
    path = config.token_path()
    if not path.exists():
        raise AuthError("Not logged in. Run: gtask login")
    try:
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    except ValueError as exc:
        raise AuthError(f"Token file {path} is unreadable ({exc}). Run: gtask login") from exc
    if not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise AuthError(LOGIN_HINT) from exc
        save_token(creds)
    return creds


def make_session() -> AuthorizedSession:
    return AuthorizedSession(load_credentials())
