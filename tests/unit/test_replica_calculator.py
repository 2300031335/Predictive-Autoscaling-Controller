"""Unit tests for ReplicaCalculator formulas, bounds, and rate constraints."""
import pytest
from app.controller.replica_calculator import ReplicaCalculator


def test_basic_replica_calculation():
    calc = ReplicaCalculator(
        min_replicas=1,
        max_replicas=10,
        safe_capacity_per_replica=25.0,
        safety_margin_percent=0.20,  # +20%
        max_scale_up_rate=4,
        max_scale_down_rate=2,
    )
    # predicted 50 RPS -> buffered: 60 RPS -> 60 / 25 = 2.4 -> ceil = 3 replicas
    replicas, reason = calc.calculate_desired_replicas(predicted_rps=50.0, current_replicas=2)
    assert replicas == 3
    assert "buffered_rps=60.0" in reason


def test_min_and_max_bounds_enforced():
    calc = ReplicaCalculator(
        min_replicas=2,
        max_replicas=8,
        safe_capacity_per_replica=20.0,
        safety_margin_percent=0.0,
        max_scale_up_rate=10,
        max_scale_down_rate=10,
    )

    # Very low traffic -> should not drop below min_replicas (2)
    replicas_low, _ = calc.calculate_desired_replicas(predicted_rps=5.0, current_replicas=2)
    assert replicas_low == 2

    # Very high traffic (500 RPS -> 25 pods) -> should not exceed max_replicas (8)
    replicas_high, _ = calc.calculate_desired_replicas(predicted_rps=500.0, current_replicas=2)
    assert replicas_high == 8


def test_scale_up_rate_limiting():
    calc = ReplicaCalculator(
        min_replicas=1,
        max_replicas=20,
        safe_capacity_per_replica=25.0,
        safety_margin_percent=0.0,
        max_scale_up_rate=3,  # at most +3 replicas in one step
        max_scale_down_rate=2,
    )

    # current=2, raw target=10 (250 RPS) -> step restricted to 2 + 3 = 5
    replicas, reason = calc.calculate_desired_replicas(predicted_rps=250.0, current_replicas=2)
    assert replicas == 5
    assert "Rate-limited" in reason


def test_scale_down_rate_limiting():
    calc = ReplicaCalculator(
        min_replicas=1,
        max_replicas=20,
        safe_capacity_per_replica=25.0,
        safety_margin_percent=0.0,
        max_scale_up_rate=3,
        max_scale_down_rate=2,  # at most -2 replicas in one step
    )

    # current=8, raw target=1 (10 RPS) -> step restricted to 8 - 2 = 6
    replicas, reason = calc.calculate_desired_replicas(predicted_rps=10.0, current_replicas=8)
    assert replicas == 6
    assert "Rate-limited" in reason
