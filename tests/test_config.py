from pathlib import Path

from gtask import config


def test_config_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("GTASK_CONFIG_DIR", str(tmp_path / "custom"))
    assert config.config_dir() == tmp_path / "custom"
    assert config.client_secret_path() == tmp_path / "custom" / "client_secret.json"
    assert config.token_path() == tmp_path / "custom" / "token.json"
    assert config.config_path() == tmp_path / "custom" / "config.toml"


def test_config_dir_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("GTASK_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_dir() == tmp_path / "xdg" / "gtask"


def test_config_dir_home_default(monkeypatch):
    monkeypatch.delenv("GTASK_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config.config_dir() == Path.home() / ".config" / "gtask"


def test_load_missing_config_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("GTASK_CONFIG_DIR", str(tmp_path))
    assert config.load_config() == {}
    assert config.get_default_list() is None


def test_set_and_get_default_list_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("GTASK_CONFIG_DIR", str(tmp_path / "new"))
    config.set_default_list('MTIz"quoted"')
    assert (tmp_path / "new" / "config.toml").exists()
    assert config.get_default_list() == 'MTIz"quoted"'
    assert config.load_config() == {"default_list": 'MTIz"quoted"'}
