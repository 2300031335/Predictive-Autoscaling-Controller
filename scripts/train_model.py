"""Trains forecasting models, evaluates accuracy on held-out split, and saves artifacts."""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from app.forecasting.data_loader import TraceDataLoader
from app.forecasting.evaluation import ForecastEvaluator
from app.forecasting.lstm_model import LSTMForecaster
from app.forecasting.preprocessing import TracePreprocessor
from app.forecasting.prophet_model import ProphetForecaster

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train-eval")


def train_and_evaluate(
    data_path: str = "./data/sample/workload_composite.csv",
    train_ratio: float = 0.80,
    save_dir: str = "./data/processed",
):
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    loader = TraceDataLoader()
    preprocessor = TracePreprocessor(interval_seconds=60)

    logger.info("Loading trace data from %s...", data_path)
    df_raw, meta = loader.load_from_csv(data_path)
    logger.info("Trace SHA256: %s, Records: %d", meta["provenance_hash"], len(df_raw))

    # Preprocess & resample
    df_clean, stats = preprocessor.clean_and_resample(df_raw)
    prophet_df = preprocessor.to_prophet_dataframe(df_clean)
    logger.info("Preprocessed into %d regular intervals", len(prophet_df))

    # Chronological Split
    train_df, test_df = TraceDataLoader.chronological_split(prophet_df, train_ratio=train_ratio)
    logger.info(
        "Chronological split: %d train records (until %s), %d test records (from %s)",
        len(train_df),
        train_df["ds"].max(),
        len(test_df),
        test_df["ds"].min(),
    )

    # 1. Fit Prophet Forecaster
    logger.info("Fitting Prophet baseline model...")
    prophet = ProphetForecaster(random_seed=42)
    prophet.fit(train_df)

    test_horizon_minutes = int(len(test_df) * 60 / 60)
    prophet_preds_pts = prophet.predict(horizon_minutes=test_horizon_minutes, interval_seconds=60)
    prophet_preds = [p.predicted_requests_per_second for p in prophet_preds_pts[: len(test_df)]]

    # Save Prophet model
    prophet_file = save_path / "prophet_model.pkl"
    prophet.save(prophet_file)

    # 2. Fit PyTorch LSTM Forecaster
    logger.info("Fitting PyTorch LSTM forecaster...")
    lstm = LSTMForecaster(lookback_window=10, epochs=35, random_seed=42)
    lstm.fit(train_df)

    lstm_preds_pts = lstm.predict(horizon_minutes=test_horizon_minutes, interval_seconds=60)
    lstm_preds = [p.predicted_requests_per_second for p in lstm_preds_pts[: len(test_df)]]

    # 3. Comprehensive Evaluation
    logger.info("Evaluating predictions on held-out test partition...")
    comparison_df = ForecastEvaluator.evaluate_models_comparison(
        actual_test_df=test_df,
        prophet_preds=prophet_preds,
        lstm_preds=lstm_preds,
    )

    print("\n" + "=" * 95)
    print("                      FORECASTING ACCURACY EVALUATION REPORT")
    print("=" * 95)
    print(comparison_df.to_string(index=False))
    print("=" * 95 + "\n")

    report_path = save_path / "model_evaluation_metrics.csv"
    comparison_df.to_csv(report_path, index=False)
    logger.info("Evaluation results saved to %s", report_path)
    return comparison_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and evaluate forecasting models")
    parser.add_argument("--data", type=str, default="./data/sample/workload_composite.csv")
    parser.add_argument("--train-ratio", type=float, default=0.80)
    parser.add_argument("--save-dir", type=str, default="./data/processed")
    args = parser.parse_args()

    train_and_evaluate(args.data, args.train_ratio, args.save_dir)
