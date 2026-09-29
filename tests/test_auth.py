import json
import stat
from datetime import datetime

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from gtask import auth
from gtask.errors import AuthError

VALID_TOKEN = {
    "token": "access",
    "refresh_token": "refresh",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "id",
    "client_secret": "secret",
    "scopes": ["https://www.googleapis.com/auth/tasks"],
    "expiry": "2099-01-01T00:00:00Z",
}


@pytest.fixture(autouse=True)
def cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("GTASK_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path / "cfg"


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_scopes():
    assert auth.SCOPES == ["https://www.googleapis.com/auth/tasks"]


def test_login_without_client_secret_is_auth_error():
    with pytest.raises(AuthError) as exc:
        auth.login()
    assert "docs/google-setup.md" in exc.value.message
    assert "--credentials" in exc.value.message


def test_login_installs_secret_runs_flow_and_saves_token(tmp_path, monkeypatch, cfg):
    source = tmp_path / "client_secret_123.json"
    source.write_text('{"installed": {"client_id": "x"}}')
    seen = {}

    class FakeCreds:
        def to_json(self):
            return json.dumps(VALID_TOKEN)

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            seen["path"], seen["scopes"] = path, scopes
            return cls()

        def run_local_server(self, port):
            seen["port"] = port
            return FakeCreds()

    monkeypatch.setattr(auth, "InstalledAppFlow", FakeFlow)
    auth.login(source)
    assert seen == {"path": str(cfg / "client_secret.json"), "scopes": auth.SCOPES, "port": 0}
    assert (cfg / "client_secret.json").read_text() == source.read_text()
    assert json.loads((cfg / "token.json").read_text()) == VALID_TOKEN
    assert mode(cfg / "client_secret.json") == 0o600
    assert mode(cfg / "token.json") == 0o600


def test_login_reuses_installed_secret(monkeypatch, cfg):
    cfg.mkdir()
    (cfg / "client_secret.json").write_text("{}")

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            return cls()

        def run_local_server(self, port):
            class C:
                def to_json(self):
                    return "{}"

            return C()

    monkeypatch.setattr(auth, "InstalledAppFlow", FakeFlow)
    auth.login()
    assert (cfg / "token.json").exists()


def test_login_with_invalid_client_file_is_auth_error(tmp_path, monkeypatch):
    source = tmp_path / "bad.json"
    source.write_text('{"not": "a client"}')

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            raise ValueError("Client secrets must be for a web or installed app.")

    monkeypatch.setattr(auth, "InstalledAppFlow", FakeFlow)
    with pytest.raises(AuthError) as exc:
        auth.login(source)
    assert "not a valid OAuth client file" in exc.value.message


def test_logout_removes_token(cfg):
    assert auth.logout() is False
    cfg.mkdir()
    (cfg / "token.json").write_text("{}")
    assert auth.logout() is True
    assert not (cfg / "token.json").exists()


def test_load_credentials_missing_token_is_auth_error():
    with pytest.raises(AuthError) as exc:
        auth.load_credentials()
    assert "gtask login" in exc.value.message


def test_load_credentials_malformed_token_is_auth_error(cfg):
    cfg.mkdir()
    (cfg / "token.json").write_text(json.dumps({"token": "only"}))
    with pytest.raises(AuthError) as exc:
        auth.load_credentials()
    assert "gtask login" in exc.value.message


def test_load_credentials_valid_token_no_refresh(cfg, monkeypatch):
    cfg.mkdir()
    (cfg / "token.json").write_text(json.dumps(VALID_TOKEN))
    monkeypatch.setattr(Credentials, "refresh", lambda self, request: pytest.fail("refreshed"))
    creds = auth.load_credentials()
    assert creds.token == "access"


def test_load_credentials_expired_refreshes_and_saves(cfg, monkeypatch):
    cfg.mkdir()
    (cfg / "token.json").write_text(json.dumps(VALID_TOKEN | {"expiry": "2000-01-01T00:00:00Z"}))

    def fake_refresh(self, request):
        self.token = "fresh"
        self.expiry = datetime(2099, 1, 1)  # noqa: DTZ001

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)
    creds = auth.load_credentials()
    assert creds.token == "fresh"
    assert json.loads((cfg / "token.json").read_text())["token"] == "fresh"
    assert mode(cfg / "token.json") == 0o600


def test_load_credentials_refresh_failure_is_auth_error(cfg, monkeypatch):
    cfg.mkdir()
    (cfg / "token.json").write_text(json.dumps(VALID_TOKEN | {"expiry": "2000-01-01T00:00:00Z"}))

    def fake_refresh(self, request):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)
    with pytest.raises(AuthError) as exc:
        auth.load_credentials()
    assert exc.value.message == auth.LOGIN_HINT


def test_make_session_wraps_credentials(cfg, monkeypatch):
    cfg.mkdir()
    (cfg / "token.json").write_text(json.dumps(VALID_TOKEN))
    session = auth.make_session()
    assert session.credentials.token == "access"


def test_save_token_tightens_existing_permissive_file(cfg):
    cfg.mkdir()
    token_path = cfg / "token.json"
    token_path.write_text("{}")
    import os

    os.chmod(token_path, 0o644)

    class FakeCreds:
        def to_json(self):
            return "{}"

    auth.save_token(FakeCreds())
    assert mode(token_path) == 0o600
    assert token_path.read_text() == "{}"
