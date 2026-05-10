# Music Services & Content Navigation

Account management, station search, content browsing for streaming services.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [sources/](../sources/README.md), [12-spotify-account-flow.md](../12-spotify-account-flow.md)

---

## Account Management

### POST /setMusicServiceAccount

Register a music service account on the device:

```xml
<credentials source="SPOTIFY" displayName="user@example.com">
  <token value="oauth-token-here"/>
</credentials>
```

Response: `<status>/setMusicServiceAccount</status>`

Used for: AMAZON, DEEZER, PANDORA, SIRIUSXM.

---

### POST /setMusicServiceOAuthAccount

OAuth-based account registration (Spotify Connect):

```xml
<setMusicServiceOAuthAccount>
  <credentials source="SPOTIFY" token="oauth-token"/>
</setMusicServiceOAuthAccount>
```

→ Full Spotify flow: [12-spotify-account-flow.md](../12-spotify-account-flow.md)

---

### POST /removeMusicServiceAccount

Remove a registered music service:

```xml
<credentials source="SPOTIFY" sourceAccount="user@example.com"/>
```

---

### GET /introspect

Query registered accounts and sync state. Similar to `/marge` but service-focused.

→ See also: [cloud/ § /marge](../cloud/README.md)

---

## Station Management

### POST /searchStation

Search for radio stations within a music service:

```xml
<search source="TUNEIN" sourceAccount="">
  <searchTerm>Bayern 3</searchTerm>
</search>
```

Returns station list with ContentItems.

---

### POST /addStation

Add a station to favorites:

```xml
<ContentItem source="TUNEIN" type="stationurl"
  location="/v1/playback/station/s14991" sourceAccount="">
  <itemName>Bayern 3</itemName>
</ContentItem>
```

---

### POST /removeStation

Remove a station from favorites. Same body structure as `/addStation`.

---

### GET /genreStations

Browse stations by genre. Returns genre categories with nested station lists.

---

### GET /stationInfo

Detailed metadata for a specific station. Takes station location as parameter.

---

### GET /trackInfo

Extended track information for currently playing music service content.

**Warning**: Times out (~30s) on non-music-service content (AIRPLAY, STORED_MUSIC).
Returns semicolon-delimited metadata string.

---

## Content Navigation

### POST /search

Generic content search across sources:

```xml
<search source="TUNEIN" sourceAccount="">
  <searchTerm>rock</searchTerm>
</search>
```

Different from `/searchStation` — searches across albums, artists, playlists, not just stations.

---

### POST /navigate

Browse content hierarchy within a source:

```xml
<navigate source="STORED_MUSIC"
  sourceAccount="4d696e69-444c-164e-9d41-b42e99ad6c47/0"
  location="1$7"/>
```

Returns child items at the given location path. Used for DLNA/UPnP browsing.

---

### POST /bookmark

Bookmark current track/station:

```xml
<bookmark/>
```

Equivalent to `POST /key` with `BOOKMARK`. Persists across services that support it.
