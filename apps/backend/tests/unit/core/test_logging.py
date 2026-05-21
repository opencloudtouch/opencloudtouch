"""Tests for structured logging configuration."""

import json
import logging
import sys
from pathlib import Path

import pytest

from opencloudtouch.core.logging import (
    CLUSTER_FILE_BACKUP_COUNT,
    CLUSTER_FILE_MAX_BYTES,
    CLUSTER_NAMES,
    NOISY_CLUSTERS,
    ClusterFileHandler,
    ContextFormatter,
    StructuredFormatter,
    _log_clusters,
    _resolve_cluster,
    get_clustered_log_entries,
    get_log_entries,
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


class TestClusteredRingBuffer:
    """Tests for the clustered log ring buffer."""

    @pytest.fixture(autouse=True)
    def _clear_clusters(self):
        for buf in _log_clusters.values():
            buf.clear()
        yield
        for buf in _log_clusters.values():
            buf.clear()

    def test_resolve_cluster_aiosqlite(self):
        assert _resolve_cluster("aiosqlite") == "database"

    def test_resolve_cluster_bosesoundtouchapi(self):
        assert _resolve_cluster("bosesoundtouchapi.soundtouchdevice") == "bose_api"

    def test_resolve_cluster_devices(self):
        assert _resolve_cluster("opencloudtouch.devices.adapter") == "devices"
        assert _resolve_cluster("opencloudtouch.devices.discovery.ssdp") == "devices"

    def test_resolve_cluster_marge(self):
        assert _resolve_cluster("opencloudtouch.marge.routes") == "marge"

    def test_resolve_cluster_bmx(self):
        assert _resolve_cluster("opencloudtouch.bmx.routes") == "bmx"

    def test_resolve_cluster_setup(self):
        assert _resolve_cluster("opencloudtouch.setup.wizard_routes") == "setup"

    def test_resolve_cluster_presets(self):
        assert _resolve_cluster("opencloudtouch.presets.service") == "presets"

    def test_resolve_cluster_general_fallback(self):
        assert _resolve_cluster("opencloudtouch.core.config") == "general"
        assert _resolve_cluster("uvicorn") == "general"
        assert _resolve_cluster("unknown.logger") == "general"

    def test_get_clustered_log_entries_returns_all_clusters(self):
        result = get_clustered_log_entries()
        for name in CLUSTER_NAMES:
            assert name in result
            assert isinstance(result[name], list)

    def test_memory_handler_routes_to_correct_cluster(self):
        from opencloudtouch.core.logging import MemoryLogHandler

        handler = MemoryLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="opencloudtouch.marge.routes",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="UUID not found",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        assert len(_log_clusters["marge"]) == 1
        assert "UUID not found" in _log_clusters["marge"][0]
        assert len(_log_clusters["general"]) == 0

    def test_memory_handler_routes_aiosqlite_to_database(self):
        from opencloudtouch.core.logging import MemoryLogHandler

        handler = MemoryLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="aiosqlite",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="SELECT * FROM devices",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        assert len(_log_clusters["database"]) == 1
        assert len(_log_clusters["general"]) == 0

    def test_get_log_entries_merges_all_clusters_sorted(self):
        _log_clusters["marge"].append("2025-01-01 10:00:01 - WARNING - marge msg")
        _log_clusters["general"].append("2025-01-01 10:00:00 - INFO - general msg")
        _log_clusters["bmx"].append("2025-01-01 10:00:02 - INFO - bmx msg")

        merged = get_log_entries()
        assert len(merged) == 3
        assert "general msg" in merged[0]
        assert "marge msg" in merged[1]
        assert "bmx msg" in merged[2]


class TestClusterFileHandler:
    """Tests for persistent per-cluster log files with rotation."""

    LOGGER_FOR_CLUSTER = {
        "database": "aiosqlite",
        "bose_api": "bosesoundtouchapi.soundtouchdevice",
        "devices": "opencloudtouch.devices.adapter",
        "marge": "opencloudtouch.marge.routes",
        "bmx": "opencloudtouch.bmx.routes",
        "setup": "opencloudtouch.setup.wizard_routes",
        "presets": "opencloudtouch.presets.service",
        "general": "opencloudtouch.core.config",
    }

    def _make_record(self, logger_name: str, level: int, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name=logger_name,
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_creates_log_files_for_all_clusters(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            for cluster, logger_name in self.LOGGER_FOR_CLUSTER.items():
                level = logging.WARNING if cluster in NOISY_CLUSTERS else logging.INFO
                handler.emit(self._make_record(logger_name, level, f"test {cluster}"))

            for cluster_name in CLUSTER_NAMES:
                log_file = tmp_path / f"{cluster_name}.log"
                assert log_file.exists(), f"{cluster_name}.log not created"
                content = log_file.read_text(encoding="utf-8")
                assert f"test {cluster_name}" in content
        finally:
            handler.close()

    def test_noisy_clusters_filter_debug_and_info(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            for noisy_cluster in NOISY_CLUSTERS:
                logger_name = self.LOGGER_FOR_CLUSTER[noisy_cluster]

                handler.emit(
                    self._make_record(logger_name, logging.DEBUG, "debug-noise")
                )
                handler.emit(self._make_record(logger_name, logging.INFO, "info-noise"))
                handler.emit(
                    self._make_record(logger_name, logging.WARNING, "warning-kept")
                )
                handler.emit(
                    self._make_record(logger_name, logging.ERROR, "error-kept")
                )

                log_file = tmp_path / f"{noisy_cluster}.log"
                content = log_file.read_text(encoding="utf-8")
                assert "debug-noise" not in content
                assert "info-noise" not in content
                assert "warning-kept" in content
                assert "error-kept" in content
        finally:
            handler.close()

    def test_non_noisy_clusters_log_all_levels(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            for cluster_name in CLUSTER_NAMES:
                if cluster_name in NOISY_CLUSTERS:
                    continue
                logger_name = self.LOGGER_FOR_CLUSTER[cluster_name]
                handler.emit(self._make_record(logger_name, logging.DEBUG, "debug-ok"))
                handler.emit(self._make_record(logger_name, logging.INFO, "info-ok"))

                content = (tmp_path / f"{cluster_name}.log").read_text(encoding="utf-8")
                assert "debug-ok" in content
                assert "info-ok" in content
        finally:
            handler.close()

    def test_rotation_creates_backup_files(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            logger_name = "opencloudtouch.marge.routes"
            msg = "X" * 200
            writes_needed = (CLUSTER_FILE_MAX_BYTES // 200) * 3
            for _ in range(writes_needed):
                handler.emit(self._make_record(logger_name, logging.INFO, msg))

            main_file = tmp_path / "marge.log"
            backup1 = tmp_path / "marge.log.1"
            backup2 = tmp_path / "marge.log.2"

            assert main_file.exists()
            assert backup1.exists(), "First backup not created after rotation"
            assert backup2.exists(), "Second backup not created after rotation"
        finally:
            handler.close()

    def test_max_disk_footprint_per_cluster(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            for cluster_name in CLUSTER_NAMES:
                logger_name = self.LOGGER_FOR_CLUSTER[cluster_name]
                level = (
                    logging.WARNING if cluster_name in NOISY_CLUSTERS else logging.INFO
                )
                msg = "M" * 200

                writes = (CLUSTER_FILE_MAX_BYTES // 200) * (
                    CLUSTER_FILE_BACKUP_COUNT + 2
                )
                for _ in range(writes):
                    handler.emit(self._make_record(logger_name, level, msg))

                total_size = 0
                for f in tmp_path.glob(f"{cluster_name}.log*"):
                    total_size += f.stat().st_size

                max_allowed = CLUSTER_FILE_MAX_BYTES * (CLUSTER_FILE_BACKUP_COUNT + 1)
                assert total_size <= max_allowed * 1.1, (
                    f"Cluster '{cluster_name}' disk usage {total_size} bytes "
                    f"exceeds max {max_allowed} bytes (with 10% tolerance)"
                )
        finally:
            handler.close()

    def test_total_disk_footprint_across_all_clusters(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            for cluster_name in CLUSTER_NAMES:
                logger_name = self.LOGGER_FOR_CLUSTER[cluster_name]
                level = (
                    logging.WARNING if cluster_name in NOISY_CLUSTERS else logging.INFO
                )
                msg = "F" * 200

                writes = (CLUSTER_FILE_MAX_BYTES // 200) * (
                    CLUSTER_FILE_BACKUP_COUNT + 2
                )
                for _ in range(writes):
                    handler.emit(self._make_record(logger_name, level, msg))

            total_size = sum(f.stat().st_size for f in tmp_path.glob("*.log*"))
            max_total = (
                CLUSTER_FILE_MAX_BYTES
                * (CLUSTER_FILE_BACKUP_COUNT + 1)
                * len(CLUSTER_NAMES)
            )
            assert total_size <= max_total * 1.1, (
                f"Total disk footprint {total_size} bytes exceeds "
                f"theoretical max {max_total} bytes (with 10% tolerance)"
            )
        finally:
            handler.close()

    def test_rotation_preserves_old_content_in_backups(self, tmp_path: Path):
        handler = ClusterFileHandler(tmp_path, base_level=logging.DEBUG)
        try:
            logger_name = "opencloudtouch.setup.wizard_routes"
            marker = "MARKER_EARLY_LOG_ENTRY"
            handler.emit(self._make_record(logger_name, logging.INFO, marker))

            msg = "P" * 200
            writes = (CLUSTER_FILE_MAX_BYTES // 200) * 2
            for _ in range(writes):
                handler.emit(self._make_record(logger_name, logging.INFO, msg))

            all_content = ""
            for f in tmp_path.glob("setup.log*"):
                all_content += f.read_text(encoding="utf-8")

            assert marker in all_content, "Early log entry lost after rotation"
        finally:
            handler.close()

    def test_setup_logging_creates_cluster_files_when_log_dir_set(
        self, tmp_path: Path, monkeypatch
    ):
        from opencloudtouch.core.config import AppConfig

        log_dir = tmp_path / "logs"
        mock_config = AppConfig(
            log_level="DEBUG", log_format="text", log_file=None, log_dir=str(log_dir)
        )
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        setup_logging()

        test_logger = logging.getLogger("opencloudtouch.marge.test")
        test_logger.warning("persistent test warning")

        marge_log = log_dir / "marge.log"
        assert marge_log.exists()
        assert "persistent test warning" in marge_log.read_text(encoding="utf-8")

        root = logging.getLogger()
        for h in root.handlers[:]:
            if isinstance(h, ClusterFileHandler):
                h.close()
                root.removeHandler(h)

    def test_no_cluster_files_when_log_dir_not_set(self, monkeypatch):
        from opencloudtouch.core.config import AppConfig

        mock_config = AppConfig(
            log_level="INFO", log_format="text", log_file=None, log_dir=None
        )
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        setup_logging()

        root = logging.getLogger()
        cluster_handlers = [
            h for h in root.handlers if isinstance(h, ClusterFileHandler)
        ]
        assert len(cluster_handlers) == 0

    def test_permission_error_falls_back_to_ram_only(self, tmp_path: Path, monkeypatch):
        """Log dir with bad permissions degrades gracefully instead of crashing."""
        from opencloudtouch.core.config import AppConfig

        log_dir = tmp_path / "no-access"
        log_dir.mkdir()
        mock_config = AppConfig(
            log_level="INFO", log_format="text", log_file=None, log_dir=str(log_dir)
        )
        monkeypatch.setattr(
            "opencloudtouch.core.logging.get_config", lambda: mock_config
        )

        def raise_permission_error(self, *args, **kwargs):
            raise PermissionError("Permission denied: '/logs/database.log'")

        monkeypatch.setattr(
            "opencloudtouch.core.logging.ClusterFileHandler.__init__",
            raise_permission_error,
        )

        # Must not crash
        setup_logging()

        root = logging.getLogger()
        cluster_handlers = [
            h for h in root.handlers if isinstance(h, ClusterFileHandler)
        ]
        assert len(cluster_handlers) == 0
