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

Some ARMv7 NAS kernels use 32 KB memory pages instead of the usual 4 KB. The `linux/arm/v7` image ships its libraries aligned for 64 KB, so the same image starts on 4 KB, 32 KB and 64 KB kernels. When the entrypoint detects a 32 KB page size it runs a short library self-test and logs `library self-test passed`.

### Supported platforms (by model series)

| Series | Image | Status |
|--------|-------|--------|
| Raspberry Pi 2/3 (4 KB pages) | `linux/arm/v7` | Supported; behaviour unchanged |
| ARM NAS with 32 KB pages, reference device WD My Cloud EX2 Ultra (kernel 4.14) | `linux/arm/v7` | Supported; verification on Docker 20.10.x and 19.03.x: **pending verification** |
| amd64 / arm64 hosts | `linux/amd64`, `linux/arm64` | Supported; unchanged |

Other NAS models are added after feedback in the discussion [NAS compatibility reports](https://github.com/opencloudtouch/opencloudtouch/discussions/637). Raspberry Pi 1 and Zero (ARMv6) are not covered.

### Docker version

- **Docker 20.10.9 or newer:** minimum for configuration-free operation on every platform. Nothing to configure.
- **Docker 19.03.8 up to 20.10.8** (for example the 19.03.8 that WD ships): recommended minimum for the legacy path; needs a seccomp profile, see below.
- **Docker 19.03.3 and similar early 19.03 releases:** `docker pull` fails with `mediaType in manifest should be 'application/vnd.docker.distribution.manifest.v2+json' not 'application/vnd.oci.image.manifest.v1+json'`. This is not supported and has not been tested beyond the pull, but it works with the workaround [Importing the image with `docker load`](#importing-the-image-with-docker-load) plus the seccomp profile.
- **Docker older than 19.03:** not supported.

On Docker older than 20.10.9 the default seccomp profile answers system calls it does not know with `EPERM` instead of `ENOSYS`. The C library of the image only falls back to the old calls on `ENOSYS`, so Python fails with errors like `Operation not permitted` or `OSError: [Errno 75]` while importing `time`. Either update Docker, or start the container with the profile [`seccomp-legacy-docker.json`](https://github.com/opencloudtouch/opencloudtouch/releases/latest/download/seccomp-legacy-docker.json) (also in the repository as [`deployment/seccomp-legacy-docker.json`](../deployment/seccomp-legacy-docker.json)):

```bash
docker run --security-opt seccomp=/path/to/seccomp-legacy-docker.json ...
```

or in a Compose file:

```yaml
security_opt:
  - seccomp=./seccomp-legacy-docker.json
```

The `docker` command-line client reads the profile file itself and sends its content to the Docker daemon, so the path only has to be valid on the machine where you run the command.

**Portainer:** a stack is deployed by Portainer's own container, and that container reads the profile file, not your NAS shell. A path that exists only on the NAS fails with "no such file or directory". Put the file where the Portainer container can see it, for example into the folder that is mounted as Portainer's `/data`, and use the path as Portainer sees it:

```yaml
services:
  opencloudtouch:
    image: ghcr.io/opencloudtouch/opencloudtouch:<version>
    network_mode: host
    security_opt:
      - seccomp=/data/seccomp-legacy-docker.json
```

The profile does not have to be mounted into the OpenCloudTouch container.

**Docker Compose on the command line (no Portainer):** with Docker Compose v2 or newer (a single binary, for example `docker-compose-linux-armv7`), `seccomp=./seccomp-legacy-docker.json` (relative to the Compose file) and an absolute path both work on Docker 19.03.8; Compose reads the file and passes its content to the daemon. Without the `security_opt` line the container exits at once with the hint about Docker older than 20.10.9.

### Importing the image with `docker load`

Use this when `docker pull` is not possible (for example on Docker 19.03.3). On a computer with a current Docker or Podman, in an empty working folder:

```bash
podman pull --platform linux/arm/v7 ghcr.io/opencloudtouch/opencloudtouch:<version>
podman save --format docker-archive -o opencloudtouch-armv7.tar ghcr.io/opencloudtouch/opencloudtouch:<version>
```

Copy `opencloudtouch-armv7.tar` to the NAS and run:

```bash
docker load -i opencloudtouch-armv7.tar
```

Then start the container with the image tag as usual, together with the seccomp profile. Use a `docker-archive`, not an OCI archive: the OCI format is the one old Docker versions cannot read.

The profile allows all system calls by default and blocks the dangerous ones that Docker's own profile blocks (mount, ptrace, namespaces, kernel modules, and so on). It is a deny-list: it is weaker than Docker's default allow-list profile but much stronger than `seccomp=unconfined`, and it does not block dangerous system calls that newer kernels add. Use it **only on old kernels (below 5.3)** and only on Docker older than 20.10.9; it is not needed and not recommended on Docker 20.10.9 or newer.

### Troubleshooting path

1. Collect the facts: `getconf PAGE_SIZE`, `uname -a` and `docker version` (client and server).
2. Match the container log:
   - `library self-test passed`: the image works, look elsewhere (network mode, ports).
   - `library self-test failed` with the hint about Docker older than 20.10.9: update Docker or use the profile above.
   - `OCT_SKIP_PAGE_SIZE_CHECK=1 is set`: the self-test was skipped on purpose, remove the variable unless you know you need it.
3. Try the fix from step 2 (Docker update or the profile) and restart the container.
4. Still failing? Open a [bug report](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml) and attach: the output of step 1, the full container log (`docker logs <container>`), your `docker run` or Compose settings without secrets, and the device model. Do not include tokens, passwords or personal data.

## Still stuck?

Open a [bug report](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml) or check [GitHub Discussions](https://github.com/opencloudtouch/opencloudtouch/discussions).
