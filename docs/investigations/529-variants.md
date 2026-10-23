# 32 KB page-size support: approach variants

Tracking issue: #530 (spike), user report: #529, earlier reports: #344 / #346.

## Original brainstorm (before phase 0)

Note: the letters here are the original brainstorm letters. They differ from the A-E labels used in the issue #530 experiments (mapping below).

| Approach | Effort | Assessment |
|---|---|---|
| **A. Build our own base image** (libc, zlib, openssl, libffi and Python from source with 64K alignment) | high | Cleanest way, but we would have to maintain the Debian userland parts ourselves, including security updates. This fits badly with our digest pinning and CVE scans. |
| **B. Alpine/musl variant with patched flags** (`LDFLAGS` for the packages we use) | medium to high | Smaller attack surface than Debian. But `abuild` would have to run for the core packages ourselves, and the Python wheels (pydantic-core, uvloop, ...) need musl-armv7 builds. |
| **C. Rewrite binaries afterwards** (`patchelf --page-size`, ELF realign on all `.so` files in the image) | low | Experimental, probably risky for `ld.so` and libc. Good as a quick test of the hypothesis. |
| **D. Change nothing**, only better error message and docs (recommend Raspberry Pi) | minimal | This is the current state. |

## Mapping to the experiments in #530

| Brainstorm | Issue #530 | Note |
|---|---|---|
| A (own base image) | B (rebuild offending libs) / D (own Python build) | Narrowed by phase 0, see below |
| B (Alpine) | C | Rejected by phase 0 |
| C (rewrite binaries) | A | Cheap first attempt |
| D (do nothing) | E / no-go | Fallback |

## Phase 0 result (scan of OCT 1.6.0 armv7, see `529-elf-alignment.md`)

- 16 of 838 ELF files are not 32 KB-safe, 14 from the Debian base and 2 (`libpsl`, `librtmp`) from curl dependencies.
- libc, ld.so, libpython, the python binary, gosu, curl, getconf and all pip wheels are fine.
- Alpine fails completely (131 of 131 files).

Consequence: "build our own base image" does **not** mean rebuilding libc/Python. It means a dedicated armv7 base layer: `python:3.11-slim` (pinned digest) plus the ~16 offending Debian packages rebuilt from source with `-Wl,-z,max-page-size=0x10000` (and a `+oct1` version suffix). Everything else stays as is.

## Decision (maintainer)

Go with the own-base-image approach, scoped as above (rebuilt Debian packages on top of the pinned `python:3.11-slim`). The cheap binary-rewrite approach stays an optional quick check. Alpine is dropped.
