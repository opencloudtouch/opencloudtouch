# syntax=docker/dockerfile:1

# ============================================================
# Multi-stage build for OpenCloudTouch
# Supports amd64 and arm64
# ============================================================

# Base Image Versions (Pinned for Reproducibility)
# Update SHA256 digests with:
#   docker pull <image>:<tag>
#   docker inspect --format='{{.RepoDigests}}' <image>:<tag>
#
# Current versions:
#   Node.js: 20.11-alpine (Alpine 3.19)
#   Python: 3.11.8-slim (Debian Bookworm)

# Stage 1: Build Frontend
FROM node:20-alpine@sha256:09e2b3d9726018aecf269bd35325f46bf75046a643a66d28360ec71132750ec8 AS frontend-builder

# Get build architecture from buildx
ARG TARGETARCH

WORKDIR /app

# Copy workspace configuration first
COPY package*.json ./
COPY apps/frontend/package*.json ./apps/frontend/

# Install dependencies using workspace
RUN npm ci

# Install platform-specific rollup binary for Alpine (musl)
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      npm install --no-save @rollup/rollup-linux-x64-musl; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
      npm install --no-save @rollup/rollup-linux-arm64-musl; \
    fi

# Copy frontend source
COPY apps/frontend/ ./apps/frontend/

# Build frontend
RUN npm run build --workspace=apps/frontend

# Stage 2: Python Dependencies (separate for better caching)
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS python-deps

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies with prefix for easy copying
# First: Install security-pinned transitive deps to prevent vulnerable versions
# being pulled first by other packages
COPY apps/backend/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install \
    jaraco-context==6.1.0 \
    wheel==0.46.2 && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Cleanup: Remove gcc and build artifacts (reduce layer size)
RUN apt-get purge -y --auto-remove gcc && \
    find /install -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /install -name "*.pyc" -delete

# Stage 3: Backend Runtime
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS backend

WORKDIR /app

# Copy Python dependencies from build stage
COPY --from=python-deps /install /usr/local

# Copy backend source (as package)
COPY apps/backend/src/opencloudtouch ./opencloudtouch

# Precompile Python bytecode for faster startup
# -b: Write .pyc files (bytecode)
# Delete .py source files to save space (bytecode is sufficient)
RUN python -m compileall -b opencloudtouch/ && \
    find opencloudtouch/ -name "*.py" ! -name "__main__.py" -delete && \
    find opencloudtouch/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/apps/frontend/dist ./frontend/dist

# Copy entrypoint script
COPY apps/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create data directory
RUN mkdir -p /data

# Run as non-root user
RUN useradd -m -u 1000 oct && chown -R oct:oct /app /data
USER oct

# Environment defaults
ENV OCT_HOST=0.0.0.0
ENV OCT_PORT=7777
ENV OCT_DB_PATH=/data/oct.db
ENV OCT_LOG_LEVEL=INFO
ENV OCT_DISCOVERY_ENABLED=true

# Set Python path for package
ENV PYTHONPATH=/app

# Healthcheck using entrypoint script
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD /entrypoint.sh health || exit 1

# Expose port
EXPOSE 7777

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
