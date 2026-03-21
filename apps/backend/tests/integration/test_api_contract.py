"""API Contract Tests — verify endpoints match OpenAPI spec.

Tests:
1. All OpenAPI paths are reachable (no 404 for documented routes)
2. Request validation (422 for invalid payloads)
3. Response schemas match documented models
4. Wizard endpoint contracts (target_addr normalization, etc.)
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from httpx import ASGITransport, AsyncClient, Timeout

from opencloudtouch.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def openapi_spec():
    """Load the exported OpenAPI YAML spec."""
    spec_path = Path(__file__).resolve().parents[2] / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml not found at {spec_path}"
    with open(spec_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def openapi_live():
    """Get live OpenAPI spec from FastAPI app (source of truth)."""
    return app.openapi()


@pytest.fixture
async def client():
    """Lightweight async test client (no DB, no lifespan)."""
    transport = ASGITransport(app=app)
    timeout = Timeout(5.0, connect=2.0)
    async with AsyncClient(
        transport=transport, base_url="http://test", timeout=timeout
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. OpenAPI Spec Integrity
# ---------------------------------------------------------------------------


class TestOpenAPISpecIntegrity:
    """Verify the YAML spec matches the live FastAPI spec."""

    def test_yaml_has_all_live_paths(self, openapi_spec, openapi_live):
        """Every path from the live app must exist in the YAML spec."""
        live_paths = set(openapi_live["paths"].keys())
        yaml_paths = set(openapi_spec["paths"].keys())
        missing = live_paths - yaml_paths
        assert not missing, f"Paths in live app but missing from YAML: {missing}"

    def test_yaml_has_no_extra_paths(self, openapi_spec, openapi_live):
        """YAML spec must not contain paths removed from the app."""
        live_paths = set(openapi_live["paths"].keys())
        yaml_paths = set(openapi_spec["paths"].keys())
        extra = yaml_paths - live_paths
        assert not extra, f"Paths in YAML but not in live app: {extra}"

    def test_all_schemas_present(self, openapi_spec, openapi_live):
        """All component schemas from live app must be in YAML."""
        live_schemas = set(openapi_live.get("components", {}).get("schemas", {}).keys())
        yaml_schemas = set(openapi_spec.get("components", {}).get("schemas", {}).keys())
        missing = live_schemas - yaml_schemas
        assert not missing, f"Schemas missing from YAML: {missing}"

    def test_version_matches(self, openapi_spec, openapi_live):
        """API version must match between YAML and live app."""
        assert openapi_spec["info"]["version"] == openapi_live["info"]["version"]

    def test_all_methods_match(self, openapi_spec, openapi_live):
        """HTTP methods for each path must match between YAML and live."""
        http_methods = {
            "get",
            "post",
            "put",
            "delete",
            "patch",
            "head",
            "options",
            "trace",
        }
        for path in openapi_live["paths"]:
            live_methods = set(openapi_live["paths"][path].keys()) & http_methods
            yaml_methods = (
                set(openapi_spec["paths"].get(path, {}).keys()) & http_methods
            )
            assert (
                live_methods == yaml_methods
            ), f"Method mismatch for {path}: live={live_methods}, yaml={yaml_methods}"


# ---------------------------------------------------------------------------
# 2. Wizard Endpoint Validation
# ---------------------------------------------------------------------------


class TestWizardEndpointValidation:
    """Verify wizard endpoints validate input correctly."""

    @pytest.mark.asyncio
    async def test_check_ports_requires_valid_ip(self, client):
        """POST /api/setup/wizard/check-ports rejects invalid IP."""
        response = await client.post(
            "/api/setup/wizard/check-ports",
            json={"device_ip": "not-an-ip"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_check_ports_rejects_empty_body(self, client):
        """POST /api/setup/wizard/check-ports rejects empty body."""
        response = await client.post(
            "/api/setup/wizard/check-ports",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_modify_config_requires_target_addr(self, client):
        """POST /api/setup/wizard/modify-config rejects missing target_addr."""
        response = await client.post(
            "/api/setup/wizard/modify-config",
            json={"device_ip": "192.168.1.100"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_modify_config_rejects_invalid_target_addr(self, client):
        """POST /api/setup/wizard/modify-config rejects shell injection."""
        response = await client.post(
            "/api/setup/wizard/modify-config",
            json={
                "device_ip": "192.168.1.100",
                "target_addr": "; rm -rf /",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_modify_config_accepts_valid_formats(self, client):
        """POST /api/setup/wizard/modify-config accepts various URL formats.

        The endpoint should accept the request body (200 or 500 depending
        on SSH connectivity), but NOT return 422 validation error.
        """
        valid_addrs = [
            "http://192.168.1.100:7777",
            "192.168.1.100",
            "oct.local",
            "http://myserver:8080",
            "myserver",
        ]
        # Mock SSH to avoid hanging on real connection attempts
        with patch("opencloudtouch.setup.wizard_routes.ssh_operation") as mock_ssh:
            mock_ctx = AsyncMock()
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_service = AsyncMock()
            mock_service.modify_bmx_url.return_value = AsyncMock(
                success=True, backup_path="/tmp/bak", diff="", error=None
            )
            with patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchConfigService",
                return_value=mock_service,
            ):
                for addr in valid_addrs:
                    response = await client.post(
                        "/api/setup/wizard/modify-config",
                        json={"device_ip": "192.168.1.100", "target_addr": addr},
                    )
                    # 422 = validation error (BAD)
                    assert (
                        response.status_code != 422
                    ), f"target_addr={addr!r} rejected with 422: {response.text}"

    @pytest.mark.asyncio
    async def test_modify_hosts_requires_target_addr(self, client):
        """POST /api/setup/wizard/modify-hosts rejects missing target_addr."""
        response = await client.post(
            "/api/setup/wizard/modify-hosts",
            json={"device_ip": "192.168.1.100"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_verify_redirect_validates_domain(self, client):
        """POST /api/setup/wizard/verify-redirect rejects shell metacharacters."""
        response = await client.post(
            "/api/setup/wizard/verify-redirect",
            json={
                "device_ip": "192.168.1.100",
                "domain": "$(evil-cmd)",
                "expected_ip": "192.168.1.200",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_backup_rejects_invalid_ip(self, client):
        """POST /api/setup/wizard/backup rejects invalid IP."""
        response = await client.post(
            "/api/setup/wizard/backup",
            json={"device_ip": "999.999.999.999"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_server_info_returns_200(self, client):
        """GET /api/setup/wizard/server-info returns valid response."""
        response = await client.get("/api/setup/wizard/server-info")
        assert response.status_code == 200
        data = response.json()
        assert "server_url" in data
        assert "default_port" in data
        assert data["default_port"] == 7777

    @pytest.mark.asyncio
    async def test_restore_requires_backup_path(self, client):
        """POST /api/setup/wizard/restore-config rejects missing backup_path."""
        response = await client.post(
            "/api/setup/wizard/restore-config",
            json={"device_ip": "192.168.1.100"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 3. Core Endpoint Contracts
# ---------------------------------------------------------------------------


class TestCoreEndpointContracts:
    """Verify core (non-wizard) endpoints respond correctly."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """GET /health must always return 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_openapi_json_available(self, client):
        """GET /openapi.json must return valid OpenAPI spec."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["openapi"].startswith("3.")
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_discover_endpoint_exists_in_openapi(self, client):
        """GET /api/devices/discover must be documented in OpenAPI."""
        response = await client.get("/openapi.json")
        spec = response.json()
        assert "/api/devices/discover" in spec["paths"]


# ---------------------------------------------------------------------------
# 4. Response Schema Validation
# ---------------------------------------------------------------------------


class TestResponseSchemas:
    """Verify key response models match documented schemas."""

    @pytest.mark.asyncio
    async def test_port_check_response_schema(self, client):
        """PortCheckResponse fields must match spec."""
        from opencloudtouch.setup.api_models import PortCheckResponse

        # Construct minimal valid response
        resp = PortCheckResponse(
            success=True, message="OK", has_ssh=True, has_telnet=False
        )
        data = resp.model_dump()
        assert set(data.keys()) == {"success", "message", "has_ssh", "has_telnet"}

    @pytest.mark.asyncio
    async def test_backup_response_schema(self, client):
        """BackupResponse fields must match spec."""
        from opencloudtouch.setup.api_models import BackupResponse

        resp = BackupResponse(
            success=True,
            message="Backup complete",
            volumes=[{"name": "/mnt/nv", "size_mb": 12.5}],
            total_size_mb=12.5,
            total_duration_seconds=3.2,
        )
        data = resp.model_dump()
        expected_keys = {
            "success",
            "message",
            "volumes",
            "total_size_mb",
            "total_duration_seconds",
        }
        assert set(data.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_config_modify_response_schema(self, client):
        """ConfigModifyResponse fields must match spec."""
        from opencloudtouch.setup.api_models import ConfigModifyResponse

        resp = ConfigModifyResponse(
            success=True,
            message="Config modified",
            backup_path="/mnt/nv/backup.xml",
            diff="- old\n+ new",
            old_url="bmx.bose.com",
            new_url="192.168.1.100",
        )
        data = resp.model_dump()
        expected_keys = {
            "success",
            "message",
            "backup_path",
            "diff",
            "old_url",
            "new_url",
        }
        assert set(data.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_verify_redirect_response_schema(self, client):
        """VerifyRedirectResponse fields must match spec."""
        from opencloudtouch.setup.api_models import VerifyRedirectResponse

        resp = VerifyRedirectResponse(
            success=True,
            domain="bmx.bose.com",
            resolved_ip="192.168.1.100",
            matches_expected=True,
            message="OK",
        )
        data = resp.model_dump()
        expected_keys = {
            "success",
            "domain",
            "resolved_ip",
            "matches_expected",
            "message",
            "expected_ip",
        }
        assert set(data.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_list_backups_response_schema(self, client):
        """ListBackupsResponse fields must match spec."""
        from opencloudtouch.setup.api_models import ListBackupsResponse

        resp = ListBackupsResponse(
            success=True,
            config_backups=["/backup1.xml"],
            hosts_backups=["/hosts.bak"],
        )
        data = resp.model_dump()
        expected_keys = {"success", "config_backups", "hosts_backups"}
        assert set(data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 5. OpenAPI Schema Coverage
# ---------------------------------------------------------------------------


class TestOpenAPISchemaCoverage:
    """Verify all Pydantic models are in the OpenAPI spec."""

    def test_wizard_request_models_in_spec(self, openapi_live):
        """All wizard request models must appear in component schemas."""
        schemas = openapi_live.get("components", {}).get("schemas", {})
        expected = [
            "PortCheckRequest",
            "BackupRequest",
            "ConfigModifyRequest",
            "HostsModifyRequest",
            "RestoreRequest",
            "VerifyRedirectRequest",
            "ListBackupsRequest",
        ]
        for model_name in expected:
            assert model_name in schemas, f"{model_name} missing from OpenAPI schemas"

    def test_wizard_response_models_in_spec(self, openapi_live):
        """All wizard response models must appear in component schemas."""
        schemas = openapi_live.get("components", {}).get("schemas", {})
        expected = [
            "PortCheckResponse",
            "BackupResponse",
            "ConfigModifyResponse",
            "HostsModifyResponse",
            "RestoreResponse",
            "VerifyRedirectResponse",
            "ListBackupsResponse",
        ]
        for model_name in expected:
            assert model_name in schemas, f"{model_name} missing from OpenAPI schemas"

    def test_target_addr_documented_in_config_modify(self, openapi_live):
        """ConfigModifyRequest must document target_addr field."""
        schemas = openapi_live["components"]["schemas"]
        config_req = schemas.get("ConfigModifyRequest", {})
        properties = config_req.get("properties", {})
        assert (
            "target_addr" in properties
        ), "target_addr field missing from ConfigModifyRequest schema"

    def test_target_addr_documented_in_hosts_modify(self, openapi_live):
        """HostsModifyRequest must document target_addr field."""
        schemas = openapi_live["components"]["schemas"]
        hosts_req = schemas.get("HostsModifyRequest", {})
        properties = hosts_req.get("properties", {})
        assert (
            "target_addr" in properties
        ), "target_addr field missing from HostsModifyRequest schema"
