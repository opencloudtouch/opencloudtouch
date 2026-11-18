# Marge calls observed from SoundTouch speakers (firmware 27.0.6)

What a speaker (SoundTouch 10 and 20) sends to the OpenCloudTouch server when `margeServerUrl`, `bmxRegistryUrl`, `statsServerUrl` and
`swUpdateUrl` point at it, and how OCT answers. Observed with `tcpdump` and `logread` on real speakers; response shapes follow what the
speakers accept. Bodies below are shortened.

## Boot (every route answered 200)

| Request | OCT answer |
|---------|------------|
| `POST /v1/scmudc/{device}` | 200 (stats, ignored) |
| `POST /streaming/support/power_on` | 200 |
| `GET /bmx/registry/v1/services` | BMX service registry JSON |
| `GET /` | 200 (web UI, probably a connectivity probe) |
| `GET /streaming/sourceproviders` | `<sourceProviders>` |
| `GET /streaming/account/{account}/full` | `<account id>` with `devices/device(presets, recents)`, `sources`, `providerSettings` |
| `GET /streaming/account/{account}/provider_settings` | static `<providerSettings>` (ELIGIBLE_FOR_TRIAL=false, STREAMING_QUALITY=2) |

After a successful boot sync the speaker does not poll periodically; it calls OCT again on events (playback, preset store, group change).
The speaker rejects an `/full` answer whose root element is not `<account>` ("account expected, but XML was ...") and then fails group creation (error 5580).

## Playback

- Orion/local radio: `GET /core02/svc-bmx-adapter-orion/prod/orion/station?data=...`, `GET /bmx/orion/now-playing`, `POST /bmx/orion/reporting`.
- TuneIn: `GET /bmx/tunein/v1/playback/station/{id}`, `POST /bmx/tunein/v1/reporting/station/{id}`.
- After a station starts the speaker posts `POST /streaming/account/{account}/device/{device}/recent` with
  `<recent><lastplayedat/><sourceid/><name/><location/><contentItemType/></recent>` (`sourceid` is the Marge source id, for example 25 for TuneIn). OCT stores it and answers 201 with the flat `<recent id>` document.
- While OCT is down a TuneIn start fails with `BMX_HTTP_ERROR` (4501); recovery is automatic once OCT is back.

## Stereo pairs

The master forwards the group to `POST /streaming/account/{account}/group/` (trailing slash) and reads `GET /streaming/account/{account}/device/{device}/group/`;
on teardown it calls `DELETE /streaming/account/{account}/group/{id}` (or without id). A group is `<group id><name/><masterDeviceId/><roles><groupRole>(deviceId, role)</groupRole>...</roles></group>`;
no group is `<group/>` with status 200. The master learns the slave from the `ipAddress` of each `groupRole` in `/addGroup`; a `senderIPAddress` in the body marks the receiving speaker as slave.

## Writes the speaker mirrors to Marge

The speaker applies a rename or a preset write only after OCT answered 2xx; on a 404 it keeps the old state, logs the failure and does not retry.

| Speaker request | OCT |
|---|---|
| `PUT .../device/{device}` body `<device deviceid><name/><macaddress/></device>` (rename) | stores the name, 200 with the `<device>` |
| `PUT .../device/{device}/preset/{n}` body `<preset buttonNumber><sourceid/><name/><username/><location/><contentItemType/><containerArt/></preset>` | stores the slot (an Orion location is unwrapped to the stream URL), 200 with the `<preset>` entry |
| `DELETE .../device/{device}/preset/{n}` (also sent first when a new preset duplicates another slot) | removes the slot, 200 |
| `GET .../device/{device}/recents` (read-back after each recent) | `<recents>` as in `/full` |

In `/full` every preset must carry a `<source>` the speaker knows; a preset without it is silently dropped from the speaker's `/presets`.
OCT therefore announces presets of an unknown source (for example `INTERNET_RADIO` imported earlier) as `LOCAL_INTERNET_RADIO`, which is how they play anyway.

Other routes the firmware knows but that were not triggered: `/streaming/support/customersupport`, `/streaming/software/update/account/...`,
`/streaming/music/account/...`, `/streaming/efe/environments`, `/requestToken`, `/navigate`.
