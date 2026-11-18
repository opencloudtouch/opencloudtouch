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

## Self-update problems

| Problem | Solution |
|---------|----------|
| Docker socket or permission error | Verify that `/var/run/docker.sock` is mounted into the OpenCloudTouch container. |
| Update returns `409` | An update is already running, no newer official release is available, or the submitted `target_version` does not exactly match the latest release. Check `/api/system/update-status` and `/api/system/check-update`. |
| Status is `rolled_back` | The new image failed to start or become healthy. The previous immutable image was restored automatically. Check the OpenCloudTouch update status and host Docker logs for the recorded failure. |
| Status is `failed` | The update or recovery process could not complete. Check the Docker and OpenCloudTouch logs before retrying. |
| Community/self-built image is not updated automatically | Expected. Automatic replacement with an official image is disabled for community builds. |

During self-update, the replacement container inherits the healthcheck from the
target image. Docker Compose healthcheck overrides, including
`test: ["NONE"]`, are not preserved and revert to the image default.

The update helper currently requires the Docker socket at
`/var/run/docker.sock` on the host. Rootless Docker and installations using a
different host-side socket path are not currently supported.

Self-update errors may expose technical details through the API response and
persisted update status. Access to the API should therefore be limited to
trusted networks.

The existing `/data` mount is preserved during container replacement and
rollback. Do not delete Docker volumes while diagnosing an update problem.
Active states older than 30 minutes are treated as stale automatically. A
running replacement without a Docker healthcheck is checked for stability only
during a fixed grace period of approximately 10 seconds. `RestartCount` detects
restarts handled by Docker's restart policy, but stability beyond this window
is not guaranteed. Stopped or explicitly unhealthy containers still trigger rollback.


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

## ARM NAS with a 32 KB page size

Some ARMv7 NAS kernels use 32 KB memory pages instead of the usual 4 KB. The `linux/arm/v7` image ships its libraries aligned for 64 KB, so the same image starts on 4 KB, 32 KB and 64 KB kernels. When the entrypoint detects a 32 KB page size it runs a short library self-test and logs `library self-test passed`.

### Supported platforms (by model series)

| Series | Image | Status |
|--------|-------|--------|
| Raspberry Pi 2/3 (4 KB pages) | `linux/arm/v7` | Supported; behaviour unchanged. Verified on a Raspberry Pi 2 Model B (4 KB pages, Docker 29.9.3): container healthy, no self-test in the log. |
| ARM NAS with 32 KB pages, reference device WD My Cloud EX2 Ultra (kernel 4.14) | `linux/arm/v7` | Supported; verified on Docker 19.03.8 (with the legacy seccomp profile) and Docker 29.9.3 (without a profile, needs `--allow-direct-routing`); Docker 20.10.14 worked without a profile |
| amd64 / arm64 hosts | `linux/amd64`, `linux/arm64` | Supported; unchanged |

