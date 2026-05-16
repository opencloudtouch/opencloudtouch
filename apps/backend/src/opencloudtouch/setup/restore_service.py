"""Restore Wizard orchestration service.

Handles backup scanning and restore execution for undoing all OCT
modifications on a SoundTouch device.
"""

import logging
import re
import time
from pathlib import Path
from typing import Optional

from opencloudtouch.setup.restore_models import (
    BackupFileInfo,
    BackupScanResult,
    BackupSet,
    RestoreResult,
    RestoreStep,
    RestoreStepName,
    StepStatus,
)
from opencloudtouch.setup.wizard_helpers import ssh_operation

logger = logging.getLogger(__name__)

# Filename patterns:
# Modern: soundtouch-{device_id}-{date}-{volume}.tgz
# Modern pre-restore: soundtouch-{device_id}-{date}-pre-restore-{volume}.tgz
# Legacy: soundtouch-{volume}.tgz
_MODERN_RE = re.compile(
    r"^soundtouch-([A-Za-z0-9]+)-(\d{8})-(pre-restore-)?(rootfs|nv|update)\.tgz$"
)
_LEGACY_RE = re.compile(r"^soundtouch-(rootfs|nv|update)\.tgz$")

# Map filename volume suffix to VolumeType value
_VOLUME_MAP = {"rootfs": "rootfs", "nv": "persistent", "update": "update"}


