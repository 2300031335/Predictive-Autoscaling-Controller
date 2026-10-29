"""Pydantic schemas and models for requests, responses, metrics, and controller states."""
from datetime import datetime
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ScalingAction(str, Enum):
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    MAINTAIN = "MAINTAIN"


class ScalingPolicyMode(str, Enum):
    PREDICTIVE_PROPHET = "PREDICTIVE_PROPHET"
    PREDICTIVE_LSTM = "PREDICTIVE_LSTM"
    REACTIVE_HPA = "REACTIVE_HPA"
    FALLBACK_REACTIVE = "FALLBACK_REACTIVE"


class MetricPoint(BaseModel):
    timestamp: datetime = Field(description="ISO 8601 timestamp of measurement")
    requests_per_second: float = Field(ge=0.0, description="Incoming requests per second")
    latency_ms: Optional[float] = Field(default=None, ge=0.0, description="Average response latency in ms")
    cpu_utilization: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="CPU usage percent")
    memory_utilization: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Memory usage percent")
    current_replicas: Optional[int] = Field(default=1, ge=1, description="Number of currently active replicas")
    error_rate: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of failed requests")

    @field_validator("requests_per_second")
    @classmethod
    def validate_non_negative_rps(cls, v: float) -> float:
        if v < 0:
            raise ValueError("requests_per_second must be non-negative")
        return round(float(v), 4)


class TraceBatch(BaseModel):
    source: str = Field(default="synthetic", description="Origin of trace (e.g. synthetic, k6, prometheus)")
    records: List[MetricPoint] = Field(min_length=1, description="List of time-series metric points")

    @field_validator("records")
    @classmethod
    def validate_chronological_order(cls, records: List[MetricPoint]) -> List[MetricPoint]:
        if len(records) > 1:
            for i in range(1, len(records)):
                if records[i].timestamp <= records[i - 1].timestamp:
                    raise ValueError(
                        f"Timestamps must be strictly increasing. Violation at index {i}: "
                        f"{records[i].timestamp} <= {records[i - 1].timestamp}"
                    )
        return records


class ForecastRequest(BaseModel):
    horizon_minutes: int = Field(default=5, ge=1, le=60, description="Forecast horizon in minutes")
    interval_seconds: int = Field(default=60, ge=10, le=300, description="Interval step in seconds")
    history: List[MetricPoint] = Field(min_length=5, description="Historical request metrics for fitting")


class ForecastPoint(BaseModel):
    timestamp: datetime = Field(description="Forecasted future timestamp")
    predicted_requests_per_second: float = Field(ge=0.0, description="Forecast point estimate")
    lower_bound: float = Field(ge=0.0, description="Lower prediction interval (e.g. 80%)")
    upper_bound: float = Field(ge=0.0, description="Upper prediction interval (e.g. 80%)")


class ForecastResponse(BaseModel):
    status: str = Field(default="success")
    model_type: str = Field(description="Model used for prediction (prophet, lstm, naive)")
    model_version: str = Field(default="1.0.0")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    horizon_minutes: int
    predictions: List[ForecastPoint]
    mean_predicted_rps: float
    max_predicted_rps: float


class ScalingDecision(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    current_replicas: int = Field(ge=1)
    predicted_rps: float = Field(ge=0.0)
    desired_replicas: int = Field(ge=1)
    action: ScalingAction
    reason: str
    active_policy: ScalingPolicyMode
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    target_deployment: str = "sample-app"


class ControllerStatus(BaseModel):
    status: str = "running"
    active_policy: ScalingPolicyMode = ScalingPolicyMode.PREDICTIVE_PROPHET
    current_replicas: int = 1
    desired_replicas: int = 1
    last_decision: Optional[ScalingDecision] = None
    last_metric_timestamp: Optional[datetime] = None
    metrics_age_seconds: Optional[float] = None
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    total_decisions_count: int = 0
    scale_up_count: int = 0
    scale_down_count: int = 0


class HealthResponse(BaseModel):
    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    forecasting_ready: bool = True
    controller_ready: bool = True


class KedaMetricResponse(BaseModel):
    metric_name: str = "desired_replicas"
    value: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
