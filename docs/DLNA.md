# DLNA media servers

OpenCloudTouch discovers UPnP/DLNA media servers (SSDP) and browses their ContentDirectory.

## Browsing

`GET /api/dlna/servers/{server_id}/browse?object_id=0&starting_index=0&requested_count=50`

- `server_id` is the server UDN without `uuid:`. An empty `object_id` means the root `0`.
- `starting_index` is 0 or more; `requested_count` is 1-200 (default 50).
- The response keeps `server_id`, `object_id` and `items` and adds `starting_index`, `number_returned`, `total_matches` (`null` if the server does not report it), `next_index` and `has_more`.
- **Always use `has_more` to decide whether to load another page, never the length of `items`.** `number_returned` is what the server reported before filtering; `next_index` is `starting_index + number_returned`.
- `items` contains only folders and audio items (UPnP class `object.item.audioItem...` or an `audio/*` protocolInfo). Other items are dropped but still count in `number_returned`, so a page can hold fewer entries than requested (even none) while `has_more` is `true`. Load the next page.
- Server order is kept. `album_art_url` is only returned when it is an absolute `http(s)` URL, otherwise `null`; OpenCloudTouch does not fetch or proxy covers.

## Errors

| `code` | Status | When |
|---|---|---|
| `dlna_server_not_found` | 404 | the server was not discovered |
| `dlna_object_not_found` | 404 | UPnP error 701 (object removed or renumbered) |
| `dlna_upstream_error` | 502 | connection refused, HTTP/SOAP failure, invalid response |
| `dlna_server_timeout` | 504 | read timeout or total deadline exceeded |
| `validation_error` | 422 | paging values out of range |

## DLNA items as presets

`POST /api/presets/dlna` with `{"device_id", "preset_number", "server_id", "object_id"}` (no other fields are accepted) assigns an item to a preset button. The response is a normal preset with `source: "DLNA"` and `dlna: {server_id, object_id}`; the title (`station_name`) and the cover (`station_favicon`, only when it is on the media server's own host) come from the media server.

- **What is stored is a reference, not a URL.** On every press OpenCloudTouch asks the media server for the object and returns its current resource URL to the speaker, so a new server IP address does not break the preset. Resource and cover URLs must be `http(s)` on the same host as the server's control URL.
- **A track plays that track. A folder or playlist plays its first audio item** (up to 250 entries are searched, no sub-folders, no queue and no next track).
- **The press only uses already discovered servers** (it never starts a network scan) and has a budget of 3 s. If the server is not known, the press fails (`dlna_server_not_found`, HTTP 503) and one background discovery starts; OpenCloudTouch also discovers once at startup. The first press after a restart or an IP change may therefore fail once.
- **Servers that renumber object ids after a library rescan** make saved presets fail with `dlna_object_not_found`. Assign the preset again.
- The speaker plays the formats it supports (for example MP3 and FLAC) and fetches the file itself; OpenCloudTouch does not transcode or proxy audio.
- The stream proxy, playlist (M3U/PLS) and descriptor-redirect routes answer 409 `dlna_preset_not_streamable` for DLNA presets.

| `code` | Save status | Press status | When |
|---|---|---|---|
| `dlna_server_not_found` | 404 | 503 | server not discovered (press: not in the discovery cache) |
| `dlna_object_not_found` | 404 | 404 | UPnP error 701 |
| `dlna_upstream_error` | 502 | 503 | server request failed |
| `dlna_server_timeout` | 504 | 503 | server did not answer in time |
| `dlna_not_playable` | 422 | 404 | not audio, no audio item in a folder, URL rule violated |
| `dlna_reference_too_long` | 422 | - | the stored reference would exceed 1024 characters (long ids and titles with non-ASCII characters) |

Titles and URLs are not written to logs or error messages.

## Timeouts

Connecting times out after 3 s. `OCT_DLNA_TIMEOUT` (default 15 s, 1-60) is the read timeout and also the total deadline of one operation. See [CONFIGURATION.md](CONFIGURATION.md).

## Mock mode

With `OCT_MOCK_MODE=true` a fake server "Mock Media Server" is used (no network): folder `Music` with 120 tracks, `Albums` three folder levels deep, `Mixed` with a non-audio item and a `file://` cover, and `Many Folders` whose first 60 entries are folders.
