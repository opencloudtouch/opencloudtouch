---
tags: [upgrade, update, migration, version, breaking-change]
---
# Upgrading OpenCloudTouch

## Docker Upgrade (recommended)

```bash
# Pull the newest stable version
docker pull ghcr.io/opencloudtouch/opencloudtouch:stable

# Stop and remove the old container
docker stop opencloudtouch
docker rm opencloudtouch

# Start fresh (your config volume persists)
docker run -d \
  --name opencloudtouch \
  --network host \
  --restart unless-stopped \
  ghcr.io/opencloudtouch/opencloudtouch:stable
```

Or with Docker Compose:

```bash
docker compose pull
docker compose up -d
```

## Before You Upgrade

1. **Check the release notes** in [CHANGELOG.md](https://github.com/opencloudtouch/opencloudtouch/blob/main/CHANGELOG.md) for breaking changes.
2. **Backup your config** — your mounted volume (`/app/config`, `/app/presets`) should be safe, but better safe than sorry.

## Breaking Changes

Starting with v1.4.1, device setup uses **SSH instead of Telnet** for setting the account UUID. If you have custom firewall rules allowing only Telnet (port 23), you'll need to also allow SSH (port 22) to the speaker.

## Raspberry Pi

For Raspberry Pi image upgrades, flash the latest image and restore your configuration from backup. See [UPGRADING.md](https://github.com/opencloudtouch/opencloudtouch/blob/main/UPGRADING.md) for details.

## Troubleshooting

- Container won't start after upgrade? Check logs: `docker logs opencloudtouch`
- Presets missing? Verify your volume mount points haven't changed.
- Still stuck? Open an issue with your old and new version numbers.
