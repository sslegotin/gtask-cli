import json

from gtask import cli


def test_no_args_shows_help(run):
    result = run()
    assert result.exit_code == 2
    assert "Usage" in result.output


def test_login_passes_credentials_and_reports(run, monkeypatch, tmp_path, config_dir):
    called = {}
    monkeypatch.setattr(cli, "auth_login", lambda path: called.setdefault("path", path))
    source = tmp_path / "client_secret_abc.json"
    source.write_text("{}")
    result = run("login", "--credentials", str(source))
    assert result.exit_code == 0, result.output
    assert called["path"] == source
    assert "Logged in" in result.output
    assert str(config_dir / "token.json") in result.output


def test_login_json(run, monkeypatch):
    monkeypatch.setattr(cli, "auth_login", lambda path: None)
    result = run("login", "--json")
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"logged_in": True}


def test_login_missing_credentials_file_is_usage_error(run):
    result = run("login", "--credentials", "/nonexistent/file.json")
    assert result.exit_code == 2


def test_login_without_client_secret_exits_3(run):
    result = run("login")
    assert result.exit_code == 3
    assert "error: No OAuth client found" in result.output
    assert "docs/google-setup.md" in result.output


def test_logout(run, config_dir):
    config_dir.mkdir()
    (config_dir / "token.json").write_text("{}")
    result = run("logout")
    assert result.exit_code == 0 and "Logged out" in result.output
    assert not (config_dir / "token.json").exists()
    result = run("--json", "logout")
    assert json.loads(result.stdout) == {"logged_in": False}


def test_status_without_files(run, config_dir):
    result = run("status")
    assert result.exit_code == 0
    assert f"config dir:     {config_dir}" in result.output
    assert "client secret:  missing" in result.output
    assert "token:          missing" in result.output
    assert "default list:   (first list)" in result.output


def test_status_json_with_files(run, config_dir):
    config_dir.mkdir()
    (config_dir / "token.json").write_text("{}")
    (config_dir / "config.toml").write_text('default_list = "L1"\n')
    result = run("status", "--json")
    assert json.loads(result.stdout) == {
        "config_dir": str(config_dir),
        "client_secret": False,
        "token": True,
        "default_list": "L1",
    }


def test_unexpected_exception_is_exit_1(run, monkeypatch):
    def boom(path):
        raise RuntimeError("wat")

    monkeypatch.setattr(cli, "auth_login", boom)
    result = run("login")
    assert result.exit_code == 1
    assert "error: unexpected: RuntimeError('wat')" in result.output


def test_debug_env_reraises(run, monkeypatch):
    def boom(path):
        raise RuntimeError("wat")

    monkeypatch.setattr(cli, "auth_login", boom)
    monkeypatch.setenv("GTASK_DEBUG", "1")
    result = run("login")
    assert isinstance(result.exception, RuntimeError)
