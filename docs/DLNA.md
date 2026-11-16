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

**In the web UI:** open the preset dialog for a button, choose **DLNA**, pick a media server, open folders and press **For preset N** on a track or a folder. The dialog lists only the entries loaded so far when you filter; use **Load more** to continue. A folder preset plays its first track only (the row says so). The last folder is remembered until the browser tab is closed; if it or the server is gone, the dialog falls back to the server root or the server list with a notice. Save failures are shown at the top of the list with a **Try again** button.

`POST /api/presets/dlna` with `{"device_id", "preset_number", "server_id", "object_id"}` (no other fields are accepted) assigns an item to a preset button. The response is a normal preset with `source: "DLNA"` and `dlna: {server_id, object_id}`; the title (`station_name`) and the cover (`station_favicon`, only when it is on the media server's own host) come from the media server.

- **What is stored is a reference, not a URL.** On every press OpenCloudTouch asks the media server for the object and returns its current resource URL to the speaker, so a new server IP address does not break the preset. Resource and cover URLs must be `http(s)` on the same host as the server's control URL.
- **A track plays that track. A folder or playlist plays its first audio item** (up to 250 entries are searched, no sub-folders, no queue and no next track) unless the media server is enabled on the speaker, see [Native folder presets](#native-folder-presets).
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

## Native media server on a speaker

A speaker can play a media server by itself (source `STORED_MUSIC`). OpenCloudTouch registers the server on the speaker with `setMusicServiceAccount` (account `<server UUID>/0`); the speaker then calls the Marge emulation to create the registration row. The registration is per speaker and per media server and never happens automatically. Only media servers whose id is a UUID can be registered.

| State | Meaning |
|---|---|
| `not_registered` | Not registered on this speaker. |
| `unmanaged` | The speaker lists the account but OpenCloudTouch has no row (database reset or registered by another client). Enabling adopts it without calling the speaker again. |
| `restart_required` | The speaker sent the old provider id 50 (it cached an earlier provider list) and does not list the account yet. Restart this speaker once with `POST /api/devices/{id}/reboot` or switch it off and on at the power supply; the estimated restart time is 1-2 minutes. OpenCloudTouch never restarts a speaker itself. |
| `ready` | The speaker lists the account as `READY`. |
| `unavailable` | Registered but not usable (listed with another status, or not listed after 30 s). Remove it and register again; OpenCloudTouch never re-registers on its own. |
| `removal_pending` | The speaker was told to remove the account but still lists it; the removal finishes with a restart. |

The state comes from the speaker's live source list. Registration is `PUT /api/dlna/native/{device_id}/servers/{server_id}` (`202` after registering, `200` with the current state when nothing had to be done; it waits up to 30 s for `ready`). A second server on the same speaker normally becomes `ready` within seconds and needs no restart. `DELETE` removes the registration; when native presets use it the call answers `409 dlna_native_in_use` unless `?force=true`, which first switches those slots back to first-track playback. `GET /api/dlna/native?device_id=` lists every discovered server and every registration; a registration whose server is no longer discovered shows `server_known=false` and can be deleted. The speaker answering `1047` on removal (account unknown) counts as removed.

Registrations are stored in the table `media_server_sources`; downgrading OpenCloudTouch is not supported. Requests for the same speaker and server are serialised by a lock inside the single backend process.

## Native folder presets

When the media server is `ready` on the speaker (see above), `POST /api/presets/dlna` for a **folder or playlist** writes a native `STORED_MUSIC` item to the speaker: pressing the button plays the whole folder with a queue (next, previous, pause, play; shuffle is a speaker feature), **also while OpenCloudTouch is switched off**. The response has `dlna_playback: "native"`. In every other case (`not_registered`, `unmanaged`, `restart_required`, `unavailable`, `removal_pending`, no registration row) the preset is written as before and the response has `dlna_playback: "reference"`; `dlna` keeps its shape, and presets that are not DLNA presets have `dlna_playback: null`.

- **Single tracks always use the reference path** for now (first track, OpenCloudTouch must run): playing a track natively is not verified on a speaker yet (hardware item H1).
- The check reads the speaker's live source list on every save; if the speaker cannot be read the save fails like any other speaker write and nothing is stored.
- Only MP3 and AAC are known to play natively; other formats, folders with more than 100 tracks, folders with only sub-folders and several media servers at once are unverified.
- Overwriting a native slot with another preset resets it; clearing a preset removes it on the speaker first and leaves the registration untouched. A sync from the speaker keeps native slots unchanged.
- If the registration is removed or the server gets a new UUID, the native slot stops working; OpenCloudTouch shows the reference again while the row is gone. Assign the preset again.
- Mock mode: the fake "Mock Media Server (UUID)" can be enabled on the mock speaker and then used for native folder presets without any hardware.

## Timeouts

Connecting times out after 3 s. `OCT_DLNA_TIMEOUT` (default 15 s, 1-60) is the read timeout and also the total deadline of one operation. See [CONFIGURATION.md](CONFIGURATION.md).

## Mock mode

With `OCT_MOCK_MODE=true` a fake server "Mock Media Server" is used (no network; a second fake server with a UUID id can be registered natively, and a registration becomes `ready` without a restart): folder `Music` with 120 tracks, `Albums` three folder levels deep, `Mixed` with a non-audio item and a `file://` cover, and `Many Folders` whose first 60 entries are folders.
