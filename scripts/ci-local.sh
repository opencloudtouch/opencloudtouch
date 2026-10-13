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

case "$target" in
  frontend)
    image="$NODE_IMAGE"
    setup='cp -r /work /tmp/work && cd /tmp/work && npm ci --silent'
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
    setup='cp -r /work /tmp/work && cd /tmp/work/apps/backend && pip install -q -e . && pip install -q -r requirements-dev.txt'
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
  "$image" \
  bash -c "$setup && $run"
