"""Fault-tolerant reactive fallback controller for abnormal conditions."""
import logging
import math
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FallbackHandler:
    """Detects invalid conditions and computes safe reactive fallback replica count."""

    def __init__(
        self,
        stale_data_threshold_seconds: float = 120.0,
        forecast_error_fallback_threshold: float = 0.35,
        min_replicas: int = 1,
        max_replicas: int = 10,
        safe_capacity_per_replica: float = 25.0,
    ):
        self.stale_threshold = stale_data_threshold_seconds
        self.error_threshold = forecast_error_fallback_threshold
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.safe_capacity = safe_capacity_per_replica

    def should_trigger_fallback(
        self,
        metrics_age_seconds: Optional[float],
        forecast_error_mape: Optional[float],
        service_available: bool,
        current_rps: Optional[float] = None,
        predicted_rps: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Evaluates health conditions and determines if fallback is required."""
        if not service_available:
            return True, "Forecasting service or control-plane dependency unavailable"

        if metrics_age_seconds is not None and metrics_age_seconds > self.stale_threshold:
            return (
                True,
                f"Metrics are stale ({metrics_age_seconds:.1f}s > threshold {self.stale_threshold:.1f}s)",
            )

        if (
            forecast_error_mape is not None
            and forecast_error_mape > (self.error_threshold * 100.0)
        ):
            return (
                True,
                f"Forecast error exceeds safe threshold ({forecast_error_mape:.1f}% > {self.error_threshold * 100:.1f}%)",
            )

        # Detect severe sudden spike where current load significantly exceeds forecast
        if current_rps is not None and predicted_rps is not None and predicted_rps > 0:
            if current_rps > (predicted_rps * 1.60):
                return (
                    True,
                    f"Workload spike detected: current {current_rps:.1f} RPS > 1.6x predicted {predicted_rps:.1f} RPS",
                )

        return False, None

    def calculate_fallback_replicas(
        self, current_rps: float, current_replicas: int
    ) -> Tuple[int, str]:
        """Calculates defensive reactive replica count based on observed current traffic."""
        # In degraded/fallback mode, operate with 20% reduced capacity per replica to safeguard SLOs
        defensive_capacity = self.safe_capacity * 0.80
        raw_replicas = math.ceil(max(1.0, current_rps) / defensive_capacity)

        # Ensure we never scale down aggressively during an unknown fault state
        fallback_replicas = max(current_replicas, raw_replicas)
        fallback_replicas = max(self.min_replicas, min(fallback_replicas, self.max_replicas))

        reason = (
            f"FALLBACK REACTIVE: current_rps={current_rps:.1f}, defensive_capacity={defensive_capacity:.1f} "
            f"-> desired={fallback_replicas}"
        )
        return fallback_replicas, reason
