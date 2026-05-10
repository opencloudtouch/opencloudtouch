# Spotify Account Addition — Technical Flow

Detailed request/response flow for adding a Spotify account to a SoundTouch device.
Based on analysis of Stockholm firmware `27.0.13-4277-8963611`.

## Flow Overview

```
1. User Auth → Spotify login in browser
2. Redirect   → App intercepts auth code
3. Token Exchange → Bose OAuth proxy exchanges code for Bose-mediated token
4. Cloud Registration → Register source in Bose Marge account
5. Device Sync → Notify local speaker about new source
```

---

## Step 0: User Authorization

### App Opens Browser
- **URL**: `https://accounts.spotify.com/authorize`
- **Params**:
  - `client_id` = Bose Spotify Client ID
  - `response_type` = `code`
  - `redirect_uri` = `http://localhost`
  - `scope` = `user-read-private user-read-email ...`
  - `state` = Base64-encoded JSON: `{"service": "SPOTIFY"}`

### Browser Redirects Back
After user authorizes, Spotify redirects to:
```
soundtouch://bose/musicservice/spotify/login?code=[AUTH_CODE]&state=[STATE]
```

The Stockholm UI (`ui_main.js`) intercepts this deep link and extracts the `code`.

---

## Step 1: OAuth Token Exchange (Bose Cloud)

### What is a "Bose-mediated token"?

The token is **not** a direct Spotify refresh token. Instead:
- Bose's OAuth proxy performs the actual OAuth2 exchange with Spotify
- It returns a Bose-issued token representing the Spotify session
- **token_version_3**: Modern firmware uses this type — the device doesn't store
  raw Spotify tokens, but a Bose "secret" that the cloud uses to fetch fresh
  Spotify access tokens on the device's behalf
- The initial response contains an `access_token` (valid ~1 hour) and `token_type: "Bearer"`
- Bose cloud manages the persistent refresh token internally

### Request

```
POST https://oauth.streaming.bose.com/oauth/account/[ACCOUNT_ID]/music/musicprovider/15/token/cs
Content-Type: application/json
Authorization: Bearer [SESSION_TOKEN]
```

```json
{
  "grant_type": "authorization_code",
  "code": "[AUTH_CODE_FROM_SPOTIFY]",
  "redirect_uri": "http://localhost"
}
```

### curl Example

```bash
curl -X POST \
  "https://oauth.streaming.bose.com/oauth/account/[ACCOUNT_ID]/music/musicprovider/15/token/cs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer [SESSION_TOKEN]" \
  -d '{
    "grant_type": "authorization_code",
    "code": "[AUTH_CODE]",
    "redirect_uri": "http://localhost"
  }'
```

---

## Step 2: Cloud Source Registration (Marge)

Register the Spotify account as a source in the user's Bose Cloud profile.

### Request

```
POST https://streaming.bose.com/streaming/account/[ACCOUNT_ID]/source
Content-Type: application/vnd.bose.streaming-v1.1+xml
Authorization: [MARGE_TOKEN]
GUID: [DEVICE_GUID]
ClientType: Stockholm
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<source>
    <username>[SPOTIFY_USER_ID]</username>
    <sourceproviderid>15</sourceproviderid>
    <credential type="token_version_3">[SECRET_TOKEN_FROM_STEP_1]</credential>
    <sourcename>[DISPLAY_NAME]</sourcename>
</source>
```

---

## Step 3: Local Device Sync (LISA API)

Notify the speaker about the new source via port 8090.

### Modern Flow (OAuth)
```
POST http://[DEVICE_IP]:8090/setMusicServiceOAuthAccount
```

```xml
<OAuthCredentials source="SPOTIFY" displayName="[DISPLAY_NAME]">
    <user>[SPOTIFY_USER_ID]</user>
    <code>[AUTH_CODE_OR_TOKEN]</code>
    <version>token_version_3</version>
</OAuthCredentials>
```

### Marge-Sync Notification (fallback)
If the speaker returns `1029 UNKNOWN_ACTION_ERROR` (LISA API too old):
```
POST http://[DEVICE_IP]:8090/notification
```

```xml
<updates deviceID="[DEVICE_UID]">
    <sourcesUpdated></sourcesUpdated>
</updates>
```

### Legacy Flow (oldest firmware)
```
POST http://[DEVICE_IP]:8090/setMusicServiceAccount
```

```xml
<credentials source="SPOTIFY" displayName="Spotify Premium">
    <user>[USER]</user>
    <pass>[TOKEN]</pass>
</credentials>
```

---

## Device-Side Persistence

After successful registration, the device stores credentials at:
```
/mnt/nv/BoseApp-Persistence/1/Sources.xml
```

```xml
<source displayName="user@example.com" secret="[SECRET_BLOB]" secretType="token_version_3">
    <sourceKey type="SPOTIFY" account="user" />
</source>
```

---

## Constants

| Placeholder | Description |
|-------------|-------------|
| `[ACCOUNT_ID]` | Internal Bose account ID (UUID) |
| `[SESSION_TOKEN]` | Temporary token from Bose login |
| `[MARGE_TOKEN]` | Persistent auth token for Marge services |
| `[DEVICE_GUID]` | Unique identifier for the controller app instance |
| `[DEVICE_IP]` | Local IP of the SoundTouch speaker |
| `15` | Constant `sourceproviderid` for Spotify |
| `token_version_3` | Credential type for modern OAuth2 Spotify accounts |

---

## For Local Emulation (no Bose Cloud)

When emulating this flow locally:

1. **Surrogate secrets**: Generate a 32-char hex string as a "Bose Secret"
2. **Marge + LISA registration**: Send this secret to the speaker and store in emulated Marge
3. **Token refresh proxy**: When speaker needs fresh Spotify `access_token`:
   - Speaker calls `/oauth/device/.../token/cs3` with the secret
   - Local server maps secret → real Spotify account → performs refresh → returns access_token
   - Raw Spotify refresh token **never leaves the server**
