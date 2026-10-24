#!/usr/bin/env bash
# Scratch script for the `experiment` suite of claude-sandbox.yml.
# Edit freely on a branch to test things that need Docker, QEMU or Buildx,
# for example multi-arch builds or entrypoint/page-size behaviour in a container.
# QEMU and Buildx are already set up. Keep it free of secrets and network side effects.
set -euo pipefail

echo "== Environment =="
uname -a
getconf PAGE_SIZE
docker version --format '{{.Server.Version}}'
docker buildx ls

echo "== Example: build the armv7 image without pushing =="
echo "docker buildx build --platform linux/arm/v7 -f deployment/Dockerfile -t oct-experiment:armv7 --load ."
echo "(commented out by default, enable in a branch when needed)"
