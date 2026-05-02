"""
Structured logging configuration for OpenCloudTouch
Provides consistent logging format with context enrichment
"""

import collections
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Dict, List

from opencloudtouch.core.config import get_config

# In-memory ring buffer: keeps the last 500 formatted log entries
_log_buffer: collections.deque[str] = collections.deque(maxlen=500)


def get_log_entries() -> List[str]:
    """Return a snapshot of the in-memory log buffer."""
    return list(_log_buffer)


class MemoryLogHandler(logging.Handler):
    """Logging handler that stores records in the module-level ring buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _log_buffer.append(self.format(record))
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

    # Optional file handler
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
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
