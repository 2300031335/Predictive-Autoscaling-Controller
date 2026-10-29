"""Data preprocessing, cleaning, gap filling, and Prophet dataset transformation."""
import logging
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TracePreprocessor:
    """Cleans time-series data, aggregates intervals, and prepares Prophet inputs."""

    def __init__(
        self,
        interval_seconds: int = 60,
        outlier_iqr_threshold: Optional[float] = 3.0,
        max_missing_gap_fill_limit: int = 5,
    ):
        self.interval_seconds = interval_seconds
        self.outlier_iqr_threshold = outlier_iqr_threshold
        self.max_missing_gap_fill_limit = max_missing_gap_fill_limit

    def clean_and_resample(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, any]]:
        """Deduplicates, resamples to regular frequency, interpolates small gaps, and bounds RPS."""
        if df.empty:
            raise ValueError("Cannot preprocess an empty DataFrame.")

        df_work = df.copy()
        raw_count = len(df_work)

        # 1. Deduplicate identical timestamps
        df_work = (
            df_work.groupby("timestamp", as_index=False)
            .agg({"requests_per_second": "mean"})
            .sort_values("timestamp")
        )
        dedup_count = len(df_work)
        duplicates_removed = raw_count - dedup_count

        # 2. Resample to continuous time grid
        df_work = df_work.set_index("timestamp")
        rule = f"{self.interval_seconds}s"
        resampled = df_work.resample(rule).mean()

        missing_count = int(resampled["requests_per_second"].isna().sum())

        # Forward fill small missing intervals up to limit, then backward fill or zero
        resampled["requests_per_second"] = (
            resampled["requests_per_second"]
            .ffill(limit=self.max_missing_gap_fill_limit)
            .bfill(limit=self.max_missing_gap_fill_limit)
            .fillna(0.0)
        )

        resampled = resampled.reset_index()

        # 3. Outlier detection and capping
        outliers_detected = 0
        if self.outlier_iqr_threshold is not None and len(resampled) > 10:
            q25 = resampled["requests_per_second"].quantile(0.25)
            q75 = resampled["requests_per_second"].quantile(0.75)
            iqr = q75 - q25
            upper_bound = q75 + (self.outlier_iqr_threshold * iqr)
            lower_bound = max(0.0, q25 - (self.outlier_iqr_threshold * iqr))

            outlier_mask = (resampled["requests_per_second"] > upper_bound) | (
                resampled["requests_per_second"] < lower_bound
            )
            outliers_detected = int(outlier_mask.sum())
            resampled.loc[resampled["requests_per_second"] > upper_bound, "requests_per_second"] = upper_bound
            resampled.loc[resampled["requests_per_second"] < lower_bound, "requests_per_second"] = lower_bound

        # 4. Enforce non-negativity
        resampled["requests_per_second"] = resampled["requests_per_second"].clip(lower=0.0)

        stats = {
            "raw_records": raw_count,
            "deduplicated_records": dedup_count,
            "duplicates_removed": duplicates_removed,
            "resampled_records": len(resampled),
            "missing_points_interpolated": missing_count,
            "outliers_adjusted": outliers_detected,
            "interval_seconds": self.interval_seconds,
        }
        return resampled, stats

    def to_prophet_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Converts cleaned DataFrame to Prophet format with columns 'ds' and 'y'."""
        if "timestamp" not in df.columns or "requests_per_second" not in df.columns:
            raise ValueError("Input DataFrame must contain 'timestamp' and 'requests_per_second'.")

        prophet_df = pd.DataFrame(
            {
                "ds": pd.to_datetime(df["timestamp"]),
                "y": df["requests_per_second"].astype(float),
            }
        ).sort_values("ds").reset_index(drop=True)

        return prophet_df
