# syntax=docker/dockerfile:1

# ============================================================
# Multi-stage build for OpenCloudTouch
# Supports amd64, arm64, and armv7 (Raspberry Pi 2/3/4/5)
# ============================================================
#
# The frontend is built from source during the Docker build (Stage 2).
# This allows users to clone the repo and run `docker-compose up --build`
# without pre-building the frontend separately.
#
# CI may pre-build the frontend and provide it via .out/dist/ to skip Stage 2
# for faster builds, but it's not required.
#
# Base Image Versions (Pinned for Reproducibility)
# Update SHA256 digests with:
#   docker pull <image>:<tag>
#   docker inspect --format='{{.RepoDigests}}' <image>:<tag>
#
# Current versions:
#   Python: python:3.11-slim with openssl fixes (Debian Bookworm)
#   Node.js: 24-slim (for frontend build)
#
# IMPORTANT: Pin to the multi-arch INDEX digest, NOT a platform-specific one.
# A platform-specific digest (e.g. amd64) silently forces that architecture
# for ALL builds, breaking arm64/armv7. Verify with:
#   curl ... /manifests/<digest> → mediaType must be image.index, NOT image.manifest

# Stage 1: Python Dependencies (separate for better caching)
FROM python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca AS python-deps

# Install build dependencies (full toolchain needed for arm/v7 cross-compilation)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libc6-dev libffi-dev make autoconf automake libtool

WORKDIR /build

# Upgrade pip, setuptools, wheel FIRST to get latest versions with security fixes
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

# Install Python dependencies with prefix for easy copying
# First: Install security-pinned transitive deps to prevent vulnerable versions
# being pulled first by other packages
COPY apps/backend/requirements.txt ./
COPY apps/backend/pyproject.toml ./
COPY apps/backend/src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 3 --prefix=/install \
    jaraco-context==6.1.0 \
    wheel==0.46.2 && \
    pip install --retries 3 --prefix=/install -r requirements.txt && \
    pip install --prefix=/install --no-deps .

# Remove vulnerable vendored packages from setuptools (CVE-2026-23949, CVE-2026-24049)
# These are bundled inside setuptools but not needed at runtime
RUN find /install -path "*setuptools/_vendor/jaraco*" -delete 2>/dev/null || true && \
    find /install -path "*setuptools/_vendor/wheel*" -delete 2>/dev/null || true && \
    find /install -name "wheel-0.45*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Cleanup: Remove build deps (keep pip's compiled bytecode — see #400/#387,
# deleting it here forced the final stage to re-compile at runtime as a
# non-root user with no write access, producing millions of negative
# dentries from the failed stat() lookups)
RUN apt-get purge -y --auto-remove gcc libc6-dev libffi-dev make autoconf automake libtool

# Stage 2: Frontend Build (platform-independent HTML/CSS/JS)
# Force amd64 — output is static files, no native binaries needed.
# This avoids Node.js platform availability issues (e.g. Node 24 dropped armv7).
FROM --platform=$BUILDPLATFORM node:24-slim AS frontend-build

WORKDIR /build

# Copy workspace root package files (lock file is at root level — npm workspaces)
COPY package.json package-lock.json ./

# Copy frontend package.json for workspace resolution
COPY apps/frontend/package.json ./apps/frontend/

# Install dependencies via workspace root
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit --workspace=apps/frontend

# Copy frontend source files
COPY apps/frontend/src ./apps/frontend/src
COPY apps/frontend/public ./apps/frontend/public
COPY apps/frontend/index.html ./apps/frontend/
COPY apps/frontend/vite.config.ts ./apps/frontend/
COPY apps/frontend/tsconfig.json ./apps/frontend/

# Build the frontend (output: .out/dist relative to workspace root)
RUN cd apps/frontend && npm run build

# Stage 3: Backend Runtime
FROM python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca AS backend

# OCI Image Labels
LABEL org.opencontainers.image.title="OpenCloudTouch" \
      org.opencontainers.image.description="Local control for Bose SoundTouch devices after cloud shutdown" \
      org.opencontainers.image.url="https://github.com/opencloudtouch/opencloudtouch" \
      org.opencontainers.image.source="https://github.com/opencloudtouch/opencloudtouch" \
      org.opencontainers.image.documentation="https://github.com/opencloudtouch/opencloudtouch/wiki" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="OpenCloudTouch"