class RestoreService:
    """Orchestrates the Restore Wizard steps.

    Composes existing services (WizardService for backup_all, BackupService
    for filename parsing) and adds restore-specific logic.
    """

    def __init__(self, wizard_service=None, device_repo=None) -> None:
        self._wizard_service = wizard_service
        self._device_repo = device_repo

    @staticmethod
    def _parse_backup_filename(filename: str) -> Optional[BackupFileInfo]:
        """Parse a backup filename and extract metadata.

        Returns BackupFileInfo or None if filename doesn't match any pattern.
        """
        match = _MODERN_RE.match(filename)
        if match:
            device_id, date, pre_restore, volume = match.groups()
            return BackupFileInfo(
                filename=filename,
                volume_type=_VOLUME_MAP[volume],
                file_path="",
                device_id=device_id,
                backup_date=date,
                is_pre_restore=pre_restore is not None,
            )

        match = _LEGACY_RE.match(filename)
        if match:
            volume = match.group(1)
            return BackupFileInfo(
                filename=filename,
                volume_type=_VOLUME_MAP[volume],
                file_path="",
            )

        return None

    async def _find_usb_backups(self, device_ip: str) -> list[BackupFileInfo]:
        """SSH to device and list backup files on USB stick.

        Returns list of parsed BackupFileInfo (excludes pre-restore files).
        """
        async with ssh_operation(device_ip, "find-backups") as ssh:
            # Check USB mount
            result = await ssh.execute("ls -d /media/sda1 2>/dev/null")
            if result.exit_code != 0 or not result.output.strip():
                return []

            # List backup directory
            result = await ssh.execute(
                "ls /media/sda1/oct-backup/*.tgz 2>/dev/null | xargs -n1 basename"
            )
            if result.exit_code != 0 or not result.output.strip():
                return []

            files = []
            for line in result.output.strip().split("\n"):
                filename = line.strip()
                if not filename:
                    continue
                info = self._parse_backup_filename(filename)
                if info and not info.is_pre_restore:
                    info.file_path = f"/media/sda1/oct-backup/{filename}"
                    files.append(info)

            return files

    @staticmethod
    def _group_into_sets(files: list[BackupFileInfo]) -> list:
        """Group backup files into BackupSets by device_id + date."""
        groups: dict[tuple, list[BackupFileInfo]] = {}
        for f in files:
            key = (f.device_id, f.backup_date)
            groups.setdefault(key, []).append(f)

        sets = []
        for (device_id, date), group_files in groups.items():
            sets.append(
                BackupSet(
                    device_id=device_id,
                    backup_date=date,
                    files=group_files,
                    is_legacy=device_id is None,
                )
            )
        return sets

    @staticmethod
    def _select_backup_set(sets: list, target_device_id: str) -> Optional["BackupSet"]:
        """Select best matching backup set for target device.

        Priority: device_id match (newest date) → legacy fallback → None.
        """
        # Find sets matching target device_id
        matching = [s for s in sets if s.device_id == target_device_id]
        if matching:
            # Pick newest by date
            matching.sort(key=lambda s: s.backup_date or "", reverse=True)
            selected = matching[0]
            selected.is_match = True
            return selected

        # Fallback to legacy (no device_id)
        legacy = [s for s in sets if s.is_legacy]
        if legacy:
            return legacy[0]

        return None

    async def scan_backups(self, device_ip: str, device_id: str) -> BackupScanResult:
        """Scan USB stick for backup files and auto-select matching set."""
        files = await self._find_usb_backups(device_ip)

        if not files:
            # Determine if USB not mounted or just empty
            async with ssh_operation(device_ip, "check-usb") as ssh:
                result = await ssh.execute("ls -d /media/sda1 2>/dev/null")
                usb_mounted = result.exit_code == 0 and bool(result.output.strip())

            if not usb_mounted:
                return BackupScanResult(
                    usb_mounted=False,
                    error="USB stick not detected at /media/sda1. Please insert USB stick and try again.",
                )
            return BackupScanResult(
                usb_mounted=True,
                error="No backup files found in /media/sda1/oct-backup/.",
            )

        sets = self._group_into_sets(files)

        # Validate archives in each set
        async with ssh_operation(device_ip, "validate-archives") as ssh:
            for backup_set in sets:
                for file_info in backup_set.files:
                    await self._validate_archive(ssh, file_info)

        selected = self._select_backup_set(sets, device_id)

        error = None
        if selected is None:
            error = (
                f"No matching backup found for device {device_id}. "
                "Please provide the correct backup or choose Clean Restore."
            )

        return BackupScanResult(
            usb_mounted=True,
            selected_set=selected,
            all_sets=sets,
            error=error,
        )

    async def execute_restore(
        self,
        device_ip: str,
        device_id: str,
        restore_type: str,
        backup_set: Optional[dict] = None,
        skip_snapshot: bool = False,
    ) -> RestoreResult:
        """Execute full restore sequence.

        Sequence: pre-snapshot → config → presets → hosts → remote_services → reboot.
        """
        start = time.time()
        steps: list[RestoreStep] = []

        async with ssh_operation(device_ip, "restore") as ssh:
            # Remount read-write
            await ssh.execute("mount -o remount,rw /")
            await ssh.execute("mount -o remount,rw /mnt/nv")

            try:
                # Pre-restore snapshot
                if not skip_snapshot:
                    step = await self._pre_restore_snapshot(device_ip, device_id)
                    steps.append(step)

                # Config
                step = await self._restore_config(ssh, restore_type, backup_set)
                steps.append(step)

                # Presets
                step = await self._restore_presets(ssh, restore_type, backup_set)
                steps.append(step)

                # Hosts
                step = await self._restore_hosts(ssh)
                steps.append(step)

                # Remote services
                step = await self._remove_remote_services(ssh)
                steps.append(step)

            finally:
                # Remount read-only
                await ssh.execute("mount -o remount,ro /mnt/nv")
                await ssh.execute("mount -o remount,ro /")

        # Update setup_status
        if self._device_repo:
            await self._device_repo.update_setup_status(device_id, "restored")

        all_ok = all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in steps
        )

        return RestoreResult(
            success=all_ok,
            restore_type=restore_type,
            steps=steps,
            total_duration_seconds=time.time() - start,
        )

    async def _pre_restore_snapshot(
        self, device_ip: str, device_id: str
    ) -> RestoreStep:
        """Create pre-restore safety snapshot via backup_all()."""
        step = RestoreStep(name=RestoreStepName.PRE_SNAPSHOT)
        start = time.time()
        try:
            if self._wizard_service:
                result = await self._wizard_service.backup_all(device_ip, device_id)
                if result.get("success"):
                    step.status = StepStatus.COMPLETED
                    step.message = "Pre-restore snapshot saved"
                else:
                    step.status = StepStatus.FAILED
                    step.message = result.get("message", "Snapshot failed")
                    step.error = step.message
            else:
                step.status = StepStatus.SKIPPED
                step.message = "No wizard service available"
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.message = f"Snapshot failed: {e}"
        step.duration_seconds = time.time() - start
        return step

    async def _restore_config(
        self, ssh, restore_type: str, backup_set: Optional[dict] = None
    ) -> RestoreStep:
        """Restore config XML files."""
        step = RestoreStep(name=RestoreStepName.CONFIG)
        start = time.time()

        # Override paths that OCT may have created
        override_paths = [
            "/mnt/nv/OverrideSdkPrivateCfg.xml",
            "/mnt/nv/SoundTouchSdkPrivateCfg.xml",
        ]

        try:
            if restore_type == "backup" and backup_set:
                # Extract config files from backup archives on device
                for file_ref in backup_set.get("files", []):
                    file_path = file_ref.get("file_path", "")
                    vol = file_ref.get("volume_type", "")
                    if vol == "rootfs":
                        await ssh.execute(
                            f"tar xzf {file_path} -C / "
                            "opt/Bose/etc/SoundTouchSdkPrivateCfg.xml 2>/dev/null"
                        )
                    elif vol == "persistent":
                        for override in override_paths:
                            # Try extracting — may not exist in archive
                            result = await ssh.execute(
                                f"tar xzf {file_path} -C / "
                                f"{override.lstrip('/')} 2>/dev/null"
                            )
                            if result.exit_code != 0:
                                # Not in archive → delete override (OCT created it)
                                await ssh.execute(f"rm -f {override}")
            else:
                # Clean restore: delete overrides only, never firmware config
                for override in override_paths:
                    await ssh.execute(f"rm -f {override}")

            step.status = StepStatus.COMPLETED
            step.message = "Config files restored"
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.message = f"Config restore failed: {e}"

        step.duration_seconds = time.time() - start
        return step

    async def _restore_presets(
        self, ssh, restore_type: str = "clean", backup_set: Optional[dict] = None
    ) -> RestoreStep:
        """Restore presets to empty template or from backup."""
        step = RestoreStep(name=RestoreStepName.PRESETS)
        start = time.time()

        try:
            # Find Presets.xml on device
            result = await ssh.execute("find /mnt/nv -name Presets.xml 2>/dev/null")
            if result.exit_code != 0 or not result.output.strip():
                step.status = StepStatus.SKIPPED
                step.message = "No Presets.xml found on device (already clean)"
                step.duration_seconds = time.time() - start
                return step

            preset_path = result.output.strip().split("\n")[0].strip()

            if restore_type == "backup" and backup_set:
                # Try extracting from nv archive
                extracted = False
                for file_ref in backup_set.get("files", []):
                    if file_ref.get("volume_type") == "persistent":
                        file_path = file_ref.get("file_path", "")
                        r = await ssh.execute(
                            f"tar xzf {file_path} -C / "
                            f"{preset_path.lstrip('/')} 2>/dev/null"
                        )
                        if r.exit_code == 0:
                            extracted = True
                            break

                if not extracted:
                    # Fallback to clean restore behavior
                    await self._write_empty_presets(ssh, preset_path)
            else:
                # Clean restore: copy empty template
                await self._write_empty_presets(ssh, preset_path)

            step.status = StepStatus.COMPLETED
            step.message = f"Presets restored at {preset_path}"
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.message = f"Preset restore failed: {e}"

        step.duration_seconds = time.time() - start
        return step

    async def _write_empty_presets(self, ssh, preset_path: str) -> None:
        """Write empty presets template to device via base64 pipe."""
        import base64

        template_path = Path(__file__).parent / "data" / "empty_presets.xml"
        content = template_path.read_bytes()
        b64 = base64.b64encode(content).decode("ascii")
        await ssh.execute(f"echo '{b64}' | base64 -d > {preset_path}")

    async def _restore_hosts(self, ssh) -> RestoreStep:
        """Remove OCT block from /etc/hosts."""
        step = RestoreStep(name=RestoreStepName.HOSTS)
        start = time.time()

        try:
            result = await ssh.execute("cat /etc/hosts")
            if result.exit_code != 0:
                step.status = StepStatus.FAILED
                step.error = "Failed to read /etc/hosts"
                step.duration_seconds = time.time() - start
                return step

            content = result.output
            if "# OCT-START" not in content:
                step.status = StepStatus.SKIPPED
                step.message = "No OCT block found in /etc/hosts (already clean)"
                step.duration_seconds = time.time() - start
                return step

            # Strip OCT block
            clean_lines = []
            in_block = False
            for line in content.splitlines():
                if "# OCT-START" in line:
                    in_block = True
                    continue
                if "# OCT-END" in line:
                    in_block = False
                    continue
                if not in_block:
                    clean_lines.append(line)

            new_content = "\n".join(clean_lines) + "\n"

            # Write back via base64 pipe
            import base64

            b64 = base64.b64encode(new_content.encode()).decode("ascii")
            await ssh.execute(f"echo '{b64}' | base64 -d > /etc/hosts")

            step.status = StepStatus.COMPLETED
            step.message = "OCT block removed from /etc/hosts"
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.message = f"Hosts restore failed: {e}"

        step.duration_seconds = time.time() - start
        return step

    async def _remove_remote_services(self, ssh) -> RestoreStep:
        """Delete /mnt/nv/remote_services to disable permanent SSH."""
        step = RestoreStep(name=RestoreStepName.REMOTE_SERVICES)
        start = time.time()

        try:
            await ssh.execute("rm -f /mnt/nv/remote_services")
            step.status = StepStatus.COMPLETED
            step.message = "/mnt/nv/remote_services deleted"
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.message = f"Failed to remove remote_services: {e}"

        step.duration_seconds = time.time() - start
        return step

    async def _validate_archive(self, ssh, file_info: BackupFileInfo) -> None:
        """Validate a backup archive by checking its contents via tar listing.

        Sets file_info.validation_status and validation_message in-place.
        """
        expected_prefixes = {
            "rootfs": "opt/Bose/",
            "persistent": "mnt/nv/",
            "update": "opt/Bose/",
        }
        expected = expected_prefixes.get(file_info.volume_type)
        if not expected:
            return

        result = await ssh.execute(
            f"tar tzf {file_info.file_path} 2>/dev/null | head -20"
        )
        if result.exit_code != 0:
            from opencloudtouch.setup.restore_models import ValidationStatus

            file_info.validation_status = ValidationStatus.INVALID
            file_info.validation_message = "Archive is corrupt or unreadable"
            return

        listing = result.output.strip()
        if not listing:
            from opencloudtouch.setup.restore_models import ValidationStatus

            file_info.validation_status = ValidationStatus.INVALID
            file_info.validation_message = "Archive is empty"
            return

        if not any(line.startswith(expected) for line in listing.split("\n")):
            from opencloudtouch.setup.restore_models import ValidationStatus

            file_info.validation_status = ValidationStatus.WARNING
            file_info.validation_message = (
                f"Expected paths starting with {expected} not found in archive"
            )

    async def _reboot_device(self, ssh) -> RestoreStep:
        """Reboot the device via SSH."""
        step = RestoreStep(name=RestoreStepName.REBOOT)
        start = time.time()

        try:
            # Send reboot command (may disconnect SSH)
            try:
                await ssh.execute("reboot")
            except Exception:
                # SSH disconnect on reboot is expected
                pass

            step.status = StepStatus.COMPLETED
            step.message = "Reboot command sent"
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.message = f"Reboot failed: {e}"

        step.duration_seconds = time.time() - start
        return step
