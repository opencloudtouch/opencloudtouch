"""Tests for wizard_service.verify_setup() -- Issue #184."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from opencloudtouch.setup.persistence_service import _PERSISTENCE_DIR
from opencloudtouch.setup.ssh_client import CommandResult
from opencloudtouch.setup.wizard_service import WizardService

FULL_SOURCES_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<sources>
    <source displayName="AIRPLAY"><sourceKey type="AIRPLAY" account="" /></source>
    <source displayName="AUX IN"><sourceKey type="AUX" account="AUX" /></source>
    <source displayName="LOCAL_INTERNET_RADIO"><sourceKey type="LOCAL_INTERNET_RADIO" account="" /></source>
    <source displayName="QPLAY"><sourceKey type="QPLAY" account="" /></source>
    <source displayName="SPOTIFY"><sourceKey type="SPOTIFY" account="" /></source>
    <source displayName="STORED_MUSIC"><sourceKey type="STORED_MUSIC" account="" /></source>
    <source displayName="STORED_MUSIC_MEDIA_RENDERER"><sourceKey type="STORED_MUSIC_MEDIA_RENDERER" account="" /></source>
    <source displayName="TUNEIN"><sourceKey type="TUNEIN" account="" /></source>
    <source displayName="UPNP"><sourceKey type="UPNP" account="" /></source>
</sources>"""

AUX_ONLY_SOURCES = """<?xml version="1.0" encoding="UTF-8" ?>
<sources>
    <source displayName="AUX IN"><sourceKey type="AUX" account="AUX" /></source>
</sources>"""

GOOD_CONFIG = """<?xml version="1.0" ?>
<SoundTouchSdkPrivateCfg>
  <bmxRegistryUrl>http://192.168.1.50:7777</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>"""

BOSE_CONFIG = """<?xml version="1.0" ?>
<SoundTouchSdkPrivateCfg>
  <bmxRegistryUrl>https://bmx.bose.com</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>"""

GOOD_SYS_CONFIG = """<?xml version="1.0" encoding="UTF-8" ?>
<SystemConfiguration>
    <AccountUUID>5448503</AccountUUID>
    <acctMode>local</acctMode>
    <isMultiDeviceAccount>true</isMultiDeviceAccount>
</SystemConfiguration>"""

GOOD_HOSTS = """127.0.0.1 localhost
# OCT-START
192.168.1.50 bose.vtuner.com
192.168.1.50 bose2.vtuner.com
192.168.1.50 primary5.vtuner.com
192.168.1.50 primary6.vtuner.com
192.168.1.50 streaming.bose.com
192.168.1.50 bmx.bose.com
192.168.1.50 api.bosesoundtouch.com
192.168.1.50 content.api.bose.io
192.168.1.50 events.api.bosecm.com
192.168.1.50 worldwide.bose.com
# OCT-END
"""


def _make_ssh_responses(responses: dict[str, str]):
    """Create SSH mock that returns different output per command pattern."""
    ssh = AsyncMock()

    async def fake_execute(cmd: str, **kwargs) -> CommandResult:
        for pattern, output in responses.items():
            if pattern in cmd:
                return CommandResult(success=True, output=output, exit_code=0)
        return CommandResult(success=True, output="", exit_code=0)

    ssh.execute = AsyncMock(side_effect=fake_execute)
    return ssh


def _make_device_repo(uuid_device_id=None):
    repo = AsyncMock()
    if uuid_device_id:
        device = MagicMock()
        device.device_id = uuid_device_id
        repo.get_by_account_uuid = AsyncMock(return_value=device)
    else:
        repo.get_by_account_uuid = AsyncMock(return_value=None)
    return repo


