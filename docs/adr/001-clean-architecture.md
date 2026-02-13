# ADR-001: Use Clean Architecture with Dependency Injection

**Date:** 2026-01-15  
**Status:** Accepted  
**Deciders:** Tech Lead, Backend Team

## Context

OpenCloudTouch is a local control replacement for Bose SoundTouch devices after cloud shutdown. We need a maintainable, testable architecture that supports:

- Multiple device types (SoundTouch 10, 20, 30, 300)
- Multiple discovery methods (SSDP, manual IPs, mocks)
- Easy unit testing without external dependencies
- Future extensibility (TuneIn, other device brands)

## Decision

We will implement **Clean Architecture** (Hexagonal Architecture) with **Dependency Injection** via FastAPI's dependency system.

### Architecture Layers

```
┌─────────────────────────────────────┐
│  API Layer (FastAPI Routes)        │  ← HTTP/REST Interface
├─────────────────────────────────────┤
│  Use Cases / Services               │  ← Business Logic
├─────────────────────────────────────┤
│  Domain Models                      │  ← Entities, Value Objects
├─────────────────────────────────────┤
│  Adapters (External Systems)       │  ← SoundTouch, RadioBrowser
├─────────────────────────────────────┤
│  Infrastructure (DB, Config)        │  ← SQLite, Logging
└─────────────────────────────────────┘
```

### Key Principles

1. **Dependency Rule:** Dependencies point inward. Inner layers don't know about outer layers.
2. **Protocols over Concrete Types:** Use `Protocol` classes for dependency contracts.
3. **Injection via app.state:** FastAPI app lifecycle manages all singleton services.
4. **Repository Pattern:** All database access goes through repositories.
5. **Adapter Pattern:** External APIs (Bose, RadioBrowser) wrapped in adapters.

### Example

```python
# Domain Interface (Protocol)
class IDeviceRepository(Protocol):
    async def get_all(self) -> List[Device]: ...

# Infrastructure Implementation
class DeviceRepository(IDeviceRepository):
    def __init__(self, db_path: str): ...
    async def get_all(self) -> List[Device]:
        # SQLite implementation

# Dependency Injection
async def lifespan(app: FastAPI):
    device_repo = DeviceRepository(db_path)
    await device_repo.initialize()
    app.state.device_repo = device_repo
    yield
    await device_repo.close()

# Route uses injected dependency
@router.get("/api/devices")
async def get_devices(request: Request):
    repo = request.app.state.device_repo
    return await repo.get_all()
```

## Consequences

### Positive

- **Testability:** Easy to mock dependencies via Protocol classes.
- **Maintainability:** Clear separation of concerns.
- **Extensibility:** New adapters (TuneIn, Sonos) can be added without changing core logic.
- **Type Safety:** MyPy/Pyright can verify dependency contracts.
- **No Global State:** All dependencies managed by FastAPI lifecycle.

### Negative

- **Initial Complexity:** More boilerplate than direct imports.
- **Learning Curve:** Team must understand Clean Architecture principles.
- **Protocol Overhead:** Every public interface needs a Protocol definition.

## Alternatives Considered

### 1. Direct Imports (No DI)

```python
# ❌ Rejected: Hard to test, tight coupling
from opencloudtouch.devices.repository import device_repo
await device_repo.get_all()
```

**Reason for rejection:** Cannot mock dependencies in tests, tight coupling between layers.

### 2. Global Singletons

```python
# ❌ Rejected: Global mutable state
_device_repo_instance = None
def get_device_repo(): return _device_repo_instance
```

**Reason for rejection:** Global state makes tests non-isolated, hard to cleanup.

### 3. Dependency Injector Library (dependency-injector)

**Reason for rejection:** FastAPI's built-in `app.state` is simpler, no extra dependency.

## Related Decisions

- See ADR-002 for SQLite schema design
- See ADR-003 for SSDP discovery implementation
- See ADR-004 for FastAPI app.state migration

## References

- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Python Protocol Classes (PEP 544)](https://peps.python.org/pep-0544/)
