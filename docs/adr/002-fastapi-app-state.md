# ADR-002: Use FastAPI app.state for Dependency Management

**Date:** 2026-01-28  
**Status:** Accepted  
**Supersedes:** Global module-level singletons  
**Deciders:** Backend Team

## Context

OpenCloudTouch initially used global module-level variables to store singleton instances (repositories, services). This caused issues:

1. **Test Isolation:** Tests had to manually call `clear_dependencies()` to reset state.
2. **Lifecycle Management:** No automatic cleanup on app shutdown.
3. **Type Safety:** IDEs couldn't infer types from global variables without type hints.
4. **Race Conditions:** Multiple test runs could interfere with each other.

Example of old pattern:

```python
# ❌ OLD PATTERN
_device_repo_instance: Optional[IDeviceRepository] = None

def set_device_repo(repo: IDeviceRepository) -> None:
    global _device_repo_instance
    _device_repo_instance = repo

def get_device_repo() -> IDeviceRepository:
    if _device_repo_instance is None:
        raise RuntimeError("DeviceRepository not initialized")
    return _device_repo_instance

# Tests had to call clear_dependencies() after each test
def clear_dependencies() -> None:
    global _device_repo_instance
    _device_repo_instance = None
```

## Decision

We will **use FastAPI's `app.state` for all dependency management**, storing singleton instances directly on the application object.

### Implementation

**Lifespan:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize dependencies at startup
    device_repo = DeviceRepository(cfg.effective_db_path)
    await device_repo.initialize()
    app.state.device_repo = device_repo  # ✅ Store in app.state
    
    device_service = DeviceService(repository=device_repo)
    app.state.device_service = device_service
    
    yield  # App runs
    
    # Cleanup at shutdown
    await device_repo.close()

app = FastAPI(lifespan=lifespan)
```

**Dependency Functions:**

```python
# ✅ NEW PATTERN
def get_device_repo(request: Request) -> IDeviceRepository:
    return request.app.state.device_repo  # Access from request

def get_device_service(request: Request) -> IDeviceService:
    return request.app.state.device_service
```

**Routes:**

```python
@router.get("/api/devices")
async def get_devices(request: Request):
    service = get_device_service(request)
    return await service.get_all()
```

**Tests:**

```python
@pytest.fixture
async def app_with_dependencies():
    app = FastAPI()
    
    # Set up dependencies on app.state
    device_repo = DeviceRepository(":memory:")
    await device_repo.initialize()
    app.state.device_repo = device_repo
    
    yield app
    
    # Automatic cleanup when fixture exits
    await device_repo.close()
```

## Consequences

### Positive

- **Automatic Lifecycle:** FastAPI manages startup/shutdown automatically.
- **Test Isolation:** Each test creates its own `app` with independent `app.state`.
- **No Global State:** No module-level variables to reset.
- **Type Safety:** `app.state` attributes are typed via stubs.
- **Simpler Tests:** No need to call `set_*()` or `clear_dependencies()`.
- **Standard Pattern:** Recommended by FastAPI documentation.

### Negative

- **Request Parameter:** All dependency functions now need `Request` parameter.
- **Migration Effort:** Existing tests had to be updated.
- **Breaking Change:** Changed dependency function signatures.

## Migration Steps

1. ✅ Update `main.py` lifespan to use `app.state` instead of `set_*()` calls.
2. ✅ Update `dependencies.py`:
   - Add `Request` parameter to all `get_*()` functions.
   - Return from `request.app.state` instead of global variables.
   - Remove all `set_*()` functions.
   - Remove `clear_dependencies()` function.
   - Remove module-level `_*_instance` variables.
3. ✅ Update integration tests:
   - Use `app.state` for fixture setup.
   - Remove calls to `set_*()` and `clear_dependencies()`.
4. ✅ Run full test suite to verify migration.

## Alternatives Considered

### 1. Keep Global Singletons

**Reason for rejection:** Tests must manually reset state, prone to race conditions.

### 2. Use dependency-injector Library

**Reason for rejection:** Adds external dependency, FastAPI's built-in solution is simpler.

### 3. Use functools.lru_cache

```python
@lru_cache  # ❌ Rejected
def get_device_repo() -> IDeviceRepository:
    return DeviceRepository(db_path)
```

**Reason for rejection:** No control over lifecycle, can't cleanup connections.

## Related Decisions

- See ADR-001 for Clean Architecture principles
- See ADR-004 for Repository Pattern

## References

- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI app.state](https://fastapi.tiangolo.com/advanced/sub-applications/#shared-state)
- [GitHub Issue: Global Dependencies Problem](https://github.com/tiangolo/fastapi/discussions/5445)
