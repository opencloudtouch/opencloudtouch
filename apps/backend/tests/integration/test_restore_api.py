"""Integration tests for Restore Wizard API endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dependencies import get_restore_service
from opencloudtouch.main import app
from opencloudtouch.setup.restore_models import (
    BackupFileInfo,
    BackupScanResult,
    BackupSet,
    RestoreResult,
    RestoreStep,
    RestoreStepName,
    StepStatus,
)
from opencloudtouch.setup.restore_service import RestoreService


@pytest.fixture
def mock_restore_service():
    """Create a mock RestoreService with pre-configured responses."""
    return AsyncMock(spec=RestoreService)


class TestScanBackupsEndpoint:
    """T020: Integration tests for POST /api/setup/wizard/scan-backups."""

    @pytest.mark.asyncio
    async def test_scan_returns_matched_set(self, mock_restore_service):
        mock_restore_service.scan_backups.return_value = BackupScanResult(
            usb_mounted=True,
            selected_set=BackupSet(
                device_id="ABC123",
                backup_date="20260101",
                is_match=True,
                files=[
                    BackupFileInfo(
                        filename="soundtouch-ABC123-20260101-rootfs.tgz",
                        volume_type="rootfs",
                        file_path="/media/sda1/oct-backup/soundtouch-ABC123-20260101-rootfs.tgz",
                        device_id="ABC123",
                        backup_date="20260101",
                    )
                ],
            ),
        )

        async def override():
            return mock_restore_service

        app.dependency_overrides[get_restore_service] = override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/setup/wizard/scan-backups",
                    json={"device_ip": "192.168.1.100", "device_id": "ABC123"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["usb_mounted"] is True
            assert data["selected_set"]["device_id"] == "ABC123"
            assert len(data["selected_set"]["files"]) == 1
        finally:
            app.dependency_overrides.pop(get_restore_service, None)

    @pytest.mark.asyncio
    async def test_scan_no_usb(self, mock_restore_service):
        mock_restore_service.scan_backups.return_value = BackupScanResult(
            usb_mounted=False,
            error="USB stick not detected",
        )

        async def override():
            return mock_restore_service

        app.dependency_overrides[get_restore_service] = override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/setup/wizard/scan-backups",
                    json={"device_ip": "192.168.1.100", "device_id": "ABC123"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["usb_mounted"] is False
            assert "not detected" in data["error"]
        finally:
            app.dependency_overrides.pop(get_restore_service, None)


class TestRestoreWizardEndpoint:
    """T042: Integration tests for POST /api/setup/wizard/restore-wizard."""

    @pytest.mark.asyncio
    async def test_clean_restore_success(self, mock_restore_service):
        mock_restore_service.execute_restore.return_value = RestoreResult(
            success=True,
            restore_type="clean",
            total_duration_seconds=5.2,
            steps=[
                RestoreStep(
                    name=RestoreStepName.CONFIG,
                    status=StepStatus.COMPLETED,
                    message="Config files restored",
                    duration_seconds=2.0,
                ),
                RestoreStep(
                    name=RestoreStepName.HOSTS,
                    status=StepStatus.COMPLETED,
                    message="OCT block removed",
                    duration_seconds=1.0,
                ),
            ],
        )

        async def override():
            return mock_restore_service

        app.dependency_overrides[get_restore_service] = override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/setup/wizard/restore-wizard",
                    json={
                        "device_ip": "192.168.1.100",
                        "device_id": "ABC123",
                        "restore_type": "clean",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["steps"]) == 2
            assert data["steps"][0]["status"] == "completed"
        finally:
            app.dependency_overrides.pop(get_restore_service, None)

    @pytest.mark.asyncio
    async def test_restore_with_backup_set(self, mock_restore_service):
        mock_restore_service.execute_restore.return_value = RestoreResult(
            success=True,
            restore_type="backup",
            total_duration_seconds=8.0,
            steps=[
                RestoreStep(
                    name=RestoreStepName.CONFIG,
                    status=StepStatus.COMPLETED,
                    message="Config restored from backup",
                    duration_seconds=3.0,
                ),
            ],
        )

        async def override():
            return mock_restore_service

        app.dependency_overrides[get_restore_service] = override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/setup/wizard/restore-wizard",
                    json={
                        "device_ip": "192.168.1.100",
                        "device_id": "ABC123",
                        "restore_type": "backup",
                        "backup_set": {
                            "device_id": "ABC123",
                            "backup_date": "20260101",
                            "files": [
                                {
                                    "file_path": "/media/sda1/oct-backup/soundtouch-ABC123-20260101-rootfs.tgz",
                                    "volume_type": "rootfs",
                                }
                            ],
                        },
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.pop(get_restore_service, None)
