"""Unit tests for FallbackHandler failure detection and reactive recovery."""
import pytest
from app.controller.fallback import FallbackHandler


def test_stale_data_detection():
    handler = FallbackHandler(stale_data_threshold_seconds=60.0)

    # Fresh metrics (10s old) -> No fallback
    trigger, _ = handler.should_trigger_fallback(
        metrics_age_seconds=10.0,
        forecast_error_mape=5.0,
        service_available=True,
    )
    assert trigger is False

    # Stale metrics (90s old) -> Fallback triggered
    trigger, reason = handler.should_trigger_fallback(
        metrics_age_seconds=90.0,
        forecast_error_mape=5.0,
        service_available=True,
    )
    assert trigger is True
    assert "Metrics are stale" in reason


def test_forecast_error_threshold_detection():
    handler = FallbackHandler(forecast_error_fallback_threshold=0.30)  # 30%

    # High error (45% MAPE) -> Fallback triggered
    trigger, reason = handler.should_trigger_fallback(
        metrics_age_seconds=10.0,
        forecast_error_mape=45.0,
        service_available=True,
    )
    assert trigger is True
    assert "Forecast error exceeds safe threshold" in reason


def test_service_unavailability_detection():
    handler = FallbackHandler()
    trigger, reason = handler.should_trigger_fallback(
        metrics_age_seconds=5.0,
        forecast_error_mape=5.0,
        service_available=False,
    )
    assert trigger is True
    assert "unavailable" in reason


def test_sudden_spike_detection():
    handler = FallbackHandler()
    # Current load 180 RPS is 2x predicted 90 RPS (> 1.6x)
    trigger, reason = handler.should_trigger_fallback(
        metrics_age_seconds=5.0,
        forecast_error_mape=5.0,
        service_available=True,
        current_rps=180.0,
        predicted_rps=90.0,
    )
    assert trigger is True
    assert "Workload spike detected" in reason


def test_defensive_fallback_replica_calculation():
    handler = FallbackHandler(
        min_replicas=1,
        max_replicas=10,
        safe_capacity_per_replica=25.0,  # 80% defensive = 20 RPS
    )
    # Current load is 65 RPS -> 65 / 20 = 3.25 -> ceil = 4 replicas
    replicas, reason = handler.calculate_fallback_replicas(current_rps=65.0, current_replicas=2)
    assert replicas == 4
    assert "FALLBACK REACTIVE" in reason

    # Never scale down during fallback
    replicas_nodecrease, _ = handler.calculate_fallback_replicas(
        current_rps=10.0, current_replicas=5
    )
    assert replicas_nodecrease == 5
