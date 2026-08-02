# Troubleshooting

## Common Problems

| Problem | Solution |
|---------|----------|
| Container won't start | `docker compose -f deployment/docker-compose.yml logs opencloudtouch` |
| Devices not found | Ensure `network_mode: host` and same network; use `OCT_MANUAL_DEVICE_IPS` as fallback (see [Configuration](CONFIGURATION.md#discovery--device-polling)) |
| Port 7777 in use | `OCT_PORT=8080 docker compose -f deployment/docker-compose.yml up -d` |
| Health check fails | `docker exec opencloudtouch curl -f http://localhost:7777/health` — check the response and container logs for the actual error |
| Devices mostly offline, polling noise in logs | Set `OCT_DEVICE_POLLING_ENABLED=false` (see [Configuration](CONFIGURATION.md#discovery--device-polling)) |
| "Update available" shown for a self-built image | Expected to no longer happen — self-built images report `build: "community"` on `/health` and the update check is skipped entirely for them. If you still see it, check that you're on a build that includes the fix (>= the release that closed the negative-dentry-growth issue). |

## Understanding `docker stats` memory numbers

`docker stats` MEM USAGE includes the container's kernel page cache and dentry/inode slab caches, not just the application's own memory. These caches are reclaimable by the kernel under memory pressure and are expected to grow over time — **this is not a leak**.

For the application's actual memory usage, use `rss_mb` from `GET /api/diagnostics/memory` instead — that's the number that reflects what the Python process itself is using.

To confirm reclaimable memory is behind a high `docker stats` number (diagnostic only — **not** a recommended workaround, it doesn't fix anything and the caches simply refill):

```bash
sync; echo 2 > /proc/sys/vm/drop_caches
```

If `docker stats` drops sharply after this while `rss_mb` stays unchanged, the growth was reclaimable kernel cache, not an application memory leak.

### Related diagnostics

```bash
# Dentry/inode cache state
cat /proc/sys/fs/dentry-state

# Slab allocator breakdown (look for the "dentry" row)
grep ^dentry /proc/slabinfo

# Full cgroup memory breakdown, including slab_reclaimable
docker exec <container> cat /sys/fs/cgroup/memory.stat  # cgroup v2
```

## Build & Deployment

See [`deployment/README.md`](../deployment/README.md) (Troubleshooting section) for build-specific issues (SSDP inside containers, SSH errors to a remote deploy target, cache invalidation).

## Still stuck?

Open a [bug report](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml) or check [GitHub Discussions](https://github.com/opencloudtouch/opencloudtouch/discussions).
