"""Unit tests for Pydantic schemas and validation rules."""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.schemas import (
    ForecastRequest,
    MetricPoint,
    ScalingAction,
    ScalingDecision,
    ScalingPolicyMode,
    TraceBatch,
)


def test_metric_point_valid():
    now = datetime.now(timezone.utc)
    point = MetricPoint(
        timestamp=now,
        requests_per_second=45.5,
        latency_ms=18.2,
        cpu_utilization=65.0,
        memory_utilization=40.0,
        current_replicas=3,
        error_rate=0.01,
    )
    assert point.requests_per_second == 45.5
    assert point.current_replicas == 3
    assert point.error_rate == 0.01


def test_metric_point_negative_rps_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        MetricPoint(
            timestamp=now,
            requests_per_second=-5.0,
        )


def test_trace_batch_chronological_order_enforced():
    now = datetime.now(timezone.utc)
    p1 = MetricPoint(timestamp=now, requests_per_second=10.0)
    p2 = MetricPoint(timestamp=now + timedelta(seconds=10), requests_per_second=20.0)
    p3 = MetricPoint(timestamp=now - timedelta(seconds=10), requests_per_second=30.0)  # out of order

    # Valid order passes
    valid_batch = TraceBatch(records=[p1, p2])
    assert len(valid_batch.records) == 2

    # Out-of-order fails
    with pytest.raises(ValidationError) as excinfo:
        TraceBatch(records=[p1, p3])
    assert "Timestamps must be strictly increasing" in str(excinfo.value)


def test_forecast_request_validation():
    now = datetime.now(timezone.utc)
    points = [
        MetricPoint(timestamp=now + timedelta(minutes=i), requests_per_second=20.0 + i)
        for i in range(10)
    ]

    req = ForecastRequest(horizon_minutes=10, interval_seconds=60, history=points)
    assert req.horizon_minutes == 10
    assert len(req.history) == 10

    # Horizon exceeds max 60 minutes
    with pytest.raises(ValidationError):
        ForecastRequest(horizon_minutes=120, history=points)

    # Insufficient points (<5)
    with pytest.raises(ValidationError):
        ForecastRequest(horizon_minutes=5, history=points[:2])


def test_scaling_decision_schema():
    decision = ScalingDecision(
        current_replicas=2,
        predicted_rps=80.0,
        desired_replicas=4,
        action=ScalingAction.SCALE_UP,
        reason="Predicted RPS 80.0 exceeds capacity for 2 replicas",
        active_policy=ScalingPolicyMode.PREDICTIVE_PROPHET,
    )
    assert decision.action == ScalingAction.SCALE_UP
    assert decision.desired_replicas == 4
    assert decision.is_fallback is False
