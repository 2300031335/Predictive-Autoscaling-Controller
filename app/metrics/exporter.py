"""Prometheus metrics exporter for predictive autoscaling and application telemetry."""
from typing import Optional
from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Application Performance Gauges & Counters
INCOMING_RPS = Gauge(
    "incoming_requests_per_second",
    "Current incoming requests per second observed by the system",
)
REQUEST_LATENCY_MS = Histogram(
    "request_latency_ms",
    "Application request latency distribution in milliseconds",
    buckets=(5, 10, 20, 50, 100, 200, 500, 1000, 2500, 5000),
)
REQUEST_LATENCY_GAUGE = Gauge(
    "request_latency_ms_current",
    "Current instantaneous average request latency in milliseconds",
)
ERROR_RATE = Gauge(
    "error_rate",
    "Current fraction of failed or error HTTP responses (0.0 to 1.0)",
)
SUCCESSFUL_TRANSACTIONS = Counter(
    "successful_transactions_total",
    "Total cumulative number of successfully completed transactions",
)

# Autoscaling Controller & Demand Gauges
CURRENT_REPLICAS = Gauge(
    "current_replicas",
    "Number of active application replicas currently running",
)
DESIRED_REPLICAS = Gauge(
    "desired_replicas",
    "Desired number of replicas computed by the autoscaling controller",
)
PREDICTED_DEMAND_RPS = Gauge(
    "predicted_demand_rps",
    "Forecasted demand in requests per second for upcoming horizon",
)
FORECAST_ERROR_MAPE = Gauge(
    "forecast_error_mape",
    "Mean absolute percentage error (MAPE) between forecast and actual traffic",
)
SCALING_DELAY_SECONDS = Gauge(
    "scaling_delay_seconds",
    "Time elapsed from forecast signal to pod ready state",
)
SCALING_DECISIONS_TOTAL = Counter(
    "scaling_decisions_total",
    "Cumulative scaling decisions evaluated by controller",
    ["action", "policy", "is_fallback"],
)

# Resource Utilization & Cost Tracking
CPU_UTILIZATION_PERCENT = Gauge(
    "cpu_utilization_percent",
    "Average CPU utilization across active pods (0 to 100)",
)
MEMORY_UTILIZATION_PERCENT = Gauge(
    "memory_utilization_percent",
    "Average Memory utilization across active pods (0 to 100)",
)
RESOURCE_HOURS_TOTAL = Counter(
    "resource_hours_total",
    "Cumulative pod-hours consumed by application replicas",
)

# System Health
CONTROLLER_HEALTH_STATUS = Gauge(
    "controller_health_status",
    "Health status of controller (1 = healthy, 0 = degraded/unhealthy)",
)
FORECAST_SERVICE_HEALTH_STATUS = Gauge(
    "forecast_service_health_status",
    "Health status of forecasting service (1 = healthy, 0 = degraded/unhealthy)",
)


class MetricsExporter:
    """Manages telemetry updates and Prometheus exposition format."""

    @staticmethod
    def update_telemetry(
        incoming_rps: float,
        latency_ms: Optional[float] = None,
        error_rate: float = 0.0,
        current_replicas: int = 1,
        desired_replicas: int = 1,
        predicted_rps: Optional[float] = None,
        forecast_error: Optional[float] = None,
        cpu_util: Optional[float] = None,
        mem_util: Optional[float] = None,
        controller_healthy: bool = True,
        forecast_healthy: bool = True,
    ):
        INCOMING_RPS.set(max(0.0, incoming_rps))
        if latency_ms is not None:
            REQUEST_LATENCY_GAUGE.set(max(0.0, latency_ms))
            REQUEST_LATENCY_MS.observe(max(0.0, latency_ms))
        ERROR_RATE.set(max(0.0, min(1.0, error_rate)))
        CURRENT_REPLICAS.set(max(1, current_replicas))
        DESIRED_REPLICAS.set(max(1, desired_replicas))

        if predicted_rps is not None:
            PREDICTED_DEMAND_RPS.set(max(0.0, predicted_rps))
        if forecast_error is not None:
            FORECAST_ERROR_MAPE.set(max(0.0, forecast_error))
        if cpu_util is not None:
            CPU_UTILIZATION_PERCENT.set(max(0.0, min(100.0, cpu_util)))
        if mem_util is not None:
            MEMORY_UTILIZATION_PERCENT.set(max(0.0, min(100.0, mem_util)))

        CONTROLLER_HEALTH_STATUS.set(1.0 if controller_healthy else 0.0)
        FORECAST_SERVICE_HEALTH_STATUS.set(1.0 if forecast_healthy else 0.0)

    @staticmethod
    def record_decision(action: str, policy: str, is_fallback: bool):
        SCALING_DECISIONS_TOTAL.labels(
            action=action, policy=policy, is_fallback=str(is_fallback).lower()
        ).inc()

    @staticmethod
    def record_success_transactions(count: int = 1):
        if count > 0:
            SUCCESSFUL_TRANSACTIONS.inc(count)

    @staticmethod
    def generate_prometheus_payload() -> bytes:
        return generate_latest(REGISTRY)
