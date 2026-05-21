"""
Structured logging configuration for OpenCloudTouch
Provides consistent logging format with context enrichment
"""

import collections
import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from opencloudtouch.core.config import get_config

# ---------------------------------------------------------------------------
# Clustered ring buffer: each category gets its own 1000-entry deque.
# This prevents noisy loggers (aiosqlite, bosesoundtouchapi) from
# pushing diagnostic entries (marge, bmx, setup) out of the buffer.
# 8 clusters × 1000 entries × ~214 bytes ≈ 1.7 MB RAM — fine for Pi.
# ---------------------------------------------------------------------------

CLUSTER_ENTRIES_PER_BUFFER = 1000

CLUSTER_RULES: list[tuple[str, str]] = [
    ("aiosqlite", "database"),
    ("bosesoundtouchapi", "bose_api"),
    ("opencloudtouch.devices", "devices"),
    ("opencloudtouch.marge", "marge"),
    ("opencloudtouch.bmx", "bmx"),
    ("opencloudtouch.setup", "setup"),
    ("opencloudtouch.presets", "presets"),
]
CLUSTER_DEFAULT = "general"

CLUSTER_NAMES: list[str] = [rule[1] for rule in CLUSTER_RULES] + [CLUSTER_DEFAULT]

# ---------------------------------------------------------------------------
# Persistent cluster log files (opt-in via OCT_LOG_DIR)
# RotatingFileHandler per cluster: maxBytes + backupCount
# Noisy clusters (database, bose_api) only log WARNING+ to disk.
# Max disk footprint: 8 × 500KB × 3 files = 12 MB
# ---------------------------------------------------------------------------

CLUSTER_FILE_MAX_BYTES = 512_000  # 500 KB per file
CLUSTER_FILE_BACKUP_COUNT = 2  # .log + .log.1 + .log.2 = 3 files per cluster

NOISY_CLUSTERS = frozenset({"database", "bose_api"})

_log_clusters: Dict[str, collections.deque[str]] = {
    name: collections.deque(maxlen=CLUSTER_ENTRIES_PER_BUFFER) for name in CLUSTER_NAMES
}

_persistent_log_dir: Optional[Path] = None


def _resolve_cluster(logger_name: str) -> str:
    for prefix, cluster in CLUSTER_RULES:
        if logger_name.startswith(prefix):
            return cluster
    return CLUSTER_DEFAULT


def get_log_entries() -> List[str]:
    """Return all log entries merged across clusters (backward-compatible)."""
    merged: list[str] = []
    for entries in _log_clusters.values():
        merged.extend(entries)
    merged.sort()
    return merged


def get_clustered_log_entries() -> Dict[str, List[str]]:
    """Return a snapshot of each cluster's ring buffer."""
    return {name: list(entries) for name, entries in _log_clusters.items()}


def get_persistent_log_dir() -> Optional[Path]:
    """Return the persistent log directory if configured, else None."""
    return _persistent_log_dir


class ClusterFileHandler(logging.Handler):
    """Routes log records to per-cluster RotatingFileHandlers on disk.

    Noisy clusters (database, bose_api) only accept WARNING+ to avoid
    SD card wear. All other clusters log at the configured level.
    """

    def __init__(self, log_dir: Path, base_level: int) -> None:
        super().__init__(level=base_level)
        self._handlers: Dict[str, RotatingFileHandler] = {}
        self._noisy_level = logging.WARNING
        log_dir.mkdir(parents=True, exist_ok=True)

        formatter = ContextFormatter(
            fmt="%(asctime)s - %(levelname)-8s - %(name)-30s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        for cluster_name in CLUSTER_NAMES:
            file_path = log_dir / f"{cluster_name}.log"
            rh = RotatingFileHandler(
                str(file_path),
                maxBytes=CLUSTER_FILE_MAX_BYTES,
                backupCount=CLUSTER_FILE_BACKUP_COUNT,
                encoding="utf-8",
            )
            rh.setFormatter(formatter)
            self._handlers[cluster_name] = rh

    def emit(self, record: logging.LogRecord) -> None:
        try:
            cluster = _resolve_cluster(record.name)
            if cluster in NOISY_CLUSTERS and record.levelno < self._noisy_level:
                return
            handler = self._handlers.get(cluster)
            if handler:
                handler.emit(record)
        except Exception:  # pragma: no cover
            self.handleError(record)

    def close(self) -> None:
        for handler in self._handlers.values():
            handler.close()
        super().close()


class MemoryLogHandler(logging.Handler):
    """Logging handler that routes records into category-specific ring buffers."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            cluster = _resolve_cluster(record.name)
            _log_clusters[cluster].append(self.format(record))
        except Exception:  # pragma: no cover
            self.handleError(record)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (correlation IDs, user context, etc.)
        if hasattr(record, "extra"):
            log_data["context"] = record.extra

        return json.dumps(log_data)


class ContextFormatter(logging.Formatter):
    """Text formatter with colored output and context."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and context."""
        # Add color to level name
        if sys.stderr.isatty():  # Only colorize if output is a terminal
            levelname = (
                f"{self.COLORS.get(record.levelname, '')}{record.levelname}{self.RESET}"
            )
        else:
            levelname = record.levelname

        # Base format: timestamp - level - logger - message
        formatted = f"{self.formatTime(record)} - {levelname:8} - {record.name:30} - {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logging() -> None:
    """Configure application-wide logging."""
    global _persistent_log_dir
    config = get_config()

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(config.log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.log_level)

    # Select formatter based on config
    if config.log_format == "json":
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(
            ContextFormatter(
                fmt="%(asctime)s - %(levelname)-8s - %(name)-30s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # In-memory ring buffer handler (always active, used by /api/logs/backend)
    memory_handler = MemoryLogHandler()
    memory_handler.setLevel(config.log_level)
    memory_handler.setFormatter(
        ContextFormatter(
            fmt="%(asctime)s - %(levelname)-8s - %(name)-30s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(memory_handler)

    # Persistent cluster log files (opt-in via OCT_LOG_DIR)
    if config.log_dir:
        log_dir = Path(config.log_dir)
        try:
            cluster_handler = ClusterFileHandler(
                log_dir, base_level=getattr(logging, config.log_level, logging.INFO)
            )
            root_logger.addHandler(cluster_handler)
            _persistent_log_dir = log_dir
        except PermissionError:
            logging.warning(
                f"Cannot write to log directory {log_dir} (permission denied). "
                "Falling back to RAM-only logging. Fix volume permissions: "
                "chown -R 1000:1000 <volume-mount-path>"
            )

    # Optional single file handler (legacy)
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(config.log_level)
        file_handler.setFormatter(StructuredFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info(
        f"Logging configured: level={config.log_level}, format={config.log_format}"
        + (f", log_dir={config.log_dir}" if config.log_dir else "")
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """Change the log level at runtime for all handlers.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    numeric = getattr(logging, level.upper(), None)
    if numeric is None:
        raise ValueError(f"Invalid log level: {level}")

    root = logging.getLogger()
    root.setLevel(numeric)
    for handler in root.handlers:
        handler.setLevel(numeric)

    logging.info("Log level changed to %s", level.upper())


def get_current_log_level() -> str:
    """Return the current effective log level as uppercase string."""
    return logging.getLevelName(logging.getLogger().level)
