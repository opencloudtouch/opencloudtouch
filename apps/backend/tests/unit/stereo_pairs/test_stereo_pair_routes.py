"""Route tests for /api/stereo-pairs (lifecycle mocked)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core import error_codes as codes
from opencloudtouch.core.dependencies import get_stereo_lifecycle
from opencloudtouch.core.exceptions import CodedApiError
from opencloudtouch.main import app

PAIR = {
    "id": 7,
    "name": "Office",
    "status": "active",
    "source": "oct",
    "members": [
        {"device_id": "L1", "name": "Left", "role": "LEFT", "reachable": True},
        {"device_id": "R1", "name": "Right", "role": "RIGHT", "reachable": True},
    ],
    "warnings": [],
}


@pytest.fixture
def lifecycle():
    mock = MagicMock()
    for name in ("list_pairs", "describe", "rename", "dissolve", "repair"):
        setattr(mock, name, AsyncMock())
    mock.describe.return_value = PAIR
    app.dependency_overrides[get_stereo_lifecycle] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_stereo_lifecycle, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_list(client, lifecycle):
    lifecycle.list_pairs.return_value = [PAIR]

    response = client.get("/api/stereo-pairs")

    assert response.status_code == 200
    assert response.json()[0]["members"][1]["role"] == "RIGHT"


def test_create_returns_202_with_operation_id(client, lifecycle):
    lifecycle.start_create.return_value = SimpleNamespace(id="op1")

    response = client.post(
        "/api/stereo-pairs", json={"left_device_id": "L1", "right_device_id": "R1"}
    )

    assert response.status_code == 202
    assert response.json() == {"operation_id": "op1"}
    lifecycle.start_create.assert_called_once_with("L1", "R1", None)


def test_create_validates_body(client, lifecycle):
    assert (
        client.post("/api/stereo-pairs", json={"left_device_id": "L1"}).status_code
        == 422
    )


def test_create_with_same_device_is_coded_400(client, lifecycle):
    lifecycle.start_create.side_effect = CodedApiError(
        400, codes.STEREO_PAIR_INVALID_REQUEST, "LEFT and RIGHT must differ"
    )

    response = client.post(
        "/api/stereo-pairs", json={"left_device_id": "L1", "right_device_id": "L1"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == codes.STEREO_PAIR_INVALID_REQUEST


def test_operation_states(client, lifecycle):
    lifecycle.get_operation.return_value = SimpleNamespace(
        state="failed",
        steps={
            "preflight": "done",
            "create_left": "failed",
            "create_right": "waiting",
            "verify": "waiting",
        },
        pair=None,
        warnings=["firmware_mismatch"],
        error_code=codes.STEREO_PAIR_MARGE_FAILED,
        error_message="no",
    )

    body = client.get("/api/stereo-pairs/operations/op1").json()

    assert body["state"] == "failed"
    assert [s["key"] for s in body["steps"]] == [
        "preflight",
        "create_left",
        "create_right",
        "verify",
    ]
    assert body["error"] == {"code": codes.STEREO_PAIR_MARGE_FAILED, "message": "no"}
    assert body["warnings"] == ["firmware_mismatch"]


def test_unknown_operation_is_404(client, lifecycle):
    lifecycle.get_operation.side_effect = CodedApiError(
        404, codes.STEREO_PAIR_OPERATION_NOT_FOUND, "Unknown operation"
    )

    assert client.get("/api/stereo-pairs/operations/nope").status_code == 404


def test_rename_dissolve_repair(client, lifecycle):
    assert client.patch("/api/stereo-pairs/7", json={"name": "New"}).status_code == 200
    lifecycle.rename.assert_awaited_once_with(7, "New")
    assert client.delete("/api/stereo-pairs/7").status_code == 204
    lifecycle.dissolve.assert_awaited_once_with(7)
    assert client.post("/api/stereo-pairs/7/repair").status_code == 204
    lifecycle.repair.assert_awaited_once_with(7)


def test_dissolve_degraded_is_coded_502(client, lifecycle):
    lifecycle.dissolve.side_effect = CodedApiError(
        502, codes.STEREO_PAIR_DEGRADED, "retry"
    )

    response = client.delete("/api/stereo-pairs/7")

    assert response.status_code == 502
    assert response.json()["code"] == codes.STEREO_PAIR_DEGRADED
