---
tags: [docker, install, setup, raspberry-pi, container]
---
# Installation Guide

Welcome to OpenCloudTouch! Here's how to get started:

## Quick Start with Docker

```bash
# Pull the stable image (recommended)
docker pull ghcr.io/opencloudtouch/opencloudtouch:stable

# Run with host networking (required for SSDP discovery)
docker run -d \
  --name opencloudtouch \
  --network host \
  --restart unless-stopped \
  ghcr.io/opencloudtouch/opencloudtouch:stable
```

## Docker Compose

Create a `docker-compose.yml`:

```yaml
services:
  opencloudtouch:
    image: ghcr.io/opencloudtouch/opencloudtouch:stable
    network_mode: host
    restart: unless-stopped
```

Then run:

```bash
docker compose up -d
```

## After Installation

Once running, open your browser and navigate to `http://<your-host-ip>:8080` to access the web interface.

For more details, see the [README](https://github.com/opencloudtouch/opencloudtouch#readme).
