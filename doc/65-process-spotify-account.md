# Process: Spotify Account Addition

Full OAuth flow to add Spotify to a SoundTouch device.

## Complete Flow

```mermaid
sequenceDiagram
    participant User as User (Browser)
    participant App as Bose App / Stockholm UI
    participant Spotify as accounts.spotify.com
    participant BoseOAuth as oauth.streaming.bose.com
    participant Marge as streaming.bose.com
    participant ST as SoundTouch Speaker
    participant FS as Speaker Filesystem

    Note over User,FS: Step 0 — User Authorization
    App->>User: Open Spotify login page<br/>client_id=Bose_ID, scope=user-read-private...
    User->>Spotify: Login + Authorize
    Spotify-->>App: Redirect: soundtouch://bose/.../login?code=AUTH_CODE

    Note over User,FS: Step 1 — Token Exchange (Bose Cloud)
    App->>BoseOAuth: POST /oauth/account/{accountId}/music/musicprovider/15/token/cs<br/>{"grant_type":"authorization_code","code":"AUTH_CODE"}
    BoseOAuth->>Spotify: Exchange code for tokens (server-side)
    Spotify-->>BoseOAuth: access_token + refresh_token
    BoseOAuth-->>App: Bose-mediated token (token_version_3)<br/>access_token + SECRET

    Note over User,FS: Step 2 — Cloud Source Registration (Marge)
    App->>Marge: POST /streaming/account/{accountId}/source<br/>XML: <source><username>SPOTIFY_USER</username><br/>  <sourceproviderid>15</sourceproviderid><br/>  <credential type="token_version_3">SECRET</credential></source>
    Marge-->>App: 200 OK — Source registered

    Note over User,FS: Step 3 — Device Sync (Local API)
    App->>ST: POST /setMusicServiceOAuthAccount (port 8090)<br/>XML: <OAuthCredentials source="SPOTIFY"><br/>  <user>SPOTIFY_USER</user><br/>  <code>AUTH_CODE_OR_TOKEN</code><br/>  <version>token_version_3</version></OAuthCredentials>
    ST->>FS: Store credentials in<br/>/mnt/nv/BoseApp-Persistence/1/Sources.xml
    ST-->>App: 200 OK

    alt LISA API too old (error 1029)
        App->>ST: POST /notification<br/><updates><sourcesUpdated/></updates>
        ST->>Marge: Fetch updated sources
    end

    Note over ST: Spotify now available in /sources
```

## Token Refresh Flow (Runtime)

```mermaid
sequenceDiagram
    participant ST as SoundTouch Speaker
    participant OAuth as oauth.streaming.bose.com
    participant Spotify as Spotify API

    ST->>OAuth: POST /oauth/device/{deviceId}/music/<br/>musicprovider/15/token/cs3<br/>(with stored SECRET)
    OAuth->>Spotify: Refresh access_token<br/>(using stored refresh_token)
    Spotify-->>OAuth: New access_token (1h validity)
    OAuth-->>ST: Fresh access_token
    ST->>Spotify: Stream music with new token
```

## Token Architecture

```mermaid
flowchart TD
    subgraph "Bose Cloud (Mediator)"
        A[Bose OAuth Proxy]
        B[Real Spotify refresh_token<br/>stored server-side]
    end

    subgraph "SoundTouch Speaker"
        C[Bose SECRET<br/>token_version_3]
    end

    subgraph "For Local Emulation"
        D[Generate surrogate 32-char hex SECRET]
        E[Map SECRET → Spotify account]
        F[Token refresh proxy:<br/>SECRET → real refresh → access_token]
        G[Raw refresh_token never leaves server]
    end

    C -->|"POST .../token/cs3"| A
    A --> B
    B -->|"OAuth2 refresh"| H[Spotify API]

    style B fill:#ffcdd2
    style G fill:#c8e6c9
```

## Constants

| Value | Meaning |
|-------|---------|
| `15` | Spotify `sourceproviderid` |
| `token_version_3` | Modern OAuth credential type |
| `soundtouch://bose/...` | Deep link redirect URI |
| `http://localhost` | OAuth redirect URI |
