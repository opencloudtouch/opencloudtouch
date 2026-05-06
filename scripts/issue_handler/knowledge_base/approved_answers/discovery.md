---
tags: [discovery, ssdp, multicast, not-found, network]
---
# Device Discovery Troubleshooting

Having trouble finding your Bose SoundTouch speakers? Here are some common solutions:

## Check Network Configuration

1. **Same network**: Make sure your speakers and the OpenCloudTouch host are on the **same network/VLAN**
2. **Multicast support**: Your network must support **SSDP multicast** (UDP port 1900)
3. **Firewall**: Ensure UDP ports **1900** (SSDP) and **5353** (mDNS) are not blocked

## Docker Users

If running in Docker, you **must** use host networking:

```bash
docker run --network host ...
```

Bridge networking will not forward multicast traffic.

## Manual Discovery

If automatic discovery fails, you can check if your speakers are reachable:

```bash
# Check if speaker responds to HTTP
curl http://<speaker-ip>:8090/info
```

## Still Not Working?

- Restart your speakers (power cycle)
- Check if the speaker firmware is up to date
- Try accessing the speaker directly via its IP address
- Review your router's multicast/IGMP settings
