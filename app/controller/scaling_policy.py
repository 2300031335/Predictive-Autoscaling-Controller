"""Autoscaling policy engine with cooldowns, stabilization, and decision logging."""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.config import settings
from app.controller.fallback import FallbackHandler
from app.controller.replica_calculator import ReplicaCalculator
from app.schemas import (
    ControllerStatus,
    ScalingAction,
    ScalingDecision,
    ScalingPolicyMode,
)

logger = logging.getLogger(__name__)


class ScalingPolicyEngine:
    """Coordinates predictive calculation, fallback checks, cooldowns, and audit logging."""

    def __init__(
        self,
        calculator: Optional[ReplicaCalculator] = None,
        fallback_handler: Optional[FallbackHandler] = None,
        scale_up_cooldown_seconds: Optional[int] = None,
        scale_down_cooldown_seconds: Optional[int] = None,
    ):
        self.calculator = calculator or ReplicaCalculator(
            min_replicas=settings.MIN_REPLICAS,
            max_replicas=settings.MAX_REPLICAS,
            safe_capacity_per_replica=settings.SAFE_CAPACITY_PER_REPLICA,
            safety_margin_percent=settings.SAFETY_MARGIN_PERCENT,
            max_scale_up_rate=settings.MAX_SCALE_UP_RATE,
            max_scale_down_rate=settings.MAX_SCALE_DOWN_RATE,
        )
        self.fallback_handler = fallback_handler or FallbackHandler(
            stale_data_threshold_seconds=settings.STALE_DATA_THRESHOLD_SECONDS,
            forecast_error_fallback_threshold=settings.FORECAST_ERROR_FALLBACK_THRESHOLD,
            min_replicas=settings.MIN_REPLICAS,
            max_replicas=settings.MAX_REPLICAS,
            safe_capacity_per_replica=settings.SAFE_CAPACITY_PER_REPLICA,
        )
        self.scale_up_cooldown = (
            scale_up_cooldown_seconds
            if scale_up_cooldown_seconds is not None
            else settings.SCALE_UP_COOLDOWN_SECONDS
        )
        self.scale_down_cooldown = (
            scale_down_cooldown_seconds
            if scale_down_cooldown_seconds is not None
            else settings.SCALE_DOWN_COOLDOWN_SECONDS
        )

        self.current_replicas: int = 1
        self.desired_replicas: int = 1
        self.last_scale_up_time: Optional[datetime] = None
        self.last_scale_down_time: Optional[datetime] = None
        self.decision_history: List[ScalingDecision] = []
        self.total_decisions: int = 0
        self.scale_up_count: int = 0
        self.scale_down_count: int = 0

    def evaluate(
        self,
        current_replicas: int,
        predicted_rps: float,
        current_rps: float,
        metrics_age_seconds: Optional[float] = None,
        forecast_error_mape: Optional[float] = None,
        service_available: bool = True,
        current_time: Optional[datetime] = None,
    ) -> ScalingDecision:
        """Evaluates autoscaling conditions and returns an actionable ScalingDecision."""
        now = current_time or datetime.now(timezone.utc)
        self.current_replicas = current_replicas
        self.total_decisions += 1

        # 1. Check if fallback should trigger
        is_fallback, fallback_reason = self.fallback_handler.should_trigger_fallback(
            metrics_age_seconds=metrics_age_seconds,
            forecast_error_mape=forecast_error_mape,
            service_available=service_available,
            current_rps=current_rps,
            predicted_rps=predicted_rps,
        )

        if is_fallback:
            target_replicas, reason = self.fallback_handler.calculate_fallback_replicas(
                current_rps=current_rps, current_replicas=current_replicas
            )
            policy = ScalingPolicyMode.FALLBACK_REACTIVE
        else:
            target_replicas, reason = self.calculator.calculate_desired_replicas(
                predicted_rps=predicted_rps, current_replicas=current_replicas
            )
            policy = (
                ScalingPolicyMode.PREDICTIVE_LSTM
                if settings.MODEL_TYPE.lower() == "lstm"
                else ScalingPolicyMode.PREDICTIVE_PROPHET
            )

        # 2. Check Cooldowns and Stabilization
        action = ScalingAction.MAINTAIN
        final_desired = current_replicas

        if target_replicas > current_replicas:
            # Scale-up request
            if self.last_scale_up_time is not None:
                elapsed = (now - self.last_scale_up_time).total_seconds()
                if elapsed < self.scale_up_cooldown:
                    action = ScalingAction.MAINTAIN
                    reason += f" [Cooldown active: scale-up locked for {self.scale_up_cooldown - elapsed:.1f}s]"
                    final_desired = current_replicas
                else:
                    action = ScalingAction.SCALE_UP
                    final_desired = target_replicas
                    self.last_scale_up_time = now
                    self.scale_up_count += 1
            else:
                action = ScalingAction.SCALE_UP
                final_desired = target_replicas
                self.last_scale_up_time = now
                self.scale_up_count += 1

        elif target_replicas < current_replicas:
            # Scale-down request
            if self.last_scale_down_time is not None:
                elapsed = (now - self.last_scale_down_time).total_seconds()
                if elapsed < self.scale_down_cooldown:
                    action = ScalingAction.MAINTAIN
                    reason += f" [Cooldown active: scale-down locked for {self.scale_down_cooldown - elapsed:.1f}s]"
                    final_desired = current_replicas
                else:
                    action = ScalingAction.SCALE_DOWN
                    final_desired = target_replicas
                    self.last_scale_down_time = now
                    self.scale_down_count += 1
            else:
                action = ScalingAction.SCALE_DOWN
                final_desired = target_replicas
                self.last_scale_down_time = now
                self.scale_down_count += 1

        else:
            action = ScalingAction.MAINTAIN
            final_desired = current_replicas
            reason += " [Traffic balanced: current replicas match demand]"

        self.desired_replicas = final_desired

        decision = ScalingDecision(
            timestamp=now,
            current_replicas=current_replicas,
            predicted_rps=predicted_rps,
            desired_replicas=final_desired,
            action=action,
            reason=reason,
            active_policy=policy,
            is_fallback=is_fallback,
            fallback_reason=fallback_reason,
            target_deployment=settings.TARGET_DEPLOYMENT_NAME,
        )

        self.decision_history.append(decision)
        if len(self.decision_history) > 1000:
            self.decision_history.pop(0)

        logger.info(
            "Scaling decision: action=%s, desired=%d (current=%d), policy=%s, fallback=%s, reason='%s'",
            action.value,
            final_desired,
            current_replicas,
            policy.value,
            is_fallback,
            reason,
        )
        return decision

    def get_status(self) -> ControllerStatus:
        """Returns the current status of the controller."""
        last_decision = self.decision_history[-1] if self.decision_history else None
        return ControllerStatus(
            status="running",
            active_policy=(
                last_decision.active_policy
                if last_decision
                else ScalingPolicyMode.PREDICTIVE_PROPHET
            ),
            current_replicas=self.current_replicas,
            desired_replicas=self.desired_replicas,
            last_decision=last_decision,
            is_fallback=last_decision.is_fallback if last_decision else False,
            fallback_reason=last_decision.fallback_reason if last_decision else None,
            total_decisions_count=self.total_decisions,
            scale_up_count=self.scale_up_count,
            scale_down_count=self.scale_down_count,
        )


# Global singleton instance
controller_engine = ScalingPolicyEngine()
