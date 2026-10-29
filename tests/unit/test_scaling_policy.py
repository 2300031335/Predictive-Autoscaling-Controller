"""Unit tests for ScalingPolicyEngine cooldowns, state changes, and history."""
from datetime import datetime, timedelta, timezone
import pytest

from app.controller.scaling_policy import ScalingPolicyEngine
from app.schemas import ScalingAction, ScalingPolicyMode


def test_cooldown_scale_up():
    engine = ScalingPolicyEngine(
        scale_up_cooldown_seconds=60,
        scale_down_cooldown_seconds=180,
    )
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Initial scale up from 1 -> 3
    d1 = engine.evaluate(
        current_replicas=1,
        predicted_rps=60.0,
        current_rps=20.0,
        current_time=t0,
    )
    assert d1.action == ScalingAction.SCALE_UP
    assert d1.desired_replicas > 1

    # Immediate second scale up 10 seconds later -> should be blocked by cooldown
    t1 = t0 + timedelta(seconds=10)
    d2 = engine.evaluate(
        current_replicas=d1.desired_replicas,
        predicted_rps=120.0,
        current_rps=60.0,
        current_time=t1,
    )
    assert d2.action == ScalingAction.MAINTAIN
    assert "Cooldown active" in d2.reason

    # After cooldown expires (65 seconds later) -> scale up allowed
    t2 = t0 + timedelta(seconds=65)
    d3 = engine.evaluate(
        current_replicas=d1.desired_replicas,
        predicted_rps=120.0,
        current_rps=60.0,
        current_time=t2,
    )
    assert d3.action == ScalingAction.SCALE_UP


def test_cooldown_scale_down():
    engine = ScalingPolicyEngine(
        scale_up_cooldown_seconds=60,
        scale_down_cooldown_seconds=180,
    )
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Scale down from 6 to 4
    d1 = engine.evaluate(
        current_replicas=6,
        predicted_rps=80.0,
        current_rps=80.0,
        current_time=t0,
    )
    assert d1.action == ScalingAction.SCALE_DOWN
    assert d1.desired_replicas == 4

    # Another scale down 60 seconds later -> blocked by 180s cooldown
    t1 = t0 + timedelta(seconds=60)
    d2 = engine.evaluate(
        current_replicas=4,
        predicted_rps=20.0,
        current_rps=20.0,
        current_time=t1,
    )
    assert d2.action == ScalingAction.MAINTAIN
    assert "Cooldown active" in d2.reason
