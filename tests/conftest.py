import pytest
from typer.testing import CliRunner

from gtask.cli import app
from tests.fake_session import FakeSession


@pytest.fixture(autouse=True)
def config_dir(monkeypatch, tmp_path):
    path = tmp_path / "config"
    monkeypatch.setenv("GTASK_CONFIG_DIR", str(path))
    return path


@pytest.fixture
def fake(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("gtask.cli.make_session", lambda: session)
    return session


@pytest.fixture
def run():
    runner = CliRunner()

    def _run(*args, input=None):
        return runner.invoke(app, list(args), input=input)

    return _run
