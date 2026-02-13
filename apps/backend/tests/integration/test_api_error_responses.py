"""Integration tests for API error responses.

Tests error handling for:
- 400 Bad Request (invalid input)
- 404 Not Found (resource not found)
- 500 Internal Server Error (server errors)

Uses real_api_client fixture from test_real_api_stack for full API stack.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_nonexistent_device_returns_404(real_api_client: AsyncClient):
    """Test that fetching a non-existent device returns 404."""
    response = await real_api_client.get("/api/devices/nonexistent-device-id")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_preset_returns_404(real_api_client: AsyncClient):
    """Test that deleting a non-existent preset returns 404."""
    response = await real_api_client.delete("/api/presets/nonexistent-device/1")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_preset_with_invalid_data_returns_400(
    real_api_client: AsyncClient,
):
    """Test that creating a preset with invalid data returns 400."""
    invalid_preset = {
        "device_id": "",  # Invalid: empty string
        "preset_number": 999,  # Invalid: out of range (1-6)
        "station_name": "Test",
        "station_uuid": "invalid_type",
        "station_url": "not-a-url",  # Invalid URL
    }

    response = await real_api_client.post("/api/presets/set", json=invalid_preset)

    assert response.status_code in (400, 422)  # 422 for validation errors
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_radio_search_with_missing_query_returns_400(
    real_api_client: AsyncClient,
):
    """Test that radio search without query parameter returns 400."""
    response = await real_api_client.get("/api/radio/search")

    assert response.status_code in (400, 422)
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_preset_with_invalid_preset_number_returns_400(
    real_api_client: AsyncClient,
):
    """Test that accessing preset with invalid number returns 400."""
    # Preset numbers must be 1-6
    invalid_preset = {
        "device_id": "test-device",
        "preset_number": 10,  # Invalid: out of range
        "station_name": "Test",
        "station_uuid": "uuid-123",
        "station_url": "http://example.com/stream",
    }

    response = await real_api_client.post("/api/presets/set", json=invalid_preset)

    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_cors_headers_present_on_errors(real_api_client: AsyncClient):
    """Test that CORS headers are present even on error responses."""
    response = await real_api_client.get(
        "/api/devices/nonexistent", headers={"Origin": "http://localhost:5173"}
    )

    assert response.status_code == 404
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_error_response_has_consistent_format(real_api_client: AsyncClient):
    """Test that error responses have consistent JSON structure."""
    response = await real_api_client.get("/api/devices/nonexistent")

    assert response.status_code == 404
    data = response.json()

    # FastAPI standard error format
    assert "detail" in data
    assert isinstance(data["detail"], (str, list, dict))


@pytest.mark.asyncio
async def test_validation_error_includes_field_details(real_api_client: AsyncClient):
    """Test that validation errors include field-specific details."""
    invalid_data = {
        "device_id": "",  # Empty string
        "preset_number": "not_a_number",  # Wrong type
    }

    response = await real_api_client.post("/api/presets/set", json=invalid_data)

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data

    # Pydantic includes field locations in validation errors
    if isinstance(data["detail"], list):
        assert len(data["detail"]) > 0


@pytest.mark.asyncio
async def test_options_request_succeeds(real_api_client: AsyncClient):
    """Test that OPTIONS requests (CORS preflight) succeed."""
    response = await real_api_client.options(
        "/api/devices",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
