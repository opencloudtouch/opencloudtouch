# ADR 008 — Build the 64 KB-aligned armv7 packages under QEMU, cached in GHCR

**Date**: 2026-11-10  
**Status**: Accepted  
**Deciders**: OpenCloudTouch maintainers

---

## Context

32 KB page-size ARM NAS kernels need ELF segments aligned to 64 KB. The armv7 image therefore
rebuilds 14 Debian runtime source packages with `-Wl,-z,max-page-size=0x10000`. Built natively under
QEMU, a cold run of this stage takes about 3 hours (about 3.5 hours for the whole image).

## Options considered

1. **QEMU build with a GHCR registry cache** (chosen). A warm run skips the stage: the whole armv7
   image builds in about 4.5 minutes.
2. **Cross-compile 13 of the 14 packages** (`dpkg-buildpackage -a armhf` on the build platform), with
   `zlib` still under QEMU because its `minizip` subproject does not link when cross-built. Measured
   cold: package stage 19 minutes, whole image 29 minutes. The resulting image was equivalent: same
   package list (name, version, status), same file list (mode, path), ELF scan with no failures,
   smoke test passed.

## Decision

Option 1. Releases happen every 4 to 6 weeks, the registry cache does not expire, and the cache is
only cold when the base image digest or the stage changes. A cold run in the background costs hours
only on those rare occasions. Option 2 saves time only on a cold cache, but adds a second stage, a
permanent `zlib` exception and a cross toolchain that can break with every Debian update.

## Consequences

- The aligned stage is cached in GHCR (`buildcache-aligned-debs-armv7`); keep that tag.
- A base image digest bump (or a stage change) means one cold build of about 3.5 hours.
- If cold builds become frequent (for example a weekly automatic digest bump), revisit option 2; the
  trial branch `ci/armv7-cross-compile-trial` has the working cross build.

- **Security updates for the 14 aligned packages arrive with the base image digest, not through
  `apt-get upgrade`.** The stage rebuilds each source at the version the pinned base image ships, and the
  runtime stage holds those packages, so a Debian security fix published after the digest was pinned is not
  picked up for them until the digest is bumped. All other packages still get `apt-get upgrade`. Two things
  limit the gap: a cold build fails when the archive no longer serves the pinned source version, which forces
  a digest bump, and a bump rebuilds the stage. The digest is pinned by hand (Dependabot has no Docker
  ecosystem entry here), so it must be bumped regularly, for example together with each release. Applying
  `apt-get upgrade` before the rebuild would not close the gap: the cached stage layer would still be stale
  until its inputs change, and the rebuilt packages would no longer match the base image's versions.
