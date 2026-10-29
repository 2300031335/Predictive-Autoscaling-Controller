"""Acceptance tests verifying KPI calculations and acceptance rules."""
import pytest
from experiments.compare_results import evaluate_acceptance_criteria


def test_acceptance_criteria_calculation_logic():
    # Synthetic baseline and predictive dicts
    reactive = {
        "slo_adherence_percent": 95.0,
        "resource_efficiency_pod_hours_per_100k_tx": 2.0,
        "overprovisioned_pod_hours": 10.0,
        "scaling_delay_seconds": 300,
        "successful_transactions": 500000,
        "service_error_rate_percent": 2.0,
    }

    # Case 1: High performance predictive run
    predictive_pass = {
        "slo_adherence_percent": 99.0,  # +4 pp (meets >= 3pp)
        "resource_efficiency_pod_hours_per_100k_tx": 1.5,  # 25% improvement (meets >= 20%)
        "overprovisioned_pod_hours": 7.0,  # 70% of base (meets <= 80%)
        "scaling_delay_seconds": 100,  # lower delay
        "successful_transactions": 520000,  # > base
        "service_error_rate_percent": 0.5,  # 25% of base (meets <= 80%)
    }

    df_results = evaluate_acceptance_criteria(reactive, predictive_pass)
    assert len(df_results) == 6
    assert (df_results["Status"] == "PASS").all()


def test_acceptance_criteria_detects_failure():
    reactive = {
        "slo_adherence_percent": 98.0,
        "resource_efficiency_pod_hours_per_100k_tx": 1.5,
        "overprovisioned_pod_hours": 5.0,
        "scaling_delay_seconds": 100,
        "successful_transactions": 500000,
        "service_error_rate_percent": 0.5,
    }

    # Degraded predictive run
    predictive_fail = {
        "slo_adherence_percent": 92.0,  # -6 pp drop -> FAIL
        "resource_efficiency_pod_hours_per_100k_tx": 2.0,  # worse efficiency -> FAIL
        "overprovisioned_pod_hours": 8.0,  # 160% of base -> FAIL
        "scaling_delay_seconds": 200,
        "successful_transactions": 480000,
        "service_error_rate_percent": 3.0,
    }

    df_results = evaluate_acceptance_criteria(reactive, predictive_fail)
    status_map = dict(zip(df_results["KPI_Number"], df_results["Status"]))
    assert status_map[1] == "FAIL"
    assert status_map[2] == "FAIL"
    assert status_map[3] == "FAIL"
