"""Stream recovery endpoints: config, validation, events and mock-mode lifespan."""

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_stream_recovery_service
from opencloudtouch.main import app
from opencloudtouch.streamrecovery.models import OUTCOME_RESUMED, StreamRecoveryEvent
from tests.unit.streamrecovery.conftest import DEVICE


@pytest.fixture
def client(service):
    app.dependency_overrides[get_stream_recovery_service] = lambda: service
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestConfig:
    @pytest.mark.asyncio
    async def test_get_returns_defaults(self, client):
        response = client.get("/api/stream-recovery")
        assert response.status_code == 200
        assert response.json() == {
            "enabled": False,
            "min_play_seconds": 600,
            "max_attempts_per_hour": 3,
            "updated_at": None,
        }

    @pytest.mark.asyncio
    async def test_put_is_returned_by_the_next_get(self, client):
        body = {"enabled": True, "min_play_seconds": 300, "max_attempts_per_hour": 2}
        put = client.put("/api/stream-recovery", json=body)
        assert put.status_code == 200
        assert put.json()["updated_at"].endswith("Z")

        got = client.get("/api/stream-recovery").json()
        assert {k: got[k] for k in body} == body
        assert got["updated_at"] == put.json()["updated_at"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [59, 86401, "x", 600.5, True])
    async def test_invalid_min_play_is_a_coded_422(self, client, value):
        response = client.put(
            "/api/stream-recovery",
            json={
                "enabled": True,
                "min_play_seconds": value,
                "max_attempts_per_hour": 3,
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "stream_recovery_min_play_invalid"
        assert body["errors"][0]["path"] == "min_play_seconds"
        assert client.get("/api/stream-recovery").json()["updated_at"] is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [0, 11, "x"])
    async def test_invalid_attempts_is_a_coded_422(self, client, value):
        response = client.put(
            "/api/stream-recovery",
            json={
                "enabled": True,
                "min_play_seconds": 600,
                "max_attempts_per_hour": value,
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "stream_recovery_attempts_invalid"
        assert response.json()["errors"][0]["path"] == "max_attempts_per_hour"

    @pytest.mark.asyncio
    async def test_first_violation_wins(self, client):
        response = client.put(
            "/api/stream-recovery",
            json={"enabled": True, "min_play_seconds": 1, "max_attempts_per_hour": 99},
        )
        assert response.json()["code"] == "stream_recovery_min_play_invalid"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body",
        [
            {"enabled": "yes", "min_play_seconds": 600, "max_attempts_per_hour": 3},
            {"enabled": 1, "min_play_seconds": 600, "max_attempts_per_hour": 3},
            {"min_play_seconds": 600, "max_attempts_per_hour": 3},
            {"enabled": True, "max_attempts_per_hour": 3},
        ],
    )
    async def test_wrong_types_and_missing_fields_are_validation_errors(
        self, client, body
    ):
        response = client.put("/api/stream-recovery", json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"


class TestEvents:
    @pytest.mark.asyncio
    async def test_newest_first_with_limit(self, client, repository):
        for number in range(1, 4):
            await repository.add_event(
                StreamRecoveryEvent(
                    occurred_at=f"2026-10-26T05:5{number}:00Z",
                    device_id=DEVICE,
                    outcome=OUTCOME_RESUMED,
                    preset_number=number,
                    station_name="Radio X",
                    play_seconds=21600,
                    attempts=1,
                )
            )
        events = client.get("/api/stream-recovery/events?limit=2").json()["events"]
        assert [e["preset_number"] for e in events] == [3, 2]
        assert set(events[0]) == {
            "id",
            "occurred_at",
            "device_id",
            "preset_number",
            "station_name",
            "play_seconds",
            "outcome",
            "attempts",
            "error_code",
        }

    @pytest.mark.asyncio
    async def test_empty_log(self, client):
        assert client.get("/api/stream-recovery/events").json() == {"events": []}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("limit", [0, 101, "x"])
    async def test_limit_is_bounded(self, client, limit):
        response = client.get(f"/api/stream-recovery/events?limit={limit}")
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"


def test_mock_mode_app_starts_serves_and_stops_cleanly(monkeypatch, tmp_path):
    monkeypatch.setenv("OCT_MOCK_MODE", "true")
    monkeypatch.setenv("OCT_DB_PATH", str(tmp_path / "oct.db"))
    with TestClient(app) as live:
        service = live.app.state.stream_recovery_service
        assert service is not None
        assert live.get("/api/stream-recovery").json()["enabled"] is False
        body = {"enabled": True, "min_play_seconds": 600, "max_attempts_per_hour": 3}
        assert live.put("/api/stream-recovery", json=body).status_code == 200
        assert live.get("/api/stream-recovery/events").json() == {"events": []}
    assert service._consumer is None or service._consumer.done()