Other NAS models are added after feedback in the discussion [NAS compatibility reports](https://github.com/opencloudtouch/opencloudtouch/discussions/637). Raspberry Pi 1 and Zero (ARMv6) are not covered.

### Docker version

- **Docker 20.10.9 or newer:** minimum for configuration-free operation on every platform. Nothing to configure. One exception on the WD My Cloud OS5 firmware: Docker 28 or newer needs the daemon option `--allow-direct-routing`, see [Starting Docker automatically after a NAS reboot](#starting-docker-automatically-after-a-nas-reboot).
- **Docker 19.03.8 up to 20.10.8** (for example the 19.03.8 that WD ships): recommended minimum for the legacy path; needs a seccomp profile, see below.
- **Docker 19.03.3 and similar early 19.03 releases:** `docker pull` fails with `mediaType in manifest should be 'application/vnd.docker.distribution.manifest.v2+json' not 'application/vnd.oci.image.manifest.v1+json'`. Importing the image with `docker load` avoids the error, see [Importing the image with `docker load`](#importing-the-image-with-docker-load). Running the container on 19.03.3 itself has not been verified.
- **Docker older than 19.03:** not supported.

On Docker older than 20.10.9 the default seccomp profile answers system calls it does not know with `EPERM` instead of `ENOSYS`. The C library of the image only falls back to the old calls on `ENOSYS`, so Python fails at `time.time()` with `OSError: [Errno 75] Value too large for defined data type`; the container log then shows that line as the self-test error. Either update Docker, or start the container with the profile [`seccomp-legacy-docker.json`](https://github.com/opencloudtouch/opencloudtouch/releases/latest/download/seccomp-legacy-docker.json) (also in the repository as [`deployment/seccomp-legacy-docker.json`](../deployment/seccomp-legacy-docker.json)):

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

With the ready-made apps below, Portainer keeps its data in the Docker volume `portainer_data`, which lies in the app's data root (`<data root>/volumes/portainer_data/_data`). The profile file can be copied there and was used from that folder with the `docker` command-line client; deploying it as a Portainer stack from that volume was not verified.

**Docker Compose on the command line (no Portainer):** with Docker Compose v2 or newer (a single binary, for example `docker-compose-linux-armv7`), `seccomp=./seccomp-legacy-docker.json` (relative to the Compose file) and an absolute path both work on Docker 19.03.8; Compose reads the file and passes its content to the daemon. Without the `security_opt` line the container exits at once with the hint about Docker older than 20.10.9.

The profile allows all system calls by default and blocks the dangerous ones that Docker's own profile blocks (mount, ptrace, namespaces, kernel modules, and so on). It is a deny-list: it is weaker than Docker's default allow-list profile but much stronger than `seccomp=unconfined`, and it does not block dangerous system calls that newer kernels add. It also makes `clone3` answer `ENOSYS`, so that the C library falls back to `clone`, which the profile filters. Use it **only on old kernels (below 5.3)** and only on Docker older than 20.10.9; it is not needed and not recommended on Docker 20.10.9 or newer.

Maintenance: the maintainers review this profile whenever the supported Docker baseline changes.

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

### Starting Docker automatically after a NAS reboot

On WD My Cloud OS5 nobody starts the Docker daemon at boot: after every reboot `docker ps` fails and the containers stay down, even with `--restart unless-stopped`. Docker has to be started by a WD app, because only apps get a start script that the firmware runs at boot.

- **Ready-made apps (verified):** an unofficial build guide and script for apps that start Docker (19.03.8 or 29.9.3) and Portainer at boot, including the bundled images, is in the discussion [Docker + Portainer app for WD My Cloud OS5](https://github.com/opencloudtouch/opencloudtouch/discussions/644). Create the Portainer admin user within 5 minutes after its first start, otherwise Portainer locks itself until you restart the container. If such an app is installed but Docker or Portainer does not come up, read its start log in a browser at `http://<NAS>/<app folder name>/startup.log`.
- **Docker 19.03.x:** the app's `start.sh` must do what you would do by hand. It was verified on a My Cloud EX2 Ultra with firmware 5.x:
  1. wait until the cgroup mounts `memory`, `devices`, `cpu`, `cpuacct` and `pids` exist under `/sys/fs/cgroup` (at boot they appear a little after the apps start, so wait up to about two minutes);
  2. load the kernel modules Docker's bridge network needs from `/usr/local/modules/driver/`: `nf_nat`, `nf_nat_ipv4`, `nf_nat_masquerade_ipv4`, `xt_addrtype`, `xt_nat`, `ipt_MASQUERADE`, `iptable_nat`, `llc`, `stp`, `bridge`, `br_netfilter` (`insmod`, skip the ones already loaded);
  3. start `dockerd --data-root <folder on the data volume> --storage-driver vfs --host unix:///var/run/docker.sock --pidfile /var/run/docker.pid` in the background.

  Keep the data root on the data volume, not in the firmware partition. The `vfs` storage driver needs more disk space than `overlay2` but works on this kernel. The `stop.sh` of the app should only stop the daemon and never delete the data root.
- **Docker 28 or newer:** the same steps, plus start `dockerd` with `--allow-direct-routing`. Docker 28 adds an iptables `raw` table rule for every container, this firmware kernel has no `raw` table, and without the flag no container can start ("Unable to enable DIRECT ACCESS FILTERING"). The flag has one consequence: published ports also answer on the container address from the local network segment, as in Docker 27 and older. Verified with Docker 29.9.3 and OpenCloudTouch; it needs no seccomp profile.
- **Uninstall:** removing the app only unregisters it, so the app's `remove.sh` has to delete the data root, the Docker bridge, the mounts and the firewall rules and chains Docker created. Kernel modules and the `FORWARD` policy that Docker sets to `DROP` come back to normal only after a reboot.
- **Verify:** reboot the NAS and wait about a minute. `docker ps` should list your containers as `Up`, and the OCT web interface should open without any manual step. In the verified setup the Docker API was ready about 40 seconds after boot.

An app is also a clean place for the hook: it shows up under Apps, where you can switch it off or uninstall it.

### Troubleshooting path

1. Collect the facts: `getconf PAGE_SIZE`, `uname -a` and `docker version` (client and server).
2. Match the container log:
   - `library self-test passed`: the image works, look elsewhere (network mode, ports).
   - `library self-test failed`: the next log line is the last error Python printed, followed by the two possible causes. On Docker older than 20.10.9 the cause is its default seccomp profile: update Docker or use the profile above. On Docker 20.10.9 or newer it is not: the image cannot load its libraries on this kernel, so report the facts from step 1.
   - `docker run` or the stack fails before the container starts with `Unable to enable DIRECT ACCESS FILTERING`: Docker 28 or newer on the WD My Cloud OS5 firmware needs the daemon option `--allow-direct-routing`, see [Starting Docker automatically after a NAS reboot](#starting-docker-automatically-after-a-nas-reboot).
   - `OCT_SKIP_PAGE_SIZE_CHECK=1 is set`: the self-test was skipped on purpose, remove the variable unless you know you need it.
3. Try the fix from step 2 (Docker update or the profile) and restart the container.
4. Still failing? Open a [bug report](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml) and attach: the output of step 1, the full container log (`docker logs <container>`), your `docker run` or Compose settings without secrets, and the device model. Do not include tokens, passwords or personal data.

## Still stuck?

Open a [bug report](https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml) or check [GitHub Discussions](https://github.com/opencloudtouch/opencloudtouch/discussions).
