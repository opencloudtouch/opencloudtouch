# Audio Controls

Volume, bass, balance, DSP, tone EQ, speaker levels, and audio sync.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [01-api-endpoints.md § Volume Control](../01-api-endpoints.md)

---

## GET /volume

```xml
<volume deviceID="B92C7D383488">
  <targetvolume>10</targetvolume>
  <actualvolume>10</actualvolume>
  <muteenabled>false</muteenabled>
</volume>
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `targetvolume` | int | 0-100 | Requested volume level |
| `actualvolume` | int | 0-100 | Current hardware volume (ramps to target) |
| `muteenabled` | boolean | — | Mute state |

**POST** `/volume`: `<volume>50</volume>`

---

## GET /bass

```xml
<bass deviceID="B92C7D383488">
  <targetbass>0</targetbass>
  <actualbass>0</actualbass>
</bass>
```

**POST** `/bass`: `<bass>-5</bass>` — value must be within `/bassCapabilities` range.

---

## GET /bassCapabilities

```xml
<bassCapabilities deviceID="B92C7D383488">
  <bassAvailable>true</bassAvailable>
  <bassMin>-9</bassMin>
  <bassMax>0</bassMax>
  <bassDefault>0</bassDefault>
</bassCapabilities>
```

Range varies by model. Always check before setting bass.

---

## GET /balance

```xml
<balance deviceID="B92C7D383488">
  <balanceAvailable>true</balanceAvailable>
  <balanceMin>-7</balanceMin>
  <balanceMax>7</balanceMax>
  <balanceDefault>0</balanceDefault>
  <targetBalance>0</targetBalance>
  <actualBalance>0</actualBalance>
</balance>
```

**POST** `/balance`: `<balance><targetBalance>3</targetBalance></balance>`

**Note**: ST30 returns `balanceAvailable=false` — no stereo balance on mono speakers.

---

## GET /DSPMonoStereo

```xml
<DSPMonoStereo>
  <mono enable="false"/>
</DSPMonoStereo>
```

Toggle mono/stereo output. Only available if `capabilities.dspMonoStereo.available=true`.

**POST** `/DSPMonoStereo`: `<DSPMonoStereo><mono enable="true"/></DSPMonoStereo>`

---

## GET /audiodspcontrols *(ST300 only)*

```xml
<audiodspcontrols audiomode="AUDIO_MODE_NORMAL" videosyncaudiodelay="0">
</audiodspcontrols>
```

| Field | Values | Description |
|-------|--------|-------------|
| `audiomode` | `AUDIO_MODE_NORMAL`, `AUDIO_MODE_DIALOG` | Dialog enhancement mode |
| `videosyncaudiodelay` | int (ms) | Lip-sync delay compensation |

---

## GET /audioproducttonecontrols *(ST300 only)*

Advanced tone EQ beyond `/bass`:

```xml
<audioproducttonecontrols>
  <bass value="50" min="-100" max="100" step="1"/>
  <treble value="0" min="-100" max="100" step="1"/>
</audioproducttonecontrols>
```

**POST**: Same structure with desired values.

---

## GET /audioproductlevelcontrols *(ST300 only)*

Multi-speaker level adjustment:

```xml
<audioproductlevelcontrols>
  <frontCenterSpeakerLevel value="0" min="-100" max="100" step="1"/>
  <rearSurroundSpeakersLevel value="0" min="-100" max="100" step="1"/>
</audioproductlevelcontrols>
```

---

## POST /speaker

TTS or audio notification playback:

```xml
<play_info>
  <url>http://translate.google.com/translate_tts?ie=UTF-8&amp;tl=EN&amp;client=tw-ob&amp;q=Hello</url>
  <app_key>YOUR_APP_KEY</app_key>
  <service>TTS Notification</service>
  <message>Google TTS</message>
  <reason>Hello World</reason>
  <volume>70</volume>
</play_info>
```

GET returns `400 Bad Request` — POST-only endpoint.

→ See [51-undocumented-features.md](../51-undocumented-features.md) for TTS usage.

---

## GET /rebroadcastlatencymode

Multiroom audio synchronization:

```xml
<rebroadcastlatencymode>
  <mode>SYNC_TO_ZONE</mode>
  <controllable>true</controllable>
</rebroadcastlatencymode>
```

| Mode | Description |
|------|-------------|
| `SYNC_TO_ZONE` | Sync audio with zone master |
| `LATENCY_MODE_NORMAL` | Default latency |
| `LATENCY_MODE_LOW` | Low latency (may cause sync issues in zones) |

→ See [zones/](../zones/README.md) for multiroom zone control.
