# Cloud agent brief: experiment "aligned base" for #530

Read first: issue #530 (`gh issue view 530 --comments`), `docs/investigations/529-variants.md`, `docs/investigations/529-elf-alignment.md`, `scripts/elf_pagesize_scan.py`.

## Goal

Produce an armv7 image of OpenCloudTouch whose ELF files all pass `scripts/elf_pagesize_scan.py` (exit code 0, ideally also the conservative 64 KB rule), so it can be tested on a 32 KB page-size NAS (WD EX2 Ultra, QNAP). This is experiment "B/own base" from #530.

## Approach

1. In `deployment/Dockerfile` on branch `exp/529-aligned-base` add a builder stage (armv7 only matters) that, starting from the pinned `python:3.11-slim` digest:
   - enables `deb-src`, installs `build-essential`, `devscripts`, `dpkg-dev`
   - for each offending package from the scan table (at least: zlib, bzip2, acl, libbsd, libmd, libpsl, rtmpdump, db5.3, gdbm, gmp, readline, findutils, grep, hostname) runs `apt-get source` and `dpkg-buildpackage -b` with `DEB_LDFLAGS_APPEND=-Wl,-z,max-page-size=0x10000`, version suffix `+oct1`
   - installs the resulting `.deb` files into the final runtime stage
   Alternatively, copy only the rebuilt shared objects if package installation causes dependency trouble; prefer real `.deb` installation.
2. Add the entrypoint bypass: in `apps/backend/entrypoint.sh`, `check_page_size()` must skip the 32768 exit when `OCT_SKIP_PAGE_SIZE_CHECK=1` (log a warning instead). Keep default behaviour unchanged. Add or adapt the existing CI test for page-size handling (`.github/workflows/ci.yml`, job `test-page-size-detection`) so it still passes.
3. Verify without hardware: export the built armv7 image and run `python scripts/elf_pagesize_scan.py` on it. Goal: exit 0. Also run a QEMU-user smoke test (container starts, `/health` OK, `import zlib, ssl, sqlite3, ctypes, pydantic_core`). QEMU-user is not evidence for page-size support, only for "nothing broke".
4. If a package cannot be rebuilt cleanly, record why and try the cheap fallback for that object only (realign tool or patchelf). Do not rewrite libc or ld.so (they already pass).

## Allowed

- Push to branches `exp/529-*` only.
- Run `test-build.yml` via `workflow_dispatch` on an `exp/529-*` branch with `image_tag=exp-529-aligned-<n>` and `docker_armv7=true` (armv7 only, never `latest` / `stable`).
- Comment on issue #530.

## Not allowed

- Merge, open PRs, push tags, touch `main`, release workflows, or any non-`exp/529-*` branch.
- Change application code under `apps/backend/src` or `apps/frontend`.
- Delete GHCR tags (maintainer does that).
- `git worktree` (use plain branch switching or the checkout you are given).

## Cost control

- Stop after at most 3 build iterations. Each `test-build.yml` armv7 run is slow (QEMU); do not retry blindly, read the log first.
- If a failure is unrelated to alignment (apt, network, QEMU), report it and stop instead of working around it for long.

## Repo rules

- All repo content in English. No mention of AI, Claude or any assistant in commits, comments or files; no Co-Authored-By trailers.
- Conventional Commits (`feat:`, `fix:`, `chore:` ...).

## Done when

- A comment on #530 contains: branch name, image tag, scan result of the built image (exit code, remaining failing objects if any), QEMU smoke-test result, build time, and the exact tester instructions from #530 filled in with the real tag.
- Then STOP. The maintainer will ask the reporter of #529 to test.
