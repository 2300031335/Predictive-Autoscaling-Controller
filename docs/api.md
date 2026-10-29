# API Reference Documentation

The Predictive Autoscaling Service exposes REST endpoints over HTTP/1.1 on port `8000`.

## Endpoints Summary

| Method | Path | Summary | Content-Type |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Health & Readiness check | `application/json` |
| `POST` | `/forecast` | Generate load forecast from historical trace | `application/json` |
| `GET` | `/forecast/latest` | Retrieve latest cached forecast | `application/json` |
| `GET` | `/controller/status` | Controller status, active policy & history | `application/json` |
| `POST` | `/controller/evaluate` | Trigger on-demand scaling evaluation | `application/json` |
| `GET` | `/metrics/keda` | KEDA External Scaler JSON metric format | `application/json` |
| `GET` | `/metrics` | Prometheus exposition telemetry | `text/plain; version=0.0.4` |

---

### 1. `GET /health`
Returns the status of the forecasting service and scaling controller.
```json
{
  "status": "healthy",
  "app_name": "predictive-autoscaler",
  "version": "1.0.0",
  "environment": "development",
  "timestamp": "2026-10-29T16:00:00Z",
  "forecasting_ready": true,
  "controller_ready": true
}
```

### 2. `POST /forecast`
Generates predictions for a specified horizon from historical metric points.
**Request Body**:
```json
{
  "horizon_minutes": 5,
  "interval_seconds": 60,
  "history": [
    {
      "timestamp": "2026-01-01T00:00:00Z",
      "requests_per_second": 32.5
    },
    {
      "timestamp": "2026-01-01T00:01:00Z",
      "requests_per_second": 34.0
    }
  ]
}
```
**Response (200 OK)**:
```json
{
  "status": "success",
  "model_type": "prophet",
  "model_version": "1.0.0",
  "generated_at": "2026-01-01T00:05:00Z",
  "horizon_minutes": 5,
  "predictions": [
    {
      "timestamp": "2026-01-01T00:06:00Z",
      "predicted_requests_per_second": 36.2,
      "lower_bound": 31.0,
      "upper_bound": 41.5
    }
  ],
  "mean_predicted_rps": 36.2,
  "max_predicted_rps": 41.5
}
```

### 3. `GET /metrics/keda`
Endpoint queried by KEDA external scaler.
```json
{
  "metric_name": "desired_replicas",
  "value": 4,
  "timestamp": "2026-10-29T16:00:00Z"
}
```

### 4. `GET /metrics`
Returns Prometheus metrics including `incoming_requests_per_second`, `desired_replicas`, `current_replicas`, `forecast_error_mape`, and `request_latency_ms`.
