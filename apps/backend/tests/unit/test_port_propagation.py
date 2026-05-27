"""Regression tests for #268: OCT_PORT must propagate to all generated URLs.

When deploying with OCT_PORT=8080, all URLs written to device configs,
returned by APIs, and used as fallbacks MUST use port 8080 — not 7777.
"""

from opencloudtouch.core.config import DEFAULT_PORT, AppConfig, clear_config
from opencloudtouch.setup.config_service import SoundTouchConfigService


class TestDefaultPortConstant:
    """DEFAULT_PORT is the single source of truth for the default port."""

    def test_default_port_value(self):
        assert DEFAULT_PORT == 7777

    def test_app_config_uses_default_port(self):
        config = AppConfig(_env_file=None)
        assert config.port == DEFAULT_PORT


class TestConfigPortPropagation:
    """station_descriptor_base_url respects OCT_PORT."""

    def test_base_url_uses_custom_port(self, monkeypatch):
        monkeypatch.delenv("OCT_STATION_DESCRIPTOR_BASE_URL", raising=False)
        monkeypatch.setenv("OCT_PORT", "8080")
        config = AppConfig(_env_file=None)
        # The model_validator replaces localhost with content.api.bose.io
        assert ":8080" in config.station_descriptor_base_url
        assert ":7777" not in config.station_descriptor_base_url

    def test_base_url_default_port(self, monkeypatch):
        monkeypatch.delenv("OCT_STATION_DESCRIPTOR_BASE_URL", raising=False)
        monkeypatch.delenv("OCT_PORT", raising=False)
        config = AppConfig(_env_file=None)
        assert f":{DEFAULT_PORT}" in config.station_descriptor_base_url

    def test_base_url_explicit_override_preserved(self, monkeypatch):
        """If user sets OCT_STATION_DESCRIPTOR_BASE_URL explicitly, use it."""
        monkeypatch.setenv(
            "OCT_STATION_DESCRIPTOR_BASE_URL", "http://myserver.local:9999"
        )
        config = AppConfig(_env_file=None)
        assert ":9999" in config.station_descriptor_base_url

    def test_localhost_replacement_uses_self_port(self, monkeypatch):
        """_replace_localhost_in_base_url must use self.port, not hardcoded 7777."""
        monkeypatch.setenv("OCT_PORT", "8080")
        monkeypatch.setenv("OCT_STATION_DESCRIPTOR_BASE_URL", "http://localhost")
        config = AppConfig(_env_file=None)
        # localhost replaced with content.api.bose.io, port from self.port
        assert ":8080" in config.station_descriptor_base_url


class TestConfigServiceUrlBuilders:
    """build_*_url methods use DEFAULT_PORT as default, accept custom port."""

    def test_bmx_url_default_port(self):
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50")
        assert f":{DEFAULT_PORT}/" in url

    def test_bmx_url_custom_port(self):
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50", port=8080)
        assert ":8080/" in url
        assert ":7777" not in url

    def test_marge_url_custom_port(self):
        url = SoundTouchConfigService.build_marge_url("x", port=8080)
        assert ":8080" in url
        assert ":7777" not in url

    def test_swupdate_url_custom_port(self):
        url = SoundTouchConfigService.build_swupdate_url("x", port=8080)
        assert ":8080/" in url
        assert ":7777" not in url

    def test_stats_url_custom_port(self):
        url = SoundTouchConfigService.build_stats_url("x", port=8080)
        assert ":8080" in url
        assert ":7777" not in url

    def test_all_builders_consistent_port(self):
        """All 4 URL builders must use the same custom port."""
        port = 9090
        urls = [
            SoundTouchConfigService.build_bmx_url("x", port=port),
            SoundTouchConfigService.build_marge_url("x", port=port),
            SoundTouchConfigService.build_swupdate_url("x", port=port),
            SoundTouchConfigService.build_stats_url("x", port=port),
        ]
        for url in urls:
            assert f":{port}" in url, f"Port {port} missing in {url}"
            assert ":7777" not in url, f"Hardcoded 7777 found in {url}"


