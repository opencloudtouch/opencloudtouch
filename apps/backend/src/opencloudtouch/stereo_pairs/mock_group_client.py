"""In-memory speakers for tests and mock mode, including the speaker's Marge call."""

from typing import Dict, List, Optional

from opencloudtouch.stereo_pairs.group_client import (
    GroupClientError,
    GroupState,
    SpeakerInfo,
)
from opencloudtouch.stereo_pairs.service import StereoPairService
from opencloudtouch.stereo_pairs.xml import GroupRequest


class FakeSpeaker:
    def __init__(self, ip: str, info: SpeakerInfo):
        self.ip = ip
        self.info = info
        self.group: Optional[GroupState] = None
        self.updates: List[tuple] = []
        self.zone_ids: List[str] = []
        self.reachable = True
        # failure injection: list of exceptions raised by the next calls
        self.add_group_errors: List[GroupClientError] = []
        self.remove_group_errors: List[GroupClientError] = []
        # simulate a timeout where the speaker applied the group anyway
        self.apply_before_error = False
        self.calls: List[str] = []


class InMemorySpeakerNetwork:
    """Behaves like the speakers: ``addGroup`` on a master calls OCT's Marge handler."""

    def __init__(self) -> None:
        self.speakers: Dict[str, FakeSpeaker] = {}
        self.service: Optional[StereoPairService] = None  # the Marge server (OCT)

    def add(
        self,
        ip: str,
        device_id: str,
        *,
        name: str = "Speaker",
        type: str = "SoundTouch 10",
        marge_account_uuid: str = "1234567",
        firmware: str = "27.0.6",
        lr_stereo_capable: bool = True,
    ) -> FakeSpeaker:
        info = SpeakerInfo(
            device_id, name, type, marge_account_uuid, firmware, lr_stereo_capable
        )
        self.speakers[ip] = FakeSpeaker(ip, info)
        return self.speakers[ip]

    def client(self, ip: str) -> "FakeGroupClient":
        return FakeGroupClient(self, self.speakers[ip])

    __call__ = client


class FakeGroupClient:
    def __init__(self, network: InMemorySpeakerNetwork, speaker: FakeSpeaker):
        self._network = network
        self._speaker = speaker

    def _check(self, call: str) -> None:
        self._speaker.calls.append(call)
        if not self._speaker.reachable:
            raise GroupClientError(
                f"{call} on {self._speaker.ip}: timeout", uncertain=True
            )

    async def get_info(self) -> SpeakerInfo:  # NOSONAR - the protocol is async
        self._check("get_info")
        return self._speaker.info

    async def get_group(
        self,
    ) -> Optional[GroupState]:  # NOSONAR - the protocol is async
        self._check("get_group")
        return self._speaker.group

    async def get_zone_member_ids(self) -> List[str]:  # NOSONAR - the protocol is async
        self._check("get_zone")
        return list(self._speaker.zone_ids)

    async def add_group(  # NOSONAR - the protocol is async and has sender_ip
        self, name, master_id, roles, *, group_id=None, sender_ip=None
    ):
        self._check("add_group")
        speaker = self._speaker
        pending_error = (
            speaker.add_group_errors.pop(0) if speaker.add_group_errors else None
        )
        if pending_error is not None and not speaker.apply_before_error:
            raise pending_error
        role_map = {device_id: role for device_id, (role, _ip) in roles.items()}
        if group_id is None:
            # master: the speaker creates the group through Marge
            service = self._network.service
            if service is None:
                raise GroupClientError(
                    "addGroup: marge unavailable",
                    code="GROUP_CREATE_GROUP_ON_MARGE_ERROR",
                )
            left = next(d for d, r in role_map.items() if r == "LEFT")
            right = next(d for d, r in role_map.items() if r == "RIGHT")
            pair = await service.marge_create(
                GroupRequest(master_id, name, left, right)
            )
            group_id = str(pair.id)
        speaker.group = GroupState(group_id, name, master_id, role_map)
        if pending_error is not None:
            raise pending_error
        return group_id

    async def update_group(  # NOSONAR - the protocol is async
        self,
        name: str,
        master_id: str,
        roles: Dict[str, tuple[str, str]],
        group_id: str,
    ) -> None:
        self._check("update_group")
        self._speaker.updates.append((name, master_id, roles, group_id))
        if self._speaker.group is not None:
            self._speaker.group.name = name

    async def remove_group(self) -> None:  # NOSONAR - the protocol is async
        self._check("remove_group")
        speaker = self._speaker
        if speaker.remove_group_errors:
            raise speaker.remove_group_errors.pop(0)
        speaker.group = None
