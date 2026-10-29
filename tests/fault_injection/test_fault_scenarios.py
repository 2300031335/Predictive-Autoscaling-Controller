"""Fault injection and robustness test suite."""
from datetime import datetime, timedelta, timezone
import pytest

from app.controller.fallback import FallbackHandler
from app.controller.scaling_policy import ScalingPolicyEngine
from app.schemas import ScalingPolicyMode, TraceBatch, MetricPoint


def test_fault_scenario_forecast_severe_underpredict():
    """Fault: Forecast severely under-predicts a sudden spike.
    Expectation: System detects current_rps > 1.6 * predicted_rps and switches to FALLBACK_REACTIVE.
    """
    engine = ScalingPolicyEngine()
    current_rps = 200.0
    predicted_rps = 80.0  # severely underpredicted

    decision = engine.evaluate(
        current_replicas=3,
        predicted_rps=predicted_rps,
        current_rps=current_rps,
        service_available=True,
    )

    assert decision.is_fallback is True
    assert decision.active_policy == ScalingPolicyMode.FALLBACK_REACTIVE
    assert "Workload spike detected" in decision.fallback_reason
    assert decision.desired_replicas >= 8  # Defensive scaling to absorb spike


def test_fault_scenario_forecasting_service_outage():
    """Fault: Forecasting service dependency is offline.
    Expectation: Fallback triggers immediately, preserves availability.
    """
    engine = ScalingPolicyEngine()
    decision = engine.evaluate(
        current_replicas=2,
        predicted_rps=0.0,
        current_rps=50.0,
        service_available=False,  # Outage
    )

    assert decision.is_fallback is True
    assert decision.active_policy == ScalingPolicyMode.FALLBACK_REACTIVE
    assert "unavailable" in decision.fallback_reason
    assert decision.desired_replicas >= 2


def test_fault_scenario_stale_metrics():
    """Fault: Monitoring agent crashed, metrics are 300s old.
    Expectation: Enters fallback mode due to stale data threshold violation.
    """
    engine = ScalingPolicyEngine()
    decision = engine.evaluate(
        current_replicas=2,
        predicted_rps=40.0,
        current_rps=40.0,
        metrics_age_seconds=300.0,  # Stale (>120s)
        service_available=True,
    )

    assert decision.is_fallback is True
    assert "Metrics are stale" in decision.fallback_reason


def test_fault_scenario_out_of_order_trace_ingestion():
    """Fault: Network jitter delivers packets out-of-order.
    Expectation: Schema validation fails closed rather than corrupting time series.
    """
    now = datetime.now(timezone.utc)
    p_future = MetricPoint(timestamp=now + timedelta(seconds=60), requests_per_second=20.0)
    p_past = MetricPoint(timestamp=now, requests_per_second=30.0)

    with pytest.raises(Exception):
        TraceBatch(records=[p_future, p_past])
