"""Deterministic in-process DLNA media server for ``OCT_MOCK_MODE`` and tests."""

from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer

MOCK_CONTROL_URL = "mock://media-server/control"
MOCK_SERVER = DlnaServer(
    id="4d696e69-0000-0000-0000-00000000c0de",
    name="Mock Media Server",
    location="mock://media-server/description.xml",
    control_url=MOCK_CONTROL_URL,
)

_ALBUM = "object.container.album.musicAlbum"
_FOLDER = "object.container.storageFolder"
_AUDIO = "object.item.audioItem.musicTrack"


def _container(item_id: str, parent: str, title: str, media_class: str) -> DlnaItem:
    return DlnaItem(item_id, parent, title, True, media_class=media_class)


def _track(item_id: str, parent: str, title: str) -> DlnaItem:
    return DlnaItem(
        item_id,
        parent,
        title,
        False,
        resource_url=f"mock://media-server/{item_id}.mp3",
        media_class=_AUDIO,
        protocol_info="http-get:*:audio/mpeg:*",
    )


_IMAGE = DlnaItem(
    "photo-1",
    "photos",
    "Cover scan",
    False,
    resource_url="mock://media-server/photo-1.jpg",
    media_class="object.item.imageItem.photo",
    protocol_info="http-get:*:image/jpeg:*",
)

_CHILDREN: dict[str, list[DlnaItem]] = {
    "0": [
        _container("albums", "0", "Albums", _FOLDER),
        _container("photos", "0", "Photos", _FOLDER),
        _track("single", "0", "Single Track"),
    ],
    "albums": [
        _container("album-1", "albums", "Album One", _ALBUM),
        _container("album-2", "albums", "Album Two", _ALBUM),
    ],
    "album-1": [
        _track(f"a1-t{n}", "album-1", f"Album One Track {n}") for n in (1, 2, 3)
    ],
    "album-2": [
        _track(f"a2-t{n}", "album-2", f"Album Two Track {n}") for n in (1, 2, 3)
    ],
    # First child is not audio: exercises the pre-save warning.
    "photos": [_IMAGE, _track("photos-t1", "photos", "Photos Track")],
}
_BY_ID = {i.id: i for items in _CHILDREN.values() for i in items} | {
    "0": _container("0", "-1", MOCK_SERVER.name, _FOLDER)
}


def mock_browse(
    object_id: str, starting_index: int, requested_count: int
) -> BrowsePage:
    """One page of children; KeyError for an unknown container."""
    children = _CHILDREN.get(object_id)
    if children is None:
        if object_id not in _BY_ID:
            raise KeyError(object_id)
        children = []
    # requested_count 0 means "all" in UPnP.
    end = starting_index + requested_count if requested_count else None
    page = children[starting_index:end]
    return BrowsePage(page, len(page), len(children))


def mock_object(object_id: str) -> DlnaItem:
    """Metadata of one object; KeyError if unknown."""
    return _BY_ID[object_id]
