"""
Regression tests for Issue #184: ST20 III presets not working.
Date: 2026-05-12
Issue: https://github.com/opencloudtouch/opencloudtouch/issues/184
"""

from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree

import pytest

from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.marge.routes import streaming_full_account
from opencloudtouch.marge.service import MargeService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.repository import RecentsRepository


class TestBug184HardcodedDeviceIdInStreamingRoute:
    """BUG 1: streaming_full_account() used hardcoded device_id."""

    @pytest.mark.asyncio
    async def test_streaming_route_resolves_device_id_dynamically(self):
        """Verify streaming endpoint uses resolved device_id."""
        mock_preset = MagicMock()
        mock_preset.slot = 1
        mock_preset.source = "TUNEIN"
        mock_preset.location = "/v1/playback/station/s33828"
        mock_preset.name = "Test Radio"
        mock_preset.image_url = ""
        mock_preset.created_at.timestamp.return_value = 1234567890
        mock_preset.updated_at.timestamp.return_value = 1234567890
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(
            return_value="F4E11EA01FE6"
        )
        mock_marge.get_full_account = AsyncMock(return_value=([mock_preset], []))
        await streaming_full_account("3784726", mock_marge)
        mock_marge.resolve_device_id_for_account.assert_called_once_with("3784726")
        mock_marge.get_full_account.assert_called_once_with("F4E11EA01FE6")

    @pytest.mark.asyncio
    async def test_streaming_route_returns_empty_when_no_device_mapped(self):
        """Verify streaming endpoint returns empty presets when no mapping."""
        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(return_value=None)
        result = await streaming_full_account("9999999", mock_marge)
        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        presets = root.find("presets")
        assert presets is not None
        assert len(presets.findall("preset")) == 0
        mock_marge.get_full_account.assert_not_called()


