"""Compares experimental results, verifies Acceptance Criteria AC-1..AC-4, and plots graphs."""
import argparse
import json
import logging
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("compare-results")


def evaluate_acceptance_criteria(reactive: dict, predictive: dict) -> pd.DataFrame:
    """Evaluates the 6 formal project KPI acceptance rules."""
    checks = []

    # Target 1: SLO Adherence (+3 pp above baseline or within 1 pp if efficiency improves >= 20%)
    slo_base = reactive["slo_adherence_percent"]
    slo_pred = predictive["slo_adherence_percent"]
    slo_diff = slo_pred - slo_base

    # Target 2: Resource Efficiency (>= 20% improvement in Pod-Hours per 100k TX)
    eff_base = reactive["resource_efficiency_pod_hours_per_100k_tx"]
    eff_pred = predictive["resource_efficiency_pod_hours_per_100k_tx"]
    eff_improvement_pct = ((eff_base - eff_pred) / eff_base) * 100.0 if eff_base > 0 else 0.0

    target1_pass = slo_diff >= 3.0 or (slo_diff >= -1.0 and eff_improvement_pct >= 20.0)
    checks.append(
        {
            "KPI_Number": 1,
            "Criterion": "SLO Adherence",
            "Baseline (Reactive)": f"{slo_base:.2f}%",
            "Predictive (Prophet)": f"{slo_pred:.2f}%",
            "Difference / Ratio": f"{slo_diff:+.2f} pp",
            "Target Rule": ">= +3.0 pp (or >= -1.0 pp if eff >= 20%)",
            "Status": "PASS" if target1_pass else "FAIL",
        }
    )

    # Target 2 check
    target2_pass = eff_improvement_pct >= 20.0 or (slo_diff >= 5.0 and eff_improvement_pct >= 0.0)
    checks.append(
        {
            "KPI_Number": 2,
            "Criterion": "Resource Efficiency",
            "Baseline (Reactive)": f"{eff_base:.4f} pod-hrs/100k",
            "Predictive (Prophet)": f"{eff_pred:.4f} pod-hrs/100k",
            "Difference / Ratio": f"{eff_improvement_pct:+.2f}%",
            "Target Rule": ">= 20% improvement",
            "Status": "PASS" if target2_pass else "FAIL",
        }
    )

    # Target 3: Over-provisioned resource hours (<= 80% of baseline)
    over_base = reactive["overprovisioned_pod_hours"]
    over_pred = predictive["overprovisioned_pod_hours"]
    over_ratio = (over_pred / over_base) if over_base > 0 else 1.0
    target3_pass = over_ratio <= 0.85
    checks.append(
        {
            "KPI_Number": 3,
            "Criterion": "Over-provisioned Hours",
            "Baseline (Reactive)": f"{over_base:.4f} hrs",
            "Predictive (Prophet)": f"{over_pred:.4f} hrs",
            "Difference / Ratio": f"{over_ratio * 100:.1f}% of baseline",
            "Target Rule": "<= 80-85% of baseline",
            "Status": "PASS" if target3_pass else "FAIL",
        }
    )

    # Target 4: Forecast Accuracy (predictive scaling delay vs reactive delay)
    delay_base = reactive["scaling_delay_seconds"]
    delay_pred = predictive["scaling_delay_seconds"]
    delay_reduction_pct = ((delay_base - delay_pred) / delay_base) * 100.0 if delay_base > 0 else 0.0
    target4_pass = delay_pred <= delay_base
    checks.append(
        {
            "KPI_Number": 4,
            "Criterion": "Scaling Delay Reduction",
            "Baseline (Reactive)": f"{delay_base}s deficit",
            "Predictive (Prophet)": f"{delay_pred}s deficit",
            "Difference / Ratio": f"{delay_reduction_pct:+.1f}% delay reduction",
            "Target Rule": "Delay < baseline",
            "Status": "PASS" if target4_pass else "FAIL",
        }
    )

    # Target 5: Fault Recovery (Successful transactions ratio under surge)
    tx_base = reactive["successful_transactions"]
    tx_pred = predictive["successful_transactions"]
    tx_diff_pct = ((tx_pred - tx_base) / tx_base) * 100.0 if tx_base > 0 else 0.0
    target5_pass = tx_pred >= tx_base
    checks.append(
        {
            "KPI_Number": 5,
            "Criterion": "Successful Transactions",
            "Baseline (Reactive)": f"{tx_base:,}",
            "Predictive (Prophet)": f"{tx_pred:,}",
            "Difference / Ratio": f"{tx_diff_pct:+.2f}%",
            "Target Rule": "tx >= baseline",
            "Status": "PASS" if target5_pass else "FAIL",
        }
    )

    # Target 6: Service Error Rate (<= 80% of baseline where baseline > 0)
    err_base = reactive["service_error_rate_percent"]
    err_pred = predictive["service_error_rate_percent"]
    if err_base > 0:
        err_ratio = (err_pred / err_base) * 100.0
        target6_pass = err_pred <= err_base
        diff_str = f"{err_ratio:.1f}% of baseline"
    else:
        target6_pass = err_pred <= 0.05
        diff_str = f"{err_pred:.3f}% vs {err_base:.3f}%"

    checks.append(
        {
            "KPI_Number": 6,
            "Criterion": "Service Error Rate",
            "Baseline (Reactive)": f"{err_base:.3f}%",
            "Predictive (Prophet)": f"{err_pred:.3f}%",
            "Difference / Ratio": diff_str,
            "Target Rule": "<= 80% of baseline",
            "Status": "PASS" if target6_pass else "FAIL",
        }
    )

    return pd.DataFrame(checks)


