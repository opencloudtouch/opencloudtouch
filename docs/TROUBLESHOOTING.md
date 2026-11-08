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

## ARM NAS with a 32 KB page size (WD My Cloud, QNAP)

Some ARMv7 NAS kernels use 32 KB memory pages instead of the usual 4 KB. The `linux/arm/v7` image ships its libraries aligned for 64 KB, so it also starts on these devices. The entrypoint runs a short library self-test when it detects a 32 KB page size. It was verified on a WD My Cloud EX2 Ultra (kernel 4.14, Docker 20.10.14 and 19.03.8).

- **Docker 20.10.9 or newer:** nothing to configure.
- **Docker older than 20.10.9** (for example the 19.03.8 that WD ships): the default seccomp profile answers system calls it does not know with `EPERM` instead of `ENOSYS`. Newer C libraries then cannot fall back to the old calls, and Python fails with `OSError: [Errno 75] Value too large for defined data type` or `Operation not permitted` while importing `time`. Either update Docker, or start the container with the profile [`deployment/seccomp-legacy-docker.json`](../deployment/seccomp-legacy-docker.json):

  ```bash
  docker run --security-opt seccomp=/path/to/seccomp-legacy-docker.json ...
  ```

  or in Compose:

  ```yaml
  security_opt:
    - seccomp=./seccomp-legacy-docker.json
  ```

  The profile allows all system calls by default and blocks the dangerous ones that Docker's own profile blocks (mount, ptrace, namespaces, kernel modules, and so on). It is weaker than Docker's allow-list profile but much stronger than `seccomp=unconfined`. Use it only on old kernels (below 5.3): it relies on the kernel answering `ENOSYS` for system calls it does not have.

If the self-test fails, the container stops with `library self-test failed`. Please open a bug report and include `getconf PAGE_SIZE`, `uname -a` and `docker version`.

## Still stuck?

Open a [bug report](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml) or check [GitHub Discussions](https://github.com/opencloudtouch/opencloudtouch/discussions).
