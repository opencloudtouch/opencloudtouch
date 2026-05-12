"""
Unit tests for configuration module
"""

import os
from pathlib import Path

import pytest

from opencloudtouch.core.config import AppConfig, clear_config, init_config


def test_config_defaults(monkeypatch):
    """Test default configuration values."""
    # Remove ALL OCT_ env vars to test production defaults
    for key in list(os.environ.keys()):
        if key.startswith("OCT_") or key == "CI":
            monkeypatch.delenv(key, raising=False)

    # Create config without reading .env file
    config = AppConfig(_env_file=None)

    assert config.host == "0.0.0.0"
    assert config.port == 7777
    assert config.log_level == "INFO"
    assert config.db_path == ""  # Empty by default
    assert config.effective_db_path == "/data/oct.db"  # Production default
    assert config.discovery_enabled is True
    assert config.discovery_timeout == 3  # Optimized for fast Bose discovery (<5s)
    assert config.manual_device_ips_list == []
    assert config.device_http_port == 8090
    assert config.device_ws_port == 8080


def test_config_log_level_validation():
    """Test log level validation."""
    # Valid log levels
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        config = AppConfig(log_level=level)
        assert config.log_level == level

    # Case insensitive
    config = AppConfig(log_level="info")
    assert config.log_level == "INFO"

    # Invalid log level
    with pytest.raises(ValueError):
        AppConfig(log_level="INVALID")


def test_config_env_prefix():
    """Test that ENV variables are recognized with OCT_ prefix."""

    # Set ENV variable
    os.environ["OCT_PORT"] = "9000"
    os.environ["OCT_LOG_LEVEL"] = "DEBUG"

    config = AppConfig()

    assert config.port == 9000
    assert config.log_level == "DEBUG"

    # Clean up
    del os.environ["OCT_PORT"]
    del os.environ["OCT_LOG_LEVEL"]


def test_config_init():
    """Test init_config function."""
    config = init_config()

    assert config is not None
    assert isinstance(config, AppConfig)


def test_config_yaml_loading():
    """Test loading config from YAML file."""
    import tempfile

    import yaml

    # Create temporary YAML config
    yaml_content = {
        "host": "127.0.0.1",
        "port": 9000,
        "log_level": "DEBUG",
        "db_path": "/tmp/test.db",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(yaml_content, f)
        yaml_path = Path(f.name)

    try:
        config = AppConfig.load_from_yaml(yaml_path)

        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.log_level == "DEBUG"
        assert config.db_path == "/tmp/test.db"
    finally:
        yaml_path.unlink()


def test_config_yaml_nonexistent():
    """Test loading config from nonexistent YAML file returns a valid config."""
    config = AppConfig.load_from_yaml(Path("/nonexistent/file.yaml"))

    # Should return a valid AppConfig instance (env vars may override defaults)
    assert isinstance(config, AppConfig)
    # Port should be a valid integer
    assert isinstance(config.port, int)
    assert config.port > 0


def test_get_config_returns_app_config():
    """get_config() returns an AppConfig instance without explicit init."""
    from opencloudtouch.core.config import get_config

    cfg = get_config()
    assert isinstance(cfg, AppConfig)


def test_get_config_returns_same_instance():
    """get_config() returns the same cached instance on repeated calls."""
    from opencloudtouch.core.config import get_config

    cfg1 = get_config()
    cfg2 = get_config()
    assert cfg1 is cfg2, "lru_cache must return the same object on repeated calls"


def test_clear_config_invalidates_cache(monkeypatch):
    """clear_config() forces a fresh AppConfig on next get_config() call (REFACT-013)."""
    from opencloudtouch.core.config import get_config

    cfg_before = get_config()

    # Clear and reload — fresh instance expected
    clear_config()
    cfg_after = get_config()

    # Both must be valid AppConfig instances
    assert isinstance(cfg_before, AppConfig)
    assert isinstance(cfg_after, AppConfig)
    # They are different objects (cache was invalidated)
    assert cfg_before is not cfg_after


def test_init_config_reloads_env_vars(monkeypatch):
    """init_config() picks up env-var changes after clear (REFACT-013 test isolation)."""
    from opencloudtouch.core.config import get_config

    # Ensure fresh state
    clear_config()

    monkeypatch.setenv("OCT_PORT", "9876")
    init_config()  # clears cache + re-initialises
    cfg = get_config()
    assert cfg.port == 9876, "init_config must pick up updated env vars"

    # Cleanup
    clear_config()


def test_effective_db_path_explicit():
    """Test effective_db_path returns explicit value when set."""
    config = AppConfig(db_path="/custom/path.db")
    assert config.effective_db_path == "/custom/path.db"


def test_effective_db_path_ci_mode(monkeypatch):
    """Test effective_db_path returns :memory: in CI."""
    monkeypatch.delenv("OCT_DB_PATH", raising=False)
    monkeypatch.setenv("CI", "true")
    config = AppConfig(_env_file=None)
    assert config.effective_db_path == ":memory:"


def test_effective_db_path_mock_mode(monkeypatch):
    """Test effective_db_path returns test DB in mock mode."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("OCT_DB_PATH", raising=False)
    config = AppConfig(mock_mode=True, _env_file=None)
    assert config.effective_db_path == "data-local/oct-test.db"


def test_effective_db_path_production(monkeypatch):
    """Test effective_db_path returns production path by default."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("OCT_MOCK_MODE", raising=False)
    monkeypatch.delenv("OCT_DB_PATH", raising=False)
    config = AppConfig(mock_mode=False, _env_file=None)
    assert config.effective_db_path == "/data/oct.db"


class TestLocalhostAutoDetection:
    """Tests for GitHub issue #43 / #167: localhost in preset URLs uses domain."""

    def test_localhost_replaced_with_domain(self, monkeypatch):
        """station_descriptor_base_url with localhost uses content.api.bose.io domain."""
        config = AppConfig(
            station_descriptor_base_url="http://localhost:7777", _env_file=None
        )
        assert config.station_descriptor_base_url == "http://content.api.bose.io:7777"

    def test_127_0_0_1_replaced_with_domain(self, monkeypatch):
        """station_descriptor_base_url with 127.0.0.1 uses content.api.bose.io domain."""
        config = AppConfig(
            station_descriptor_base_url="http://127.0.0.1:7777", _env_file=None
        )
        assert config.station_descriptor_base_url == "http://content.api.bose.io:7777"

    def test_explicit_ip_not_replaced(self, monkeypatch):
        """Explicitly configured IP is NOT replaced."""
        config = AppConfig(
            station_descriptor_base_url="http://192.168.1.50:7777", _env_file=None
        )
        assert config.station_descriptor_base_url == "http://192.168.1.50:7777"

    def test_hostname_not_replaced(self, monkeypatch):
        """content.api.bose.io hostname is NOT replaced."""
        config = AppConfig(
            station_descriptor_base_url="http://content.api.bose.io:7777",
            _env_file=None,
        )
        assert config.station_descriptor_base_url == "http://content.api.bose.io:7777"

    def test_default_value_uses_domain(self, monkeypatch):
        """Default value (localhost) is replaced with content.api.bose.io on startup."""
        monkeypatch.delenv("OCT_STATION_DESCRIPTOR_BASE_URL", raising=False)
        config = AppConfig(_env_file=None)
        assert config.station_descriptor_base_url == "http://content.api.bose.io:7777"
