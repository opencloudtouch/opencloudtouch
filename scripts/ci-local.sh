#!/usr/bin/env bash
# Run CI's frontend or backend test job locally, inside a container that
# matches the GitHub Actions runner (same Node/Python version, same OS).
#
# Why a container instead of installing straight into the repo: on a host
# where the repo lives on a filesystem without symlink support (e.g. exFAT
# on Windows), `npm ci` can't create the workspace symlink and fails outright
# — even with admin rights, since it's a filesystem limitation, not a
# permissions one. Copying the repo into the container's own filesystem
# sidesteps that, and as a side effect gives a byte-for-byte match of what
# `npm ci` / `pip install` actually resolve in CI, rather than whatever a
# local workaround (--legacy-peer-deps, --no-workspaces, etc.) happens to
# resolve instead.
#
# Usage:
#   scripts/ci-local.sh frontend [vitest args...]
#   scripts/ci-local.sh frontend --shell          # drop into a shell after install
#   scripts/ci-local.sh backend  [pytest args...]
#   scripts/ci-local.sh backend  --shell
#
# Examples:
#   scripts/ci-local.sh frontend
#   scripts/ci-local.sh frontend run tests/unit/health.test.ts
#   scripts/ci-local.sh backend tests/unit/zones/ -v
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_IMAGE="node:24-slim"
PYTHON_IMAGE="python:3.11-slim"   # matches Dockerfile and ci.yml's backend-tests job

if command -v podman &>/dev/null; then
  RUNTIME=podman
elif command -v docker &>/dev/null; then
  RUNTIME=docker
else
  echo "Need docker or podman on PATH." >&2
  exit 1
fi

target="${1:-}"
shift || true

tty_flags=""
# Persistent package-manager caches (named volumes, stored on the container
# engine's own Linux filesystem — not the Windows host's exFAT drive, so
# this works even though a bind-mounted node_modules wouldn't). These only
# cache *downloads*: `npm ci` still wipes and reinstalls node_modules from
# package-lock.json every run (that's the point of `ci` over `install`), and
# `pip install` still resolves exact versions from requirements — the cache
# just skips re-fetching/rebuilding packages already seen on a prior run, on
# this same machine. Correctness (byte-for-byte match of what CI resolves)
# is unaffected; only re-download/rebuild time is skipped.
cache_volume_args=""

# cp -r on the raw bind mount was the real bottleneck (not the package
# install): it was copying the whole working tree verbatim, including
# multi-GB dev-only dirs (.venv, .mypy_cache, .out, scripts/issue_handler,
# etc.) that no test run needs and that are regenerated fresh inside the
# container anyway. Reading each of their many small files through the
# bind mount dominated total runtime (measured: ~5m of a ~7.5m frontend
# run was this copy alone, almost unaffected by whether the npm cache
# above was warm or cold). tar --exclude avoids descending into them at
# all, cutting what's actually read from the slow bind mount to the
# source tree.
COPY_EXCLUDES=(
  --exclude=.git
  --exclude=.venv
  --exclude=.mypy_cache
  --exclude=.out
  --exclude=.local
  --exclude=.pytest_cache
  --exclude=.ruff_cache
  --exclude=__pycache__
  --exclude=node_modules
  --exclude=scripts/issue_handler
  --exclude=.specify
)
copy_cmd="mkdir -p /tmp/work && tar -C /work ${COPY_EXCLUDES[*]} -cf - . | tar -C /tmp/work -xf -"

case "$target" in
  frontend)
    image="$NODE_IMAGE"
    setup="$copy_cmd"' && cd /tmp/work && npm ci --silent'
    cache_volume_args="-v oct-ci-local-npm-cache:/root/.npm"
    if [ "${1:-}" = "--shell" ]; then
      run='bash'
      tty_flags="-it"
    elif [ "$#" -gt 0 ]; then
      run="cd /tmp/work/apps/frontend && npx vitest $*"
    else
      run='cd /tmp/work && npm run test:coverage --workspace=apps/frontend'
    fi
    ;;
  backend)
    image="$PYTHON_IMAGE"
    setup="$copy_cmd"' && cd /tmp/work/apps/backend && pip install -q -e . && pip install -q -r requirements-dev.txt'
    cache_volume_args="-v oct-ci-local-pip-cache:/root/.cache/pip"
    if [ "${1:-}" = "--shell" ]; then
      run='bash'
      tty_flags="-it"
    else
      run="cd /tmp/work/apps/backend && OCT_MOCK_MODE=true OCT_HAS_DEVICES=false CI=true pytest ${*:---cov=opencloudtouch --cov-report=term-missing --cov-fail-under=80}"
    fi
    ;;
  *)
    echo "Usage: $0 {frontend|backend} [extra test-runner args | --shell]" >&2
    exit 1
    ;;
esac

echo "Using $RUNTIME, image $image" >&2

# MSYS_NO_PATHCONV: on Git Bash for Windows, the shell rewrites the
# "HOST:CONTAINER" volume spec as if it were a Windows path, mangling the
# container side. This disables that rewriting; it's a no-op elsewhere.
# shellcheck disable=SC2086
MSYS_NO_PATHCONV=1 "$RUNTIME" run --rm $tty_flags \
  -v "${REPO_ROOT}:/work:ro" \
  $cache_volume_args \
  "$image" \
  bash -c "set -eo pipefail; $setup && $run"
