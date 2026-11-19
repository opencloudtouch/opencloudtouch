"""Regression tests found while measuring the uncompressed backup on the real device.

* Two backups of the same day in different formats (.tgz from before, .tar now) were merged into ONE set
  that listed every volume twice.
* The scan validated every archive of every set (about 30 s per large archive on the device).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.setup.restore_models import BackupFileInfo
from opencloudtouch.setup.restore_service import RestoreService


def _file(name: str, volume: str, device="ABC123", date="20261105") -> BackupFileInfo:
    return BackupFileInfo(
        filename=name,
        volume_type=volume,
        file_path=f"/media/sda1/oct-backup/{name}",
        device_id=device,
        backup_date=date,
    )


def test_same_day_tar_and_tgz_are_one_set_with_one_file_per_volume_preferring_tar():
    files = [
        _file("soundtouch-ABC123-20261105-rootfs.tgz", "rootfs"),
        _file("soundtouch-ABC123-20261105-rootfs.tar", "rootfs"),
        _file("soundtouch-ABC123-20261105-nv.tgz", "persistent"),
        _file("soundtouch-ABC123-20261105-nv.tar", "persistent"),
        _file("soundtouch-ABC123-20261105-update.tgz", "update"),
    ]

    sets = RestoreService._group_into_sets(files)

    assert len(sets) == 1
    names = sorted(f.filename for f in sets[0].files)
    assert names == [
        "soundtouch-ABC123-20261105-nv.tar",
        "soundtouch-ABC123-20261105-rootfs.tar",
        "soundtouch-ABC123-20261105-update.tgz",  # no .tar for this volume: the .tgz stays
    ]


def test_different_days_stay_different_sets():
    files = [
        _file("soundtouch-ABC123-20261104-rootfs.tgz", "rootfs", date="20261104"),
        _file("soundtouch-ABC123-20261105-rootfs.tar", "rootfs"),
    ]
    assert len(RestoreService._group_into_sets(files)) == 2


@pytest.mark.parametrize("order", ["tar_first", "tgz_first"])
def test_the_preference_does_not_depend_on_the_listing_order(order):
    tar = _file("soundtouch-ABC123-20261105-rootfs.tar", "rootfs")
    tgz = _file("soundtouch-ABC123-20261105-rootfs.tgz", "rootfs")
    files = [tar, tgz] if order == "tar_first" else [tgz, tar]

    (backup_set,) = RestoreService._group_into_sets(files)

    assert [f.filename for f in backup_set.files] == [
        "soundtouch-ABC123-20261105-rootfs.tar"
    ]


@pytest.mark.asyncio
async def test_scan_validates_only_the_selected_set():
    service = RestoreService()
    files = [
        _file(
            "soundtouch-OTHER99-20261101-rootfs.tar",
            "rootfs",
            device="OTHER99",
            date="20261101",
        ),
        _file("soundtouch-ABC123-20261105-rootfs.tar", "rootfs"),
        _file("soundtouch-ABC123-20261105-nv.tar", "persistent"),
    ]
    validated: list[str] = []

    async def fake_validate(ssh, file_info):
        validated.append(file_info.filename)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = AsyncMock()
    mock_ctx.__aexit__.return_value = False

    with (
        patch.object(service, "_find_usb_backups", AsyncMock(return_value=files)),
        patch.object(service, "_validate_archive", side_effect=fake_validate),
        patch(
            "opencloudtouch.setup.restore_service.ssh_operation", return_value=mock_ctx
        ),
    ):
        result = await service.scan_backups("192.168.1.100", "ABC123")

    assert result.selected_set is not None
    assert sorted(validated) == [
        "soundtouch-ABC123-20261105-nv.tar",
        "soundtouch-ABC123-20261105-rootfs.tar",
    ]
    assert len(result.all_sets) == 2  # the other set is still listed, just not read


@pytest.mark.asyncio
async def test_scan_without_a_matching_set_reads_no_archive():
    service = RestoreService()
    files = [
        _file(
            "soundtouch-OTHER99-20261101-rootfs.tar",
            "rootfs",
            device="OTHER99",
            date="20261101",
        )
    ]
    validate = AsyncMock()

    with (
        patch.object(service, "_find_usb_backups", AsyncMock(return_value=files)),
        patch.object(service, "_validate_archive", validate),
        patch(
            "opencloudtouch.setup.restore_service.ssh_operation",
            return_value=MagicMock(),
        ),
    ):
        result = await service.scan_backups("192.168.1.100", "ABC123")

    assert result.selected_set is None
    assert result.error
    validate.assert_not_called()
