"""Deterministic replica calculation with safety margins, bounds, and rate limits."""
import math
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class ReplicaCalculator:
    """Calculates replica count from predicted demand using documented formulas."""

    def __init__(
        self,
        min_replicas: int = 1,
        max_replicas: int = 10,
        safe_capacity_per_replica: float = 25.0,
        safety_margin_percent: float = 0.15,
        max_scale_up_rate: int = 3,
        max_scale_down_rate: int = 2,
    ):
        if min_replicas < 1:
            raise ValueError("min_replicas must be at least 1")
        if max_replicas < min_replicas:
            raise ValueError(f"max_replicas ({max_replicas}) cannot be less than min_replicas ({min_replicas})")
        if safe_capacity_per_replica <= 0:
            raise ValueError("safe_capacity_per_replica must be positive")

        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.safe_capacity_per_replica = safe_capacity_per_replica
        self.safety_margin_percent = safety_margin_percent
        self.max_scale_up_rate = max_scale_up_rate
        self.max_scale_down_rate = max_scale_down_rate

    def calculate_desired_replicas(
        self, predicted_rps: float, current_replicas: int
    ) -> Tuple[int, str]:
        """Calculates bounded desired replicas and returns (desired_replicas, explanation).

        Formula:
          1. buffered_rps = predicted_rps * (1 + safety_margin_percent)
          2. raw_replicas = ceil(buffered_rps / safe_capacity_per_replica)
          3. bounded_by_limits = clamp(raw_replicas, min_replicas, max_replicas)
          4. bounded_by_rates = enforce max_scale_up_rate / max_scale_down_rate
        """
        # Step 1: Headroom buffer
        buffered_rps = max(0.0, float(predicted_rps)) * (1.0 + self.safety_margin_percent)

        # Step 2: Capacity conversion
        raw_replicas = math.ceil(buffered_rps / self.safe_capacity_per_replica)
        if raw_replicas < 1:
            raw_replicas = 1

        # Step 3: Absolute min/max bounds
        bounded_replicas = max(self.min_replicas, min(raw_replicas, self.max_replicas))

        # Step 4: Scaling-rate restriction
        max_allowed_up = current_replicas + self.max_scale_up_rate
        max_allowed_down = max(self.min_replicas, current_replicas - self.max_scale_down_rate)

        final_replicas = bounded_replicas
        rate_constrained = False

        if final_replicas > max_allowed_up:
            final_replicas = max_allowed_up
            rate_constrained = True
        elif final_replicas < max_allowed_down:
            final_replicas = max_allowed_down
            rate_constrained = True

        # Clamp again to absolute limits for safety
        final_replicas = max(self.min_replicas, min(final_replicas, self.max_replicas))

        reason = (
            f"predicted_rps={predicted_rps:.1f}, buffered_rps={buffered_rps:.1f}, "
            f"raw={raw_replicas}, capacity_per_replica={self.safe_capacity_per_replica}, "
            f"current={current_replicas} -> desired={final_replicas}"
        )
        if rate_constrained:
            reason += (
                f" [Rate-limited: step clamped within -{self.max_scale_down_rate}/+{self.max_scale_up_rate}]"
            )
        if bounded_replicas != raw_replicas:
            reason += f" [Bound-clamped within {self.min_replicas}..{self.max_replicas}]"

        return final_replicas, reason
