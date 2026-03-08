"""Unit tests for radio adapter factory function.

Covers the get_radio_adapter() factory and its OCT_MOCK_MODE env var branching.
"""

from opencloudtouch.radio.adapter import get_radio_adapter


class TestGetRadioAdapterFactory:
    """Tests for get_radio_adapter() factory function."""

    def test_default_mode_returns_radiobrowser_adapter(self):
        """Default mode (OCT_MOCK_MODE unset) returns RadioBrowserAdapter."""
        import os

        os.environ.pop("OCT_MOCK_MODE", None)

        from opencloudtouch.radio.providers.radiobrowser import RadioBrowserAdapter

        adapter = get_radio_adapter()
        assert isinstance(adapter, RadioBrowserAdapter)

    def test_mock_mode_true_returns_mock_adapter(self, monkeypatch):
        """OCT_MOCK_MODE=true returns MockRadioAdapter (lines 44-47)."""
        monkeypatch.setenv("OCT_MOCK_MODE", "true")

        from opencloudtouch.radio.providers.mock import MockRadioAdapter

        adapter = get_radio_adapter()
        assert isinstance(adapter, MockRadioAdapter)

    def test_mock_mode_uppercase_returns_mock_adapter(self, monkeypatch):
        """OCT_MOCK_MODE=TRUE (uppercase) is normalised to lowercase correctly."""
        monkeypatch.setenv("OCT_MOCK_MODE", "TRUE")

        from opencloudtouch.radio.providers.mock import MockRadioAdapter

        adapter = get_radio_adapter()
        assert isinstance(adapter, MockRadioAdapter)

    def test_mock_mode_false_returns_radiobrowser_adapter(self, monkeypatch):
        """OCT_MOCK_MODE=false explicitly returns RadioBrowserAdapter."""
        monkeypatch.setenv("OCT_MOCK_MODE", "false")

        from opencloudtouch.radio.providers.radiobrowser import RadioBrowserAdapter

        adapter = get_radio_adapter()
        assert isinstance(adapter, RadioBrowserAdapter)