class TestVerifySetupAllPass:
    """Happy path: all checks pass."""

    @pytest.mark.asyncio
    async def test_all_checks_pass(self):
        repo = _make_device_repo(uuid_device_id="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        config_hash = "abc123"
        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f /opt/Bose": "exists",
                "test -f /mnt/nv/Override": "exists",
                "test -f /mnt/nv/SoundTouch": "exists",
                "md5sum": f"{config_hash}  /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml\n{config_hash}  /mnt/nv/OverrideSdkPrivateCfg.xml\n{config_hash}  /mnt/nv/SoundTouchSdkPrivateCfg.xml",
                "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml": GOOD_CONFIG,
                "cat /etc/hosts": GOOD_HOSTS,
                f"test -f {_PERSISTENCE_DIR}/SystemConfigurationDB.xml": "exists",
                f"cat {_PERSISTENCE_DIR}/SystemConfigurationDB.xml": GOOD_SYS_CONFIG,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        assert result["success"] is True
        assert result["failed_count"] == 0
        assert result["passed_count"] == 11


class TestVerifyUUIDMissing:
    """UUID missing from device."""

    @pytest.mark.asyncio
    async def test_uuid_missing_fails_check_1(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": GOOD_CONFIG,
                "cat /etc/hosts": GOOD_HOSTS,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        assert result["success"] is False
        uuid_check = next(c for c in result["checks"] if c["name"] == "uuid_present")
        assert uuid_check["passed"] is False


class TestVerifyUUIDNotInDB:
    """UUID exists on device but not in DB."""

    @pytest.mark.asyncio
    async def test_uuid_not_in_db_fails(self):
        repo = _make_device_repo(uuid_device_id=None)
        service = WizardService(device_repo=repo)

        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": GOOD_CONFIG,
                "cat /etc/hosts": GOOD_HOSTS,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        db_check = next(c for c in result["checks"] if c["name"] == "uuid_in_db")
        assert db_check["passed"] is False


class TestVerifySourcesIncomplete:
    """Sources.xml has only AUX."""

    @pytest.mark.asyncio
    async def test_aux_only_fails(self):
        repo = _make_device_repo(uuid_device_id="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": AUX_ONLY_SOURCES,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": GOOD_CONFIG,
                "cat /etc/hosts": GOOD_HOSTS,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        src_check = next(c for c in result["checks"] if c["name"] == "sources_complete")
        assert src_check["passed"] is False
        assert "Missing sources" in src_check["message"]


class TestVerifyBMXStillBose:
    """BMX URL still points to bose.com."""

    @pytest.mark.asyncio
    async def test_bose_bmx_url_fails(self):
        repo = _make_device_repo(uuid_device_id="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": BOSE_CONFIG,
                "cat /etc/hosts": GOOD_HOSTS,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        bmx_check = next(c for c in result["checks"] if c["name"] == "config_bmx_url")
        assert bmx_check["passed"] is False
        assert "Bose cloud" in bmx_check["message"]


class TestVerifyNoOCTBlock:
    """No OCT block in /etc/hosts."""

    @pytest.mark.asyncio
    async def test_no_oct_block_fails(self):
        repo = _make_device_repo(uuid_device_id="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": GOOD_CONFIG,
                "cat /etc/hosts": "127.0.0.1 localhost\n",
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        hosts_check = next(
            c for c in result["checks"] if c["name"] == "hosts_oct_block"
        )
        assert hosts_check["passed"] is False


class TestVerifyMissingDomains:
    """OCT block exists but missing domains."""

    @pytest.mark.asyncio
    async def test_missing_domains_fails(self):
        repo = _make_device_repo(uuid_device_id="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        partial_hosts = "# OCT-START\n192.168.1.50 bose.vtuner.com\n# OCT-END\n"
        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": GOOD_CONFIG,
                "cat /etc/hosts": partial_hosts,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        domain_check = next(
            c for c in result["checks"] if c["name"] == "hosts_domains_complete"
        )
        assert domain_check["passed"] is False
        assert "Missing host entries" in domain_check["message"]


class TestVerifyWrongIP:
    """Host entries point to wrong IP."""

    @pytest.mark.asyncio
    async def test_wrong_ip_fails(self):
        repo = _make_device_repo(uuid_device_id="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        wrong_ip_hosts = """# OCT-START
10.0.0.1 bose.vtuner.com
10.0.0.1 bose2.vtuner.com
10.0.0.1 primary5.vtuner.com
10.0.0.1 primary6.vtuner.com
10.0.0.1 streaming.bose.com
10.0.0.1 bmx.bose.com
10.0.0.1 api.bosesoundtouch.com
10.0.0.1 content.api.bose.io
10.0.0.1 events.api.bosecm.com
10.0.0.1 worldwide.bose.com
# OCT-END
"""
        ssh = _make_ssh_responses(
            {
                f"cat {_PERSISTENCE_DIR}/Sources.xml": FULL_SOURCES_XML,
                "test -f": "exists",
                "md5sum": "abc  f1\nabc  f2\nabc  f3",
                "cat /opt/Bose": GOOD_CONFIG,
                "cat /etc/hosts": wrong_ip_hosts,
            }
        )

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.verify_setup(
                "192.168.1.100", "AABBCCDDEEFF", "192.168.1.50"
            )

        ip_check = next(c for c in result["checks"] if c["name"] == "hosts_ip_correct")
        assert ip_check["passed"] is False
        assert "wrong IP" in ip_check["message"]
