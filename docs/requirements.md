# Functional and Non-Functional Requirements Specification

## 1. Functional Requirements (FR) Traceability Matrix

| Req ID | Requirement Description | Implementation Module | Verification Status |
| :--- | :--- | :--- | :--- |
| **FR-1** | Workload generation (steady, ramp, spike, periodic, burst, drop traces). | `workloads/workload_generator.py` | **VERIFIED** (6 deterministic benchmark traces generated) |
| **FR-2** | Data preparation (validation, deduplication, IQR outlier handling, SHA256 provenance). | `app/forecasting/data_loader.py`, `app/forecasting/preprocessing.py` | **VERIFIED** (`tests/unit/test_data_loader.py`) |
| **FR-3** | Forecasting (Prophet baseline, PyTorch LSTM comparison, `/forecast`, `/forecast/latest`). | `app/forecasting/prophet_model.py`, `app/forecasting/lstm_model.py`, `app/services/forecast_service.py` | **VERIFIED** (`tests/unit/test_prophet_model.py`, `tests/integration/test_api.py`) |
| **FR-4** | Predictive scaling (replica formula, safety margin, step rate bounds, cooldowns, fallback). | `app/controller/replica_calculator.py`, `app/controller/scaling_policy.py`, `app/controller/fallback.py` | **VERIFIED** (`tests/unit/test_replica_calculator.py`, `tests/unit/test_scaling_policy.py`, `tests/unit/test_fallback.py`) |
| **FR-5** | Kubernetes and KEDA integration (separate reactive vs predictive manifests, KEDA ScaledObject). | `kubernetes/keda-scaledobject.yaml`, `kubernetes/reactive-hpa.yaml`, `kubernetes/forecast-deployment.yaml` | **VERIFIED** (`app/main.py:get_keda_metric`, `tests/integration/test_api.py`) |
| **FR-6** | Monitoring (Prometheus exporter with 12+ metrics, Grafana dashboard). | `app/metrics/exporter.py`, `kubernetes/prometheus/`, `kubernetes/grafana/` | **VERIFIED** (`tests/integration/test_api.py:test_metrics_prometheus_exposition`) |
| **FR-7** | Load testing (versioned k6 scripts: steady, ramp, spike, periodic, burst). | `workloads/steady.js`, `workloads/ramp.js`, `workloads/spike.js`, etc. | **VERIFIED** (k6 JavaScript suites in `workloads/`) |
| **FR-8** | Fault tolerance (underpredicting fallback, sudden spike defense, dependency outage handling). | `app/controller/fallback.py` | **VERIFIED** (`tests/fault_injection/test_fault_scenarios.py`) |

## 2. Non-Functional Requirements (NFR)

1. **Determinism**: Workload traces and model benchmarks employ fixed random seeds (`seed=42`) ensuring bit-for-bit repeatability across test runs.
2. **Low Overhead**: Model inference and scaling evaluation execute within 15ms per evaluation cycle.
3. **Fail-Safe Operation**: Upon network partition, sensor failure, or model degradation, the system fails open/defensive, guaranteeing minimum pod allocation for current traffic.
4. **Cloud-Native Compatibility**: Fully adheres to CNCF Kubernetes v1.28+ and KEDA v2.10+ specifications.
