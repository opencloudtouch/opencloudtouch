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
#   Python: 3.11.8-slim (Debian Bookworm)
#   Node.js: 20-slim (for frontend build)

# Stage 1: Python Dependencies (separate for better caching)
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS python-deps

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

# Cleanup: Remove build deps and artifacts (reduce layer size)
RUN apt-get purge -y --auto-remove gcc libc6-dev libffi-dev make autoconf automake libtool && \
    find /install -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /install -name "*.pyc" -delete

# Stage 2: Frontend Build (platform-independent HTML/CSS/JS)
FROM node:20-slim AS frontend-build

WORKDIR /build/frontend

# Install dependencies first (better layer caching)
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit

# Copy source files needed for build
COPY apps/frontend/src ./src
COPY apps/frontend/public ./public
COPY apps/frontend/index.html ./
COPY apps/frontend/vite.config.ts ./
COPY apps/frontend/tsconfig.json ./
COPY apps/frontend/tsconfig.app.json ./
COPY apps/frontend/tsconfig.node.json ./

# Build the frontend (output: ../../.out/dist relative to /build/frontend = /build/.out/dist)
RUN npm run build

# Stage 3: Backend Runtime
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS backend

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
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get upgrade -y --no-install-recommends

# Copy Python dependencies from build stage
COPY --from=python-deps /install /usr/local

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

# Install su-exec for dropping privileges in entrypoint (tiny, no deps)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

# Environment defaults
ENV OCT_HOST=0.0.0.0
ENV OCT_PORT=7777
ENV OCT_DB_PATH=/data/oct.db
ENV OCT_LOG_LEVEL=INFO
ENV OCT_DISCOVERY_ENABLED=true
# USER is required by asyncssh (getpass.getuser()) — without it, SSH
# connections crash on container runtimes that don't set it (TrueNAS, etc.)
ENV USER=oct

# Build signature — HMAC of version, only CI can produce a valid one
ARG OCT_BUILD_SIGNATURE=""
ENV OCT_BUILD_SIGNATURE=${OCT_BUILD_SIGNATURE}

# Set Python path for package
ENV PYTHONPATH=/app

# Healthcheck using entrypoint script
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD /entrypoint.sh health || exit 1

# Expose port
EXPOSE 7777

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
