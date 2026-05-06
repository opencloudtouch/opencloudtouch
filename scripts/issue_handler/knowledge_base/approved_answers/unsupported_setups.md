---
tags: [proxmox, lxc, vm, virtualization]
---
# Unsupported Setups

Thank you for your interest in OpenCloudTouch! Unfortunately, running OpenCloudTouch inside **Proxmox LXC containers** or similar virtualized environments is **not supported**.

## Why?

OpenCloudTouch relies on **SSDP multicast discovery** to find Bose SoundTouch speakers on your network. Virtualization platforms like Proxmox LXC do not forward multicast traffic by default, which prevents device discovery from working.

## Recommended Setup

For the best experience, we recommend running OpenCloudTouch on:

- **Raspberry Pi** (any model with network access)
- **Docker on a host with direct network access** (using `--network host`)
- **Any Linux system** with direct access to the same network as your speakers

If you have questions about supported setups, please open a new issue describing your environment.
