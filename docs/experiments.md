# Experimental Design and Empirical Evaluation

## 1. Experimental Design

To evaluate the proposed predictive autoscaler against the industry standard reactive Kubernetes Horizontal Pod Autoscaler (HPA), an identical 150-minute multi-phase composite workload trace was executed across both strategies.

### Workload Envelope:
- **Duration**: 150 minutes (900 data points at 10-second intervals).
- **Workload Phases**:
  1. Steady baseline traffic (35 RPS).
  2. Linear ramp traffic (35 to 140 RPS).
  3. Flash-mob spike (140 to 230 RPS).
  4. Cyclical / periodic wave traffic (45 to 135 RPS).
  5. Intermittent burst bursts (50 to 160 RPS).
- **Cluster Capacity Envelope**:
  - Safe Capacity per replica: 25 requests/second.
  - Resource Bounds: Minimum 1 replica, Maximum 10 replicas.
  - Pod Startup Delay: 30 seconds (simulating container pull, initialization, and readiness probe).
  - SLO Threshold: $\le 200\text{ ms}$ response latency.

---

## 2. Real Execution Results Summary

Source: `experiments/results/experiment_summary.json` (Generated from actual simulator execution):

| Metric | Reactive HPA Baseline | Predictive Autoscaler (Prophet) | Improvement / Delta |
| :--- | :--- | :--- | :--- |
| **Total Requests** | 799,750 | 799,750 | 0 (Identical input trace) |
| **Successful Transactions** | 790,837 | 799,111 | **+8,274 transactions (+1.05%)** |
| **Failed Requests** | 8,913 | 639 | **-8,274 failures (-92.8%)** |
| **Service Error Rate** | 1.251% | 0.218% | **-1.033 percentage points** |
| **SLO Adherence ($\le 200\text{ ms}$)** | 97.89% | 99.67% | **+1.78 percentage points** |
| **Latency p50 (Median)** | 35.80 ms | 35.70 ms | -0.10 ms |
| **Latency p95** | 100.90 ms | 76.20 ms | **-24.70 ms (-24.5%)** |
| **Latency p99** | 358.50 ms | 154.30 ms | **-204.20 ms (-57.0%)** |
| **Total Pod-Hours Consumed** | 13.7853 hrs | 11.6883 hrs | **-2.0970 hrs (-15.2%)** |
| **Over-provisioned Pod-Hours** | 5.0066 hrs | 2.8133 hrs | **-2.1933 hrs (-43.8%)** |
| **Resource Efficiency Proxy** | 1.7432 pod-hrs/100k TX | 1.4627 pod-hrs/100k TX | **+16.09% efficiency gain** |

---

## 3. Key Findings and Analysis

1. **Elimination of Severe Tail Latency**: Reactive HPA suffers a severe p99 tail latency spike of **358.5 ms** during sudden load increases because pods take 30 seconds to start after CPU thresholds are breached. In contrast, the predictive scaler scales pods before the surge, holding p99 at **154.3 ms** ($\le 200\text{ ms}$ SLO).
2. **Reduced Over-Provisioning**: Reactive HPA over-provisions during traffic drops due to conservative stabilization delays (5.01 pod-hours wasted). The predictive controller anticipates traffic drops and smoothly downscales, reducing over-provisioned hours to 2.81 hrs (**43.8% reduction**).
3. **92.8% Drop in Failed Transactions**: By avoiding pod saturation, predictive autoscaling prevented 8,274 request dropouts compared to reactive HPA.
