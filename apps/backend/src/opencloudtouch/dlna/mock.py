"""Deterministic fake DLNA server for ``OCT_MOCK_MODE`` and tests."""

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer

MOCK_SERVER = DlnaServer(
    id="mock-media-server",
    name="Mock Media Server",
    location="http://mock-media.invalid/root.xml",
    control_url="http://mock-media.invalid/control",
)
_BASE = "http://mock-media.invalid"
_AUDIO = "object.item.audioItem.musicTrack"


def _folder(item_id: str, parent: str, title: str) -> DlnaItem:
    return DlnaItem(
        id=item_id,
        parent_id=parent,
        title=title,
        is_container=True,
        media_class="object.container.storageFolder",
    )


def _track(item_id: str, parent: str, title: str, cover: str | None = None) -> DlnaItem:
    return DlnaItem(
        id=item_id,
        parent_id=parent,
        title=title,
        is_container=False,
        resource_url=f"{_BASE}/media/{item_id}.mp3",
        media_class=_AUDIO,
        album_art_url=cover,
        protocol_info="http-get:*:audio/mpeg:*",
    )


def _build() -> dict[str, list[DlnaItem]]:
    tree: dict[str, list[DlnaItem]] = {
        "0": [
            _folder("music", "0", "Music"),
            _folder("albums", "0", "Albums"),
            _folder("mixed", "0", "Mixed"),
            _folder("subfolders", "0", "Many Folders"),
        ],
        "music": [
            _track(f"music-{n:03d}", "music", f"Track {n:03d}") for n in range(1, 121)
        ],
        "albums": [_folder("albums-a", "albums", "Artist A")],
        "albums-a": [_folder("albums-a-b", "albums-a", "Album B")],
        "albums-a-b": [_folder("albums-a-b-c", "albums-a-b", "Disc C")],
        "albums-a-b-c": [
            _track("albums-a-b-c-1", "albums-a-b-c", "Deep Track 1"),
            _track("albums-a-b-c-2", "albums-a-b-c", "Deep Track 2"),
        ],
        "mixed": [
            _track("mixed-http", "mixed", "Track with cover", f"{_BASE}/cover.jpg"),
            _track("mixed-file", "mixed", "Track with file cover", "file:///cover.jpg"),
            DlnaItem(
                id="mixed-image",
                parent_id="mixed",
                title="Photo",
                is_container=False,
                resource_url=f"{_BASE}/media/photo.jpg",
                media_class="object.item.imageItem.photo",
                protocol_info="http-get:*:image/jpeg:*",
            ),
        ],
        "subfolders": [
            _folder(f"sub-{n:02d}", "subfolders", f"Folder {n:02d}")
            for n in range(1, 61)
        ]
        + [_track(f"sub-track-{n}", "subfolders", f"Track {n}") for n in range(1, 6)],
    }
    return tree


class MockDlnaDiscovery(DlnaDiscovery):
    """Discovery that always finds the fake server (no network)."""

    def __init__(self) -> None:
        pass

    async def discover(self) -> list[DlnaServer]:
        return [MOCK_SERVER]


class MockDlnaClient(DlnaClient):
    """Client serving the fake content tree (no network)."""

    def __init__(self) -> None:
        self._tree = _build()
        self._by_id = {i.id: i for items in self._tree.values() for i in items}
        self._by_id["0"] = _folder("0", "-1", "Root")

    async def browse(
        self,
        server: DlnaServer,
        object_id: str = "0",
        starting_index: int = 0,
        requested_count: int = 50,
    ) -> BrowsePage:
        children = self._tree.get(object_id)
        if children is None:
            if object_id in self._by_id:
                children = []
            else:
                raise DlnaBrowseError("No Such Object", error_code="701")
        page = children[starting_index : starting_index + requested_count]
        return BrowsePage(page, len(page), len(children))

    async def get_object(self, server: DlnaServer, object_id: str) -> DlnaItem:
        item = self._by_id.get(object_id)
        if item is None:
            raise DlnaBrowseError("No Such Object", error_code="701")
        return item
