# Troubleshooting and Operational Runbook

## 1. Common Issues and Resolutions

### Issue 1: `Importing plotly failed. Interactive plots will not work.`
- **Context**: Displayed when Prophet is imported without `plotly` installed.
- **Impact**: Harmless informational notice. Prophet uses CmdStanPy for core mathematical modeling, and matplotlib is used for static visualization. Plotly is only needed for HTML-interactive browser graphs.
- **Resolution**: No action required. If interactive HTML charts are desired, install with `pip install plotly`.

### Issue 2: Fallback Controller Triggered Frequently
- **Symptom**: Controller logs show `FALLBACK REACTIVE` with reason `Workload spike detected: current X RPS > 1.6x predicted Y RPS`.
- **Cause**: The incoming traffic profile has sudden, un-patterned spikes that cannot be predicted by time-series seasonality.
- **Resolution**:
  1. Increase safety margin in `.env`: `SAFETY_MARGIN_PERCENT=0.25` (25% buffer).
  2. Adjust fallback threshold in `app/config.py`: `FORECAST_ERROR_FALLBACK_THRESHOLD=0.45`.
  3. Ensure the model has been trained on at least 24 hours of seasonal data.

### Issue 3: Stale Metrics Fallback
- **Symptom**: `Metrics are stale (150.0s > threshold 120.0s)`.
- **Cause**: The metrics ingestion pipeline or Prometheus scraper stopped emitting fresh telemetry.
- **Resolution**:
  1. Verify the scraping pod/service is healthy: `kubectl get pods -n predictive-system`.
  2. Check Prometheus target health at `http://<prometheus-ip>:9090/targets`.

### Issue 4: Dual Scaling Conflicts (HPA and KEDA Fighting)
- **Symptom**: Pod count oscillates rapidly up and down.
- **Cause**: Both `reactive-hpa.yaml` and `keda-scaledobject.yaml` are applied simultaneously to `Deployment/sample-app`.
- **Resolution**: Delete the reactive HPA when running predictive scaling:
  ```bash
  kubectl delete hpa sample-app-reactive-hpa -n predictive-system
  ```
