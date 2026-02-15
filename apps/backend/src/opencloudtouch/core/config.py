"""
Zentrale Konfiguration für OpenCloudTouch.
Nutzt pydantic-settings für ENV + YAML Validierung.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration with ENV override and YAML support."""

    model_config = SettingsConfigDict(
        env_prefix="OCT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore deployment-related env vars (DEPLOY_*, CONTAINER_*, etc.)
    )

    # Server
    host: str = Field(default="0.0.0.0", description="API bind address")  # nosec B104
    port: int = Field(default=7777, description="API port")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="text", description="Log format: 'text' or 'json'")
    log_file: Optional[str] = Field(default=None, description="Optional log file path")

    # CORS
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:4173",  # Vite preview (E2E tests)
            "http://localhost:5173",  # Vite dev
            "http://localhost:7777",
        ],
        description="Allowed CORS origins (use ['*'] for development only)",
    )

    # Mock Mode
    mock_mode: bool = Field(
        default=False, description="Enable mock mode (for testing without real devices)"
    )

    # Database
    db_path: str = Field(
        default="", description="SQLite database path (auto-configured if empty)"
    )

    @property
    def effective_db_path(self) -> str:
        """
        Get effective database path based on environment.

        Priority:
        1. Explicit OCT_DB_PATH (if set)
        2. CI=true → ":memory:"
        3. OCT_MOCK_MODE=true → "data-local/oct-test.db"
        4. Production → "data/oct.db"
        """
        # Explicit override
        if self.db_path:
            return self.db_path

        # CI: Use in-memory DB
        if os.getenv("CI", "false").lower() == "true":
            return ":memory:"

        # Mock mode: Use test DB in data-local
        if self.mock_mode:
            return "data-local/oct-test.db"

        # Production: Use persistent DB in data/
        return "/data/oct.db"

    # Discovery
    discovery_enabled: bool = Field(
        default=True, description="Enable SSDP/UPnP discovery"
    )
    discovery_timeout: int = Field(default=5, description="Discovery timeout (seconds)")
    manual_device_ips: str = Field(
        default="", description="Comma-separated list of manual device IPs"
    )

    @property
    def manual_device_ips_list(self) -> list[str]:
        """Get manual IPs as list."""
        if not self.manual_device_ips:
            return []
        return [ip.strip() for ip in self.manual_device_ips.split(",") if ip.strip()]

    # Device Ports (Local HTTP/WebSocket API)
    device_http_port: int = Field(default=8090, description="Device HTTP API port")
    device_ws_port: int = Field(default=8080, description="Device WebSocket port")

    # Station Descriptor
    station_descriptor_base_url: str = Field(
        default="http://localhost:7777",
        description="Base URL for OCT backend (used in Bose preset programming)",
    )

    # Feature Toggles (9.3.6 - NICE TO HAVE)
    enable_hdmi_controls: bool = Field(
        default=True,
        description="Enable HDMI/CEC controls for ST300 (can be disabled if causing issues)",
    )
    enable_advanced_audio: bool = Field(
        default=True,
        description="Enable advanced audio controls (DSP, Tone, Level) for ST300",
    )
    enable_zone_management: bool = Field(
        default=True, description="Enable multi-room zone management"
    )
    enable_group_management: bool = Field(
        default=True, description="Enable group management features"
    )

    # Production Safety
    allow_dangerous_operations: bool = Field(
        default=False,
        description="Allow dangerous operations like DELETE /api/devices (testing only)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate and normalize log level.

        Args:
            v: Log level string (case-insensitive).

        Returns:
            Uppercase log level string.

        Raises:
            ValueError: If log level is not in allowed values.
        """
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v}")
        return v_upper

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate and normalize log format.

        Args:
            v: Log format string (case-insensitive).

        Returns:
            Lowercase log format string ('text' or 'json').

        Raises:
            ValueError: If log format is not in allowed values.
        """
        allowed = {"text", "json"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"log_format must be one of {allowed}, got {v}")
        return v_lower

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "AppConfig":
        """Load configuration from YAML file (optional overlay)."""
        if not yaml_path.exists():
            return cls()

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)


# Globale Config-Instanz
config: Optional[AppConfig] = None


def init_config(yaml_path: Optional[Path] = None) -> AppConfig:
    """Initialize global config instance."""
    global config
    if yaml_path and yaml_path.exists():
        config = AppConfig.load_from_yaml(yaml_path)
    else:
        config = AppConfig()
    return config


def get_config() -> AppConfig:
    """Get current config instance."""
    if config is None:
        raise RuntimeError("Config not initialized. Call init_config() first.")
    return config
