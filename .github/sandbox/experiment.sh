#!/usr/bin/env bash
# Scratch script for the `experiment` suite of claude-sandbox.yml.
# Smoke test of the published armv7 experiment image under QEMU (#529).
set -euo pipefail

IMG="${OCT_IMAGE:-ghcr.io/opencloudtouch/opencloudtouch:exp-529-bullseye-1}"
PLATFORM="linux/arm/v7"

echo "== Environment =="
uname -a
getconf PAGE_SIZE
docker version --format '{{.Server.Version}}'

echo "== Pull $IMG ($PLATFORM) =="
docker pull --platform "$PLATFORM" "$IMG"

echo "== libc, Python and native imports =="
docker run --rm --platform "$PLATFORM" --entrypoint sh "$IMG" -c '
  ldd --version | head -1
  python --version
  python -c "import zlib, ssl, sqlite3, ctypes, bz2, readline, pydantic_core, uvloop, httptools, psutil, yaml, cryptography; print(\"imports ok\")"
'

echo "== Start container in mock mode =="
docker run -d --name oct-smoke --platform "$PLATFORM" -p 7777:7777 \
  -e OCT_MOCK_MODE=true -e OCT_DISCOVERY_ENABLED=false -e OCT_LOG_LEVEL=DEBUG \
  "$IMG"

healthy=false
for _ in $(seq 1 90); do
  if curl -fsS http://localhost:7777/health; then
    echo
    healthy=true
    break
  fi
  sleep 2
done

echo "== Container logs =="
docker logs oct-smoke 2>&1 | head -80

if [ "$healthy" != "true" ]; then
  echo "Container did not become healthy"
  exit 1
fi
if docker logs oct-smoke 2>&1 | grep -q "Python self-test failed"; then
  echo "Entrypoint self-test reported a problem"
  exit 1
fi
echo "Smoke test passed"
