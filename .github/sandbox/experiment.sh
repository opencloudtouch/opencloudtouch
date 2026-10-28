#!/usr/bin/env bash
# Scratch script for the `experiment` suite of claude-sandbox.yml.
# Builds the syscall probe image (#529) for armv7 under QEMU, runs it, and
# shows the same probe natively under the real Docker 19.03.8 seccomp profile.
set -euo pipefail

echo "== Environment =="
uname -a
docker version --format '{{.Server.Version}}'

echo "== Build probe image (linux/arm/v7, QEMU) =="
docker buildx build --platform linux/arm/v7 -f deployment/Dockerfile \
  --load -t oct-probe:armv7 .

echo "== Run probe (armv7 under QEMU, default seccomp of this runner) =="
docker run --rm --platform linux/arm/v7 oct-probe:armv7

echo "== Probe under the real Docker 19.03.8 default seccomp profile (x86_64) =="
WORK=$(mktemp -d)
sed -n "/^COPY <<'PROBE_C' \/probe.c\$/,/^PROBE_C\$/p" deployment/Dockerfile | sed '1d;$d' > "$WORK/probe.c"
gcc -O1 -Wall -static -o "$WORK/probe" "$WORK/probe.c"
curl -fsSL -o "$WORK/moby-19.03.8.json" \
  https://raw.githubusercontent.com/moby/moby/v19.03.8/profiles/seccomp/default.json
python3 -c "
import json,sys
p=json.load(open('$WORK/moby-19.03.8.json'))
print('profile: defaultAction =', p['defaultAction'], '| defaultErrnoRet =', p.get('defaultErrnoRet'))
"
for opt in "seccomp=$WORK/moby-19.03.8.json" "seccomp=unconfined"; do
  echo
  echo "---------- --security-opt ${opt##*/} ----------"
  docker run --rm -v "$WORK/probe:/probe:ro" --security-opt "$opt" debian:bullseye-slim /probe
done