WORKDIR /app

# Apply OS security patches (fixes CVE-2026-0861 glibc and other HIGH vulns in base image)
# and install gosu/curl (entrypoint privilege drop / HEALTHCHECK probe).
# Deliberately placed before any COPY of app/frontend/entrypoint source: apt
# operations are the slowest, most network-heavy part of this stage, and
# Docker invalidates every layer from the first changed COPY onward. Keeping
# apt-get here means routine source edits never force gosu/curl to
# re-download — only a base-image or package-list change does.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends gosu curl

# Copy Python dependencies from build stage
COPY --from=python-deps /install /usr/local

# Precompile bytecode for the dependency tree so the runtime (non-root)
# user never has to write .pyc files itself. Must run here, against the
# exact files that ship in this stage, not in the discarded python-deps
# stage. Same base-image digest as python-deps, so the magic number matches.
RUN python -m compileall -q /usr/local || true

# Remove vulnerable packages AFTER copying deps (CVE-2026-23949, CVE-2026-24049)
# - Base image contains setuptools with vendored jaraco.context-5.3.0 and wheel-0.45.1
# - These are not needed at runtime and pose security risks
RUN find /usr/local/lib -path "*setuptools/_vendor/jaraco*" -delete 2>/dev/null || true && \
    find /usr/local/lib -path "*setuptools/_vendor/wheel*" -delete 2>/dev/null || true && \
    find /usr/local/lib -name "wheel-0.45*.dist-info" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib -name "jaraco.context-5.3.0*" -exec rm -rf {} + 2>/dev/null || true

# Copy backend source (as package)
COPY apps/backend/src/opencloudtouch ./opencloudtouch

# Precompile Python bytecode for faster startup
# -b: Write .pyc files (bytecode)
# Delete .py source files to save space (bytecode is sufficient)
RUN python -m compileall -b opencloudtouch/ && \
    find opencloudtouch/ -name "*.py" ! -name "__main__.py" -delete && \
    find opencloudtouch/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Copy frontend from build stage (built from source for self-build compatibility)
# In CI, this stage is skipped and .out/dist is provided via build context for faster builds
COPY --from=frontend-build /build/.out/dist ./frontend/dist

# Copy legal files
COPY LICENSE NOTICE DISCLAIMER.md ./

# Copy entrypoint script
COPY apps/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create data and log directories
RUN mkdir -p /data /logs

# Create non-root user (entrypoint fixes volume permissions then drops to oct)
RUN useradd -m -u 1000 oct && chown -R oct:oct /app /data /logs

# Environment defaults
ENV OCT_HOST=0.0.0.0
ENV OCT_PORT=7777
ENV OCT_DB_PATH=/data/oct.db
ENV OCT_LOG_LEVEL=INFO
ENV OCT_DISCOVERY_ENABLED=true
# USER is required by asyncssh (getpass.getuser()) â€” without it, SSH
# connections crash on container runtimes that don't set it (TrueNAS, etc.)
ENV USER=oct

# Build signature â€” HMAC of version, only CI can produce a valid one
ARG OCT_BUILD_SIGNATURE=""
ENV OCT_BUILD_SIGNATURE=${OCT_BUILD_SIGNATURE}

# Optional version override (docker build --build-arg OCT_VERSION=x).
# Not required for a correct version: _resolve_version() already reads the
# real pyproject.toml version from installed package metadata by default,
# for every build (official or self-built) — the same `pip install .` step
# bakes it in regardless of OCT_BUILD_SIGNATURE. This ARG only exists for
# forks that want to stamp a custom string instead of the upstream version.
ARG OCT_VERSION=""
ENV OCT_VERSION=${OCT_VERSION}

# Set Python path for package
ENV PYTHONPATH=/app

# Healthcheck via HTTP probe (curl) — does NOT spawn a Python interpreter.
# The previous `/entrypoint.sh health` variant started a fresh interpreter
# every 30s, which itself contributed to negative-dentry growth (see #387
# follow-up). curl is a tiny, already-present dependency (added above),
# not a new heavy one.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${OCT_PORT}/health || exit 1

# Expose port
EXPOSE 7777

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
