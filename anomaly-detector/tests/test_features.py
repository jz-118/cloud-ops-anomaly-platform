import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from anomaly_detector.features import build_feature_frame


def test_build_feature_frame_aligns_and_adds_time_features():
    index = pd.date_range("2026-01-01", periods=10, freq="min", tz="UTC")
    frame = build_feature_frame(
        {
            "cpu": pd.Series(np.arange(10), index=index, dtype=float),
            "latency": pd.Series(np.arange(10) * 2, index=index, dtype=float),
        },
        rolling_window=3,
    )

    assert len(frame) == 8
    assert {"cpu", "cpu__mean", "latency__std", "time__hour_sin"}.issubset(frame.columns)
    assert not frame.isna().any().any()


def test_build_feature_frame_handles_infinite_values():
    index = pd.date_range("2026-01-01", periods=8, freq="min", tz="UTC")
    values = pd.Series([1, 2, np.inf, 4, 5, 6, 7, 8], index=index)
    frame = build_feature_frame({"value": values}, rolling_window=2)

    assert np.isfinite(frame.to_numpy()).all()


def test_build_feature_frame_returns_empty_for_empty_prometheus_results():
    frame = build_feature_frame(
        {
            "request_rate": pd.Series(dtype="float64"),
            "latency": pd.Series(dtype="float64"),
        },
        rolling_window=5,
    )

    assert frame.empty