class TestBug184AccountIdToDeviceIdMapping:
    """BUG 3: No account_id to device_id mapping in the database."""

    @pytest.mark.asyncio
    async def test_device_model_has_marge_account_uuid(self):
        """Verify Device model includes marge_account_uuid field."""
        device = Device(
            device_id="F4E11EA01FE6",
            ip="192.168.1.100",
            name="Test Speaker",
            model="SoundTouch 20",
            mac_address="F4E11EA01FE6",
            firmware_version="27.0.6.46330",
            marge_account_uuid="3784726",
        )
        assert device.marge_account_uuid == "3784726"

    @pytest.mark.asyncio
    async def test_device_model_marge_account_uuid_defaults_none(self):
        """Verify marge_account_uuid defaults to None."""
        device = Device(
            device_id="F4E11EA01FE6",
            ip="192.168.1.100",
            name="Test Speaker",
            model="SoundTouch 20",
            mac_address="F4E11EA01FE6",
            firmware_version="27.0.6.46330",
        )
        assert device.marge_account_uuid is None

    @pytest.mark.asyncio
    async def test_device_to_dict_includes_marge_account_uuid(self):
        """Verify to_dict() exports marge_account_uuid."""
        device = Device(
            device_id="F4E11EA01FE6",
            ip="192.168.1.100",
            name="Test Speaker",
            model="SoundTouch 20",
            mac_address="F4E11EA01FE6",
            firmware_version="27.0.6.46330",
            marge_account_uuid="3784726",
        )
        d = device.to_dict()
        assert "marge_account_uuid" in d
        assert d["marge_account_uuid"] == "3784726"

    @pytest.mark.asyncio
    async def test_resolve_device_id_for_account_uses_repo(self):
        """Verify MargeService resolves account_id via device repository."""
        mock_device = MagicMock()
        mock_device.device_id = "F4E11EA01FE6"
        mock_device.name = "Test ST20"
        mock_device_repo = AsyncMock(spec=DeviceRepository)
        mock_device_repo.get_by_account_uuid = AsyncMock(return_value=mock_device)
        mock_preset_repo = AsyncMock(spec=PresetRepository)
        mock_recents_repo = AsyncMock(spec=RecentsRepository)
        service = MargeService(mock_preset_repo, mock_recents_repo, mock_device_repo)
        result = await service.resolve_device_id_for_account("3784726")
        assert result == "F4E11EA01FE6"
        mock_device_repo.get_by_account_uuid.assert_called_once_with("3784726")

    @pytest.mark.asyncio
    async def test_resolve_returns_none_when_no_mapping(self):
        """Verify resolve returns None for unknown account_id."""
        mock_device_repo = AsyncMock(spec=DeviceRepository)
        mock_device_repo.get_by_account_uuid = AsyncMock(return_value=None)
        mock_device_repo.get_by_device_id = AsyncMock(return_value=None)
        mock_preset_repo = AsyncMock(spec=PresetRepository)
        mock_recents_repo = AsyncMock(spec=RecentsRepository)
        service = MargeService(mock_preset_repo, mock_recents_repo, mock_device_repo)
        result = await service.resolve_device_id_for_account("unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_returns_none_without_device_repo(self):
        """Verify resolve returns None gracefully when no device_repo."""
        mock_preset_repo = AsyncMock(spec=PresetRepository)
        mock_recents_repo = AsyncMock(spec=RecentsRepository)
        service = MargeService(mock_preset_repo, mock_recents_repo)
        result = await service.resolve_device_id_for_account("3784726")
        assert result is None


class TestBug184AccountPairingInWizard:
    """BUG 2: ensure_account_uuid() existed but was never called in wizard."""

    @pytest.mark.asyncio
    async def test_wizard_has_ensure_account_pairing_method(self):
        """Verify WizardService exposes ensure_account_pairing."""
        from opencloudtouch.setup.wizard_service import WizardService

        wizard = WizardService()
        assert hasattr(wizard, "ensure_account_pairing")
        assert callable(wizard.ensure_account_pairing)

    @pytest.mark.asyncio
    async def test_ensure_account_pairing_persists_uuid(self):
        """Verify pairing persists UUID to device repository."""
        from opencloudtouch.setup.account_pairing_service import AccountPairingResult
        from opencloudtouch.setup.wizard_service import WizardService

        mock_device_repo = AsyncMock()
        mock_device_repo.update_marge_account_uuid = AsyncMock()
        wizard = WizardService(device_repo=mock_device_repo)
        fake_result = AccountPairingResult(
            success=True, had_uuid=False, uuid="1234567", message="UUID set"
        )
        with patch(
            "opencloudtouch.setup.wizard_service.ensure_account_uuid",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            result = await wizard.ensure_account_pairing(
                "192.168.1.100", "F4E11EA01FE6"
            )
        assert result["success"] is True
        assert result["uuid"] == "1234567"
        mock_device_repo.update_marge_account_uuid.assert_called_once_with(
            "F4E11EA01FE6", "1234567"
        )

    @pytest.mark.asyncio
    async def test_ensure_account_pairing_handles_failure(self):
        """Verify pairing handles failures gracefully."""
        from opencloudtouch.setup.wizard_service import WizardService

        wizard = WizardService()
        with patch(
            "opencloudtouch.setup.wizard_service.ensure_account_uuid",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Device unreachable"),
        ):
            result = await wizard.ensure_account_pairing(
                "192.168.1.100", "F4E11EA01FE6"
            )
        assert result["success"] is False
        assert "Device unreachable" in result["error"]


class TestBug184DatabaseMigration:
    """Verify migration v103 adds marge_account_uuid column."""

    @pytest.mark.asyncio
    async def test_repository_stores_and_retrieves_account_uuid(self, tmp_path):
        """Full integration: store device with UUID, retrieve by UUID."""
        db_path = tmp_path / "test.db"
        repo = DeviceRepository(str(db_path))
        await repo.initialize()
        try:
            device = Device(
                device_id="F4E11EA01FE6",
                ip="192.168.1.100",
                name="Test ST20",
                model="SoundTouch 20",
                mac_address="F4E11EA01FE6",
                firmware_version="27.0.6.46330",
            )
            await repo.upsert(device)
            await repo.update_marge_account_uuid("F4E11EA01FE6", "3784726")
            found = await repo.get_by_account_uuid("3784726")
            assert found is not None
            assert found.device_id == "F4E11EA01FE6"
            assert found.marge_account_uuid == "3784726"
        finally:
            await repo.close()

    @pytest.mark.asyncio
    async def test_get_by_account_uuid_returns_none_for_unknown(self, tmp_path):
        """Verify get_by_account_uuid returns None for non-existent UUID."""
        db_path = tmp_path / "test.db"
        repo = DeviceRepository(str(db_path))
        await repo.initialize()
        try:
            found = await repo.get_by_account_uuid("nonexistent")
            assert found is None
        finally:
            await repo.close()
