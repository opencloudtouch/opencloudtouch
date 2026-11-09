# ADR 008 — Cross-compile the 64 KB-aligned armv7 packages

**Date**: 2026-11-09  
**Status**: Accepted  
**Deciders**: OpenCloudTouch maintainers

---

## Context

32 KB page-size ARM NAS kernels need ELF segments aligned to 64 KB. The armv7 image therefore
rebuilds 14 Debian runtime source packages with `-Wl,-z,max-page-size=0x10000`. Built natively under
QEMU, a cold run of this stage takes about 3.5 hours.

## Decision

Build 13 of the 14 packages with a cross toolchain (`dpkg-buildpackage -a armhf` on the build
platform) and only `zlib` under QEMU. `zlib` does not cross-build: its `minizip` subproject does not
link, and three workarounds failed. One workaround is below the limit of three set in the spec.

## Measurements (cold cache)

| Variant | Package stage | Full armv7 image |
|---|---|---|
| QEMU only | about 3 h 2 min | about 3.5 h |
| Hybrid (cross + zlib under QEMU) | 16.5 min | about 40 min |

Equivalence: the package lists (name, version, status) and the file lists (mode, path) of both images
are identical. The ELF scan of the hybrid image reports 840 ELF files with no failures; the
`dpkg --audit`, `apt-get check` and QEMU smoke test also pass.

## Consequences

- The aligned stage is cached in GHCR (`buildcache-aligned-debs-armv7`), so unchanged inputs skip it.
- The `ALIGNED_QEMU_SOURCES` build argument lists the packages that stay on QEMU; remove `zlib` from it
  once the `minizip` cross-build is fixed upstream.
- Running on a 32 KB device is still verified by hand (see the PR).
