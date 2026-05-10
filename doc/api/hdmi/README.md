# HDMI Controls (ST300 Only)

HDMI-CEC control and input assignment. Available exclusively on SoundTouch 300.

→ Parent: [API Schema Reference](../api/README.md)

---

## GET /productcechdmicontrol

HDMI-CEC mode:

```xml
<productcechdmicontrol>
  <cecmode>CEC_MODE_ON</cecmode>
</productcechdmicontrol>
```

| Mode | Description |
|------|-------------|
| `CEC_MODE_ON` | CEC active — TV remote controls volume |
| `CEC_MODE_OFF` | CEC disabled |
| `CEC_MODE_ALT` | Alternative CEC mode (compatibility) |

**POST**: `<productcechdmicontrol><cecmode>CEC_MODE_OFF</cecmode></productcechdmicontrol>`

---

## GET /producthdmiassignmentcontrols

HDMI input button mapping:

```xml
<producthdmiassignmentcontrols>
  <hdmiinputselection_01>HDMI_IN_BUTTON_NONE</hdmiinputselection_01>
</producthdmiassignmentcontrols>
```

| Value | Description |
|-------|-------------|
| `HDMI_IN_BUTTON_NONE` | No button assigned to HDMI input |
| `HDMI_IN_BUTTON_TV` | TV button selects this HDMI input |
| `HDMI_IN_BUTTON_1` .. `HDMI_IN_BUTTON_4` | Source buttons |

The ST300 has HDMI ARC input for TV audio. These controls map which remote button switches to the HDMI input.
