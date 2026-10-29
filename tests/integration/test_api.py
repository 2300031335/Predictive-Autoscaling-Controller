"""Integration tests for FastAPI endpoints and KEDA metrics exposition."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["forecasting_ready"] is True
    assert data["controller_ready"] is True


def test_metrics_prometheus_exposition(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "incoming_requests_per_second" in res.text
    assert "desired_replicas" in res.text


def test_controller_status_endpoint(client):
    res = client.get("/controller/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "running"
    assert data["current_replicas"] >= 1
    assert data["desired_replicas"] >= 1


def test_keda_metric_endpoint(client):
    res = client.get("/metrics/keda")
    assert res.status_code == 200
    data = res.json()
    assert data["metric_name"] == "desired_replicas"
    assert data["value"] >= 1


def test_forecast_and_latest_endpoint(client):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Valid payload with 10 chronological points
    history = [
        {
            "timestamp": (now + timedelta(minutes=i)).isoformat(),
            "requests_per_second": 30.0 + 2.0 * i,
        }
        for i in range(10)
    ]
    payload = {
        "horizon_minutes": 5,
        "interval_seconds": 60,
        "history": history,
    }

    post_res = client.post("/forecast", json=payload)
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "success"
    assert len(post_data["predictions"]) == 5
    assert post_data["max_predicted_rps"] > 0

    # Query /forecast/latest
    latest_res = client.get("/forecast/latest")
    assert latest_res.status_code == 200
    latest_data = latest_res.json()
    assert latest_data["max_predicted_rps"] == post_data["max_predicted_rps"]


def test_forecast_malformed_rejected(client):
    # Empty history
    res_empty = client.post("/forecast", json={"horizon_minutes": 5, "history": []})
    assert res_empty.status_code == 422

    # Negative RPS
    res_neg = client.post(
        "/forecast",
        json={
            "horizon_minutes": 5,
            "history": [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "requests_per_second": -10.0,
                }
            ],
        },
    )
    assert res_neg.status_code == 422
