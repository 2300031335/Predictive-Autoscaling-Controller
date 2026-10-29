"""Synthetic workload trace generator for realistic autoscaling benchmarks."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd


class WorkloadGenerator:
    """Generates deterministic, parameterized time-series workload traces."""

    def __init__(
        self,
        start_time: Optional[datetime] = None,
        interval_seconds: int = 10,
        random_seed: int = 42,
    ):
        self.start_time = start_time or datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.interval_seconds = interval_seconds
        self.random_seed = random_seed
        self.rng = np.random.default_rng(random_seed)

    def _create_timestamps(self, total_points: int) -> List[datetime]:
        return [
            self.start_time + timedelta(seconds=i * self.interval_seconds)
            for i in range(total_points)
        ]

    def generate_steady(
        self, duration_minutes: int = 60, base_rps: float = 50.0, noise_std: float = 2.0
    ) -> pd.DataFrame:
        """Steady traffic with Gaussian noise."""
        total_points = int((duration_minutes * 60) / self.interval_seconds)
        timestamps = self._create_timestamps(total_points)
        noise = self.rng.normal(0, noise_std, total_points)
        rps = np.clip(base_rps + noise, a_min=1.0, a_max=None)
        return self._format_dataframe(timestamps, rps, "steady")

    def generate_ramp(
        self,
        duration_minutes: int = 60,
        start_rps: float = 20.0,
        end_rps: float = 180.0,
        noise_std: float = 3.0,
    ) -> pd.DataFrame:
        """Gradual linear increase in traffic."""
        total_points = int((duration_minutes * 60) / self.interval_seconds)
        timestamps = self._create_timestamps(total_points)
        linear_trend = np.linspace(start_rps, end_rps, total_points)
        noise = self.rng.normal(0, noise_std, total_points)
        rps = np.clip(linear_trend + noise, a_min=1.0, a_max=None)
        return self._format_dataframe(timestamps, rps, "ramp")

    def generate_spike(
        self,
        duration_minutes: int = 60,
        base_rps: float = 30.0,
        spike_rps: float = 220.0,
        spike_start_min: int = 25,
        spike_duration_min: int = 10,
        noise_std: float = 2.5,
    ) -> pd.DataFrame:
        """Sudden sharp spike simulating a flash mob or promotion."""
        total_points = int((duration_minutes * 60) / self.interval_seconds)
        timestamps = self._create_timestamps(total_points)
        rps = np.full(total_points, base_rps, dtype=float)

        spike_start_idx = int((spike_start_min * 60) / self.interval_seconds)
        spike_end_idx = spike_start_idx + int((spike_duration_min * 60) / self.interval_seconds)
        spike_end_idx = min(spike_end_idx, total_points)

        # Bell-shaped spike profile
        spike_len = spike_end_idx - spike_start_idx
        if spike_len > 0:
            x = np.linspace(-2.5, 2.5, spike_len)
            bell = np.exp(-0.5 * (x**2))
            rps[spike_start_idx:spike_end_idx] += (spike_rps - base_rps) * bell

        noise = self.rng.normal(0, noise_std, total_points)
        rps = np.clip(rps + noise, a_min=1.0, a_max=None)
        return self._format_dataframe(timestamps, rps, "spike")

    def generate_periodic(
        self,
        duration_minutes: int = 120,
        base_rps: float = 60.0,
        amplitude_rps: float = 40.0,
        period_minutes: int = 30,
        noise_std: float = 3.0,
    ) -> pd.DataFrame:
        """Sinusoidal diurnal or cyclical wave pattern."""
        total_points = int((duration_minutes * 60) / self.interval_seconds)
        timestamps = self._create_timestamps(total_points)
        t_minutes = np.array([i * self.interval_seconds / 60.0 for i in range(total_points)])
        sine_wave = amplitude_rps * np.sin(2 * np.pi * t_minutes / period_minutes)
        noise = self.rng.normal(0, noise_std, total_points)
        rps = np.clip(base_rps + sine_wave + noise, a_min=1.0, a_max=None)
        return self._format_dataframe(timestamps, rps, "periodic")

    def generate_burst(
        self,
        duration_minutes: int = 90,
        base_rps: float = 40.0,
        burst_rps: float = 140.0,
        burst_interval_minutes: int = 20,
        burst_length_minutes: int = 3,
        noise_std: float = 3.0,
    ) -> pd.DataFrame:
        """Intermittent sharp bursts repeated at intervals."""
        total_points = int((duration_minutes * 60) / self.interval_seconds)
        timestamps = self._create_timestamps(total_points)
        rps = np.full(total_points, base_rps, dtype=float)

        interval_points = int((burst_interval_minutes * 60) / self.interval_seconds)
        burst_len_points = int((burst_length_minutes * 60) / self.interval_seconds)

        for start_idx in range(interval_points // 2, total_points, interval_points):
            end_idx = min(start_idx + burst_len_points, total_points)
            rps[start_idx:end_idx] = burst_rps

        noise = self.rng.normal(0, noise_std, total_points)
        rps = np.clip(rps + noise, a_min=1.0, a_max=None)
        return self._format_dataframe(timestamps, rps, "burst")

    def generate_composite(self, duration_minutes: int = 180) -> pd.DataFrame:
        """Multi-phase benchmark combining steady, ramp, spike, periodic, burst, and drops."""
        phase_duration = duration_minutes // 5

        df_steady = self.generate_steady(duration_minutes=phase_duration, base_rps=35.0)
        df_ramp = self.generate_ramp(
            duration_minutes=phase_duration, start_rps=35.0, end_rps=140.0
        )
        df_spike = self.generate_spike(
            duration_minutes=phase_duration,
            base_rps=140.0,
            spike_rps=230.0,
            spike_start_min=phase_duration // 3,
            spike_duration_min=phase_duration // 4,
        )
        df_periodic = self.generate_periodic(
            duration_minutes=phase_duration,
            base_rps=90.0,
            amplitude_rps=45.0,
            period_minutes=phase_duration // 2,
        )
        df_burst = self.generate_burst(
            duration_minutes=phase_duration,
            base_rps=50.0,
            burst_rps=160.0,
            burst_interval_minutes=phase_duration // 3,
        )

        all_dfs = [df_steady, df_ramp, df_spike, df_periodic, df_burst]
        combined = pd.concat(all_dfs, ignore_index=True)

        # Re-index continuous timestamps
        total_pts = len(combined)
        combined["timestamp"] = self._create_timestamps(total_pts)
        combined["pattern"] = "composite"
        return combined

    def _format_dataframe(
        self, timestamps: List[datetime], rps: np.ndarray, pattern_name: str
    ) -> pd.DataFrame:
        # Simulate realistic latency (base + non-linear congestion curve)
        # Latency increases when RPS is high (e.g. 15ms base + exponent)
        base_latency = 12.0
        simulated_latency = base_latency + (rps / 30.0) ** 1.8 + self.rng.normal(0, 1.5, len(rps))
        simulated_latency = np.clip(simulated_latency, a_min=5.0, a_max=800.0)

        df = pd.DataFrame(
            {
                "timestamp": [ts.isoformat() for ts in timestamps],
                "requests_per_second": np.round(rps, 2),
                "latency_ms": np.round(simulated_latency, 2),
                "pattern": pattern_name,
            }
        )
        return df


def generate_all_sample_traces(output_dir: str = "./data/sample", seed: int = 42):
    """Generates standard sample datasets used for benchmarks and tests."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generator = WorkloadGenerator(interval_seconds=10, random_seed=seed)

    traces = {
        "workload_steady.csv": generator.generate_steady(duration_minutes=60, base_rps=40.0),
        "workload_ramp.csv": generator.generate_ramp(duration_minutes=60, start_rps=20.0, end_rps=160.0),
        "workload_spike.csv": generator.generate_spike(duration_minutes=60, base_rps=35.0, spike_rps=220.0),
        "workload_periodic.csv": generator.generate_periodic(duration_minutes=90, base_rps=70.0, amplitude_rps=40.0),
        "workload_burst.csv": generator.generate_burst(duration_minutes=60, base_rps=40.0, burst_rps=150.0),
        "workload_composite.csv": generator.generate_composite(duration_minutes=150),
    }

    for filename, df in traces.items():
        filepath = out_path / filename
        df.to_csv(filepath, index=False)
        print(f"Generated {filepath} ({len(df)} records)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic workload traces")
    parser.add_argument("--output-dir", type=str, default="./data/sample", help="Directory to save traces")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    args = parser.parse_args()
    generate_all_sample_traces(args.output_dir, args.seed)
