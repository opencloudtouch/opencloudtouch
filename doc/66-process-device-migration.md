# Process: Device Migration

Redirecting a SoundTouch device from Bose Cloud to a local service.

## Migration Decision Tree

```mermaid
flowchart TD
    A[Start Migration] --> B{Telnet:17000<br/>reachable?}
    B -->|Yes| T[Method 4: Telnet]
    B -->|No| C{SSH access<br/>available?}

    C -->|Yes| D{Which method?}
    C -->|No| N[Enable SSH first<br/>→ see 67-process-device-access.md]

    D -->|Recommended| E[Method 1: XML Config]
    D -->|Quick test| F[Method 2: /etc/hosts]
    D -->|Locked firmware| G[Method 3: Binary Patch]

    T --> T1[sys configuration × 4 URLs]
    T1 --> T2[envswitch boseurls set]
    T2 --> T3[getpdo CurrentSystemConfiguration<br/>→ verify]
    T3 --> T4{margeAccountUUID<br/>empty?}
    T4 -->|Yes| T5[envswitch accountid set OR<br/>POST /setMargeAccount]
    T4 -->|No| L[Power-cycle device]
    T5 --> L

    E --> H{Need HTTPS?}
    F --> I[Edit /etc/hosts<br/>→ point domains to local IP]
    G --> J[Patch IsItBose regex<br/>in libBmxAccountHsm.so]

    H -->|No, HTTP OK| K[Edit SoundTouchSdkPrivateCfg.xml<br/>→ set HTTP URLs]
    H -->|Yes| CA[Inject custom CA<br/>→ see 40-tls-and-certificates.md]

    I --> CA
    J --> E

    K --> L
    CA --> L
    L --> M[Verify: device calls<br/>local service at boot]

    style T fill:#c8e6c9
    style E fill:#bbdefb
    style F fill:#fff9c4
    style G fill:#ffcdd2
```

## XML Config Migration (Method 1)

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ST as SoundTouch Speaker
    participant FS as Speaker Filesystem
    participant Local as Local Service

    Note over Admin,Local: Step 1 — Backup
    Admin->>ST: SSH: cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml
    ST-->>Admin: Original config (save as backup!)

    Note over Admin,Local: Step 2 — Read current state
    Admin->>ST: GET /info (port 8090)
    ST-->>Admin: deviceID, presets, sources

    Admin->>ST: GET /presets
    ST-->>Admin: Current presets (backup!)

    Note over Admin,Local: Step 3 — Write new config
    Admin->>ST: SSH: Write SoundTouchSdkPrivateCfg.xml
    Note over FS: <margeServerUrl>http://local-ip:8000</margeServerUrl><br/><statsServerUrl>http://local-ip:8000</statsServerUrl><br/><swUpdateUrl>http://local-ip:8000/updates/soundtouch</swUpdateUrl><br/><bmxRegistryUrl>http://local-ip:8000/bmx/registry/v1/services</bmxRegistryUrl>

    Note over Admin,Local: Step 4 — CA injection (if HTTPS)
    Admin->>ST: SSH: scp ca.crt → append to ca-bundle.crt

    Note over Admin,Local: Step 5 — Reboot
    Admin->>ST: Power cycle (unplug/replug)
    ST->>ST: Boot sequence starts
    ST->>Local: POST /streaming/support/power_on
    Local-->>ST: 200 OK
    ST->>Local: Fetch source availability
    Local-->>ST: TUNEIN, LOCAL_INTERNET_RADIO available

    Note over Admin,Local: Step 6 — Verify
    Admin->>ST: GET /info
    ST-->>Admin: Check margeURL points to local service
    Admin->>Local: Check logs for power_on request
```

## Rollback

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ST as SoundTouch Speaker

    Admin->>ST: SSH: Restore original SoundTouchSdkPrivateCfg.xml
    Admin->>ST: SSH: Remove injected CA from ca-bundle.crt
    Admin->>ST: Power cycle
    ST->>ST: Boot with original Bose cloud URLs
    Note over ST: Device back to factory cloud config
```

## Telnet:17000 Migration (Method 4 — No SSH)

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ST as SoundTouch Speaker (port 17000)
    participant API as Speaker HTTP API (port 8090)
    participant Local as Local Service

    Note over Admin,Local: Preflight
    Admin->>ST: TCP connect :17000 (timeout 2s)
    ST-->>Admin: Banner / prompt
    Admin->>ST: getpdo CurrentSystemConfiguration
    ST-->>Admin: Current URLs (verify shell works)

    Admin->>API: GET /info
    API-->>Admin: deviceID, margeAccountUUID

    Note over Admin,Local: URL Configuration (send one-by-one, wait for OK)
    Admin->>ST: sys configuration margeServerUrl http://local:8000
    ST-->>Admin: OK
    Admin->>ST: sys configuration statsServerUrl http://local:8000
    ST-->>Admin: OK
    Admin->>ST: sys configuration bmxRegistryUrl http://local:8000/bmx/registry/v1/services
    ST-->>Admin: OK
    Admin->>ST: sys configuration swUpdateUrl http://local:8000/updates/soundtouch
    ST-->>Admin: OK
    Admin->>ST: envswitch boseurls set http://local:8000 http://local:8000/updates/soundtouch
    ST-->>Admin: OK

    Note over Admin,Local: Verify
    Admin->>ST: getpdo CurrentSystemConfiguration
    ST-->>Admin: Updated URLs (confirm all 4 changed)

    Note over Admin,Local: Account Pairing (if needed)
    alt margeAccountUUID empty
        Admin->>API: POST /setMargeAccount (5s timeout)
        alt HTTP works
            API-->>Admin: 200 OK
        else HTTP fails / missing / hangs
            Admin->>ST: envswitch accountid set 1234567
            ST-->>Admin: OK
        end
    end

    Note over Admin,Local: Reboot (manual!)
    Admin->>Admin: Power-cycle device (unplug/replug)
    ST->>Local: POST /streaming/support/power_on
    Local-->>ST: 200 OK
    Note over Admin: Migration complete
```

## Method Comparison

```mermaid
quadrantChart
    title Migration Methods
    x-axis Low Risk --> High Risk
    y-axis Low Effort --> High Effort
    XML Config: [0.2, 0.3]
    /etc/hosts: [0.4, 0.15]
    Binary Patch: [0.85, 0.8]
    Triple Threat: [0.95, 0.95]
```