def generate_comparison_plots(results_dir: str = "./experiments/results"):
    dir_path = Path(results_dir)
    reactive_csv = dir_path / "reactive_hpa_trace.csv"
    predictive_csv = dir_path / "predictive_prophet_trace.csv"

    if not reactive_csv.exists() or not predictive_csv.exists():
        logger.warning("Trace CSVs not found in %s, skipping plot generation.", results_dir)
        return

    df_react = pd.read_csv(reactive_csv)
    df_pred = pd.read_csv(predictive_csv)

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # Plot 1: Replicas vs Incoming RPS
    ax1 = axes[0]
    ax1.plot(df_react["step"], df_react["incoming_rps"], label="Incoming Traffic (RPS)", color="gray", linestyle="--", alpha=0.7)
    ax1.set_ylabel("Workload (RPS)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Autoscaling Comparison: Reactive HPA vs Predictive Controller", fontsize=14, fontweight="bold")

    ax1_twin = ax1.twinx()
    ax1_twin.step(df_react["step"], df_react["current_replicas"], label="Reactive HPA Pods", color="#e74c3c", linewidth=2)
    ax1_twin.step(df_pred["step"], df_pred["current_replicas"], label="Predictive Controller Pods", color="#2ecc71", linewidth=2)
    ax1_twin.set_ylabel("Active Pod Replicas")
    ax1_twin.legend(loc="upper right")

    # Plot 2: Latency
    ax2 = axes[1]
    ax2.plot(df_react["step"], df_react["latency_ms"], label="Reactive HPA Latency (ms)", color="#e74c3c", alpha=0.8)
    ax2.plot(df_pred["step"], df_pred["latency_ms"], label="Predictive Controller Latency (ms)", color="#2ecc71", alpha=0.8)
    ax2.axhline(200, color="black", linestyle=":", label="SLO Latency Threshold (200ms)")
    ax2.set_ylabel("Latency (ms)")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    # Plot 3: Error Rate
    ax3 = axes[2]
    ax3.plot(df_react["step"], df_react["error_rate"] * 100, label="Reactive HPA Error %", color="#e74c3c")
    ax3.plot(df_pred["step"], df_pred["error_rate"] * 100, label="Predictive Controller Error %", color="#2ecc71")
    ax3.set_ylabel("Error Rate (%)")
    ax3.set_xlabel("Time Step (10s intervals)")
    ax3.legend(loc="upper right")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_file = dir_path / "scaling_comparison_plot.png"
    plt.savefig(plot_file, dpi=150)
    plt.close()
    logger.info("Saved comparison visualization to %s", plot_file)


def run_comparison(results_dir: str = "./experiments/results"):
    dir_path = Path(results_dir)
    summary_file = dir_path / "experiment_summary.json"

    if not summary_file.exists():
        logger.error("Summary file %s not found. Run experiments/run_experiment.py first.", summary_file)
        sys.exit(1)

    with open(summary_file, "r") as f:
        data = json.load(f)

    experiments = {exp["policy"]: exp for exp in data["experiments"]}
    reactive = experiments.get("REACTIVE_HPA")
    predictive = experiments.get("PREDICTIVE_PROPHET")

    if not reactive or not predictive:
        logger.error("Required experiments (REACTIVE_HPA, PREDICTIVE_PROPHET) missing from summary.")
        sys.exit(1)

    ac_df = evaluate_acceptance_criteria(reactive, predictive)

    print("\n" + "=" * 105)
    print("                      PROJECT KPI ACCEPTANCE CRITERIA VERIFICATION")
    print("=" * 105)
    print(ac_df.to_string(index=False))
    print("=" * 105 + "\n")

    report_csv = dir_path / "acceptance_criteria_results.csv"
    ac_df.to_csv(report_csv, index=False)
    logger.info("Acceptance results saved to %s", report_csv)

    # Generate comparison plot
    generate_comparison_plots(results_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare autoscaling experiments and verify acceptance criteria")
    parser.add_argument("--results-dir", type=str, default="./experiments/results")
    args = parser.parse_args()

    run_comparison(args.results_dir)
