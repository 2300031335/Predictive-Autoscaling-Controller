"""Model evaluation metrics, test set comparison, and forecast accuracy analysis."""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class ForecastEvaluator:
    """Evaluates time-series forecasting performance against ground truth."""

    @staticmethod
    def calculate_metrics(
        actual: np.ndarray, predicted: np.ndarray, epsilon: float = 1e-5
    ) -> Dict[str, float]:
        """Calculates standard and domain-specific autoscaling forecast metrics."""
        actual = np.asarray(actual, dtype=float)
        predicted = np.asarray(predicted, dtype=float)

        if len(actual) != len(predicted):
            raise ValueError(
                f"Array length mismatch: actual has {len(actual)}, predicted has {len(predicted)}"
            )
        if len(actual) == 0:
            raise ValueError("Arrays cannot be empty.")

        errors = actual - predicted
        abs_errors = np.abs(errors)

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors**2)))

        # MAPE with epsilon guard to prevent divide by zero
        mape = float(np.mean(abs_errors / np.maximum(actual, epsilon))) * 100.0

        # SMAPE: symmetric percentage error
        smape_denom = (np.abs(actual) + np.abs(predicted)) / 2.0
        smape = float(np.mean(abs_errors / np.maximum(smape_denom, epsilon))) * 100.0

        # Autoscaling-critical asymmetric errors
        # Under-prediction: actual > predicted (traffic spikes that caught us under-provisioned)
        under_errors = np.maximum(0.0, errors)
        max_under_prediction = float(np.max(under_errors)) if len(under_errors) > 0 else 0.0

        # Over-prediction: predicted > actual (wasted capacity)
        over_errors = np.maximum(0.0, -errors)
        max_over_prediction = float(np.max(over_errors)) if len(over_errors) > 0 else 0.0

        return {
            "sample_count": len(actual),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "mape_percent": round(mape, 2),
            "smape_percent": round(smape, 2),
            "max_under_prediction_rps": round(max_under_prediction, 2),
            "max_over_prediction_rps": round(max_over_prediction, 2),
        }

    @classmethod
    def evaluate_models_comparison(
        cls,
        actual_test_df: pd.DataFrame,
        prophet_preds: List[float],
        lstm_preds: Optional[List[float]] = None,
    ) -> pd.DataFrame:
        """Produces a structured comparison table between baseline and predictive models."""
        y_true = actual_test_df["y"].values[: len(prophet_preds)]

        prophet_metrics = cls.calculate_metrics(y_true, np.array(prophet_preds))
        prophet_metrics["model"] = "Prophet"

        rows = [prophet_metrics]

        if lstm_preds is not None and len(lstm_preds) > 0:
            lstm_metrics = cls.calculate_metrics(y_true, np.array(lstm_preds[: len(y_true)]))
            lstm_metrics["model"] = "PyTorch_LSTM"
            rows.append(lstm_metrics)

        # Baseline: naive persistence model (predicts previous step value)
        naive_preds = np.roll(y_true, 1)
        naive_preds[0] = y_true[0]
        naive_metrics = cls.calculate_metrics(y_true, naive_preds)
        naive_metrics["model"] = "Naive_Persistence_Baseline"
        rows.append(naive_metrics)

        df_comparison = pd.DataFrame(rows)
        # Reorder columns
        cols = [
            "model",
            "sample_count",
            "mae",
            "rmse",
            "mape_percent",
            "smape_percent",
            "max_under_prediction_rps",
            "max_over_prediction_rps",
        ]
        return df_comparison[[c for c in cols if c in df_comparison.columns]]
