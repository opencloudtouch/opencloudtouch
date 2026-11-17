# DevOps Agent Rules (`deployment/`, `scripts/`, `.github/`)

- **Boundaries:** Never modify `apps/` source code (delegate to Backend/Frontend).
- **Docker:** Multi-stage, multi-arch (`amd64`, `arm64`, `arm/v7`), non-root user, health check mandatory.
- **Scripts:** PowerShell for local deployment, POSIX shell for container entrypoints. Must support mock mode (default) and real device mode.
- **CI/CD:** GitHub Actions must preserve ≥ 80% coverage gates.