class TestResolveRoutesFallback:
    """OCT_BACKEND_URL fallback must use configured port."""

    def test_fallback_uses_config_port(self, monkeypatch):
        monkeypatch.delenv("OCT_BACKEND_URL", raising=False)
        monkeypatch.setenv("OCT_PORT", "8080")
        clear_config()
        try:
            from opencloudtouch.bmx.resolve_routes import _build_oct_resolved_xml

            xml = _build_oct_resolved_xml(
                "/oct/device/AABBCCDD/preset/1", "TestStation", "Test"
            )
            assert xml is not None
            assert ":8080/" in xml
            assert ":7777" not in xml
        finally:
            monkeypatch.delenv("OCT_PORT", raising=False)
            clear_config()

    def test_explicit_env_var_honored(self, monkeypatch):
        monkeypatch.setenv("OCT_BACKEND_URL", "http://content.api.bose.io:9999")
        clear_config()
        try:
            from opencloudtouch.bmx.resolve_routes import _build_oct_resolved_xml

            xml = _build_oct_resolved_xml(
                "/oct/device/AABBCCDD/preset/1", "TestStation", "Test"
            )
            assert xml is not None
            assert ":9999/" in xml
        finally:
            monkeypatch.delenv("OCT_BACKEND_URL", raising=False)
            clear_config()


class TestCorsValidatorPort:
    """_ensure_cors_includes_port adds port-specific origin when needed."""

    def test_custom_port_added_to_cors(self, monkeypatch):
        """OCT_PORT=8080 → http://localhost:8080 must appear in cors_origins."""
        monkeypatch.setenv("OCT_PORT", "8080")
        config = AppConfig(_env_file=None)
        assert "http://localhost:8080" in config.cors_origins

    def test_default_port_no_duplication(self, monkeypatch):
        """OCT_PORT=7777 (default) → no duplicate http://localhost:7777."""
        monkeypatch.delenv("OCT_PORT", raising=False)
        config = AppConfig(_env_file=None)
        count = config.cors_origins.count(f"http://localhost:{DEFAULT_PORT}")
        assert count == 1, f"Expected exactly 1 entry, got {count}"

    def test_wildcard_cors_skips_validator(self, monkeypatch):
        """cors_origins=['*'] → validator returns early, no modification."""
        monkeypatch.setenv("OCT_CORS_ORIGINS", '["*"]')
        config = AppConfig(_env_file=None)
        assert config.cors_origins == ["*"]


class TestTuneInFallback:
    """get_oct_base_url fallback must use configured port."""

    def test_fallback_uses_config_port(self, monkeypatch):
        monkeypatch.delenv("OCT_BACKEND_URL", raising=False)
        monkeypatch.setenv("OCT_PORT", "8080")
        clear_config()
        try:
            from opencloudtouch.bmx.tunein import get_oct_base_url

            url = get_oct_base_url()
            assert ":8080" in url
            assert ":7777" not in url
        finally:
            monkeypatch.delenv("OCT_PORT", raising=False)
            clear_config()

    def test_explicit_env_var_honored(self, monkeypatch):
        """OCT_BACKEND_URL set explicitly → used as-is."""
        monkeypatch.setenv("OCT_BACKEND_URL", "http://myproxy.local:9999")
        clear_config()
        try:
            from opencloudtouch.bmx.tunein import get_oct_base_url

            url = get_oct_base_url()
            assert url == "http://myproxy.local:9999"
        finally:
            monkeypatch.delenv("OCT_BACKEND_URL", raising=False)
            clear_config()


class TestApiModelsNormalization:
    """_normalize_target_addr default port must use DEFAULT_PORT."""

    def test_hostname_without_port_uses_default(self):
        from opencloudtouch.setup.api_models import _normalize_target_addr

        result = _normalize_target_addr("oct.local")
        assert f":{DEFAULT_PORT}" in result

    def test_hostname_with_custom_port_preserved(self):
        from opencloudtouch.setup.api_models import _normalize_target_addr

        result = _normalize_target_addr("oct.local:8080")
        assert ":8080" in result
        assert ":7777" not in result
