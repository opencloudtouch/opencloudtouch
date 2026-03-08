"""Tests for structured logging configuration."""

import json
import logging
import sys

from opencloudtouch.core.logging import (
    ContextFormatter,
    StructuredFormatter,
    get_logger,
    setup_logging,
)


class TestStructuredFormatter:
    """Tests for StructuredFormatter (JSON logging)."""

    def test_basic_log_record(self):
        """Test JSON formatter with basic log record.

        Arrange: Create formatter and basic log record
        Act: Format the record
        Assert: Output is valid JSON with expected fields
        """
        # Arrange
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Act
        output = formatter.format(record)
        data = json.loads(output)

        # Assert
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert "timestamp" in data

    def test_log_record_with_exception(self):
        """Test JSON formatter with exception info.

        Arrange: Create formatter and record with exception
        Act: Format the record
        Assert: Exception details are included in JSON
        """
        # Arrange
        formatter = StructuredFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=100,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        # Act
        output = formatter.format(record)
        data = json.loads(output)

        # Assert
        assert data["message"] == "Error occurred"
        assert "exception" in data
        assert "ValueError: Test error" in data["exception"]


class TestContextFormatter:
    """Tests for ContextFormatter (colored text logging)."""

    def test_basic_log_record(self):
        """Test colored text formatter with basic record.

        Arrange: Create formatter and basic log record
        Act: Format the record
        Assert: Output contains message, level, logger name
        """
        # Arrange
        formatter = ContextFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Act
        output = formatter.format(record)

        # Assert
        assert "Test message" in output
        assert "test.module" in output
        assert "INFO" in output

    def test_log_record_with_exception(self):
        """Test colored formatter with exception info.

        Arrange: Create formatter and record with exception
        Act: Format the record
        Assert: Exception traceback is included
        """
        # Arrange
        formatter = ContextFormatter()

        try:
            raise RuntimeError("Test runtime error")
        except RuntimeError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="backend.api",
            level=logging.ERROR,
            pathname="/path/to/api.py",
            lineno=200,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        # Act
        output = formatter.format(record)

        # Assert
        assert "Error occurred" in output
        assert "RuntimeError: Test runtime error" in output


class TestLoggingSetup:
    """Tests for setup_logging() configuration."""

    def test_default_configuration(self, monkeypatch, tmp_path):
        """Test logging setup with default config.

        Arrange: Mock config with default text logging
        Act: Call setup_logging()
        Assert: Root logger configured with INFO level
        """
        # Arrange
        from opencloudtouch.core.config import AppConfig

        mock_config = AppConfig(log_level="INFO", log_format="text", log_file=None)
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        # Act
        setup_logging()

        # Assert
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 1

    def test_json_format_configuration(self, monkeypatch):
        """Test logging setup with JSON format.

        Arrange: Mock config with JSON format
        Act: Call setup_logging()
        Assert: Console handler uses StructuredFormatter
        """
        # Arrange
        from opencloudtouch.core.config import AppConfig

        mock_config = AppConfig(log_level="DEBUG", log_format="json", log_file=None)
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        # Act
        setup_logging()

        # Assert
        root_logger = logging.getLogger()
        console_handler = root_logger.handlers[0]
        assert isinstance(console_handler.formatter, StructuredFormatter)

    def test_file_logging_configuration(self, monkeypatch, tmp_path):
        """Test logging setup with file logging.

        Arrange: Mock config with log file path
        Act: Call setup_logging() and write log message
        Assert: Log file created and contains message
        """
        # Arrange
        log_file = tmp_path / "test.log"

        from opencloudtouch.core.config import AppConfig

        mock_config = AppConfig(
            log_level="WARNING", log_format="text", log_file=str(log_file)
        )
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        # Act
        setup_logging()
        test_logger = logging.getLogger("test.file")
        test_logger.warning("Test warning message")

        # Assert
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test warning message" in content

        # Cleanup: Remove file handler only (keep console handlers for pytest)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                root_logger.removeHandler(handler)

    def test_third_party_logger_silencing(self, monkeypatch):
        """Test that noisy third-party loggers are silenced.

        Arrange: Mock config with DEBUG level
        Act: Call setup_logging()
        Assert: Third-party loggers set to WARNING
        """
        # Arrange
        from opencloudtouch.core.config import AppConfig

        mock_config = AppConfig(log_level="DEBUG", log_format="text", log_file=None)
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        # Act
        setup_logging()

        # Assert
        assert logging.getLogger("urllib3").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING


class TestGetLogger:
    """Tests for get_logger() utility function."""

    def test_returns_logger_with_correOCT_name(self):
        """Test get_logger returns logger with specified name.

        Arrange: -
        Act: Call get_logger with name
        Assert: Returns Logger instance with correct name
        """
        # Act
        logger = get_logger("test.logger")

        # Assert
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger"
