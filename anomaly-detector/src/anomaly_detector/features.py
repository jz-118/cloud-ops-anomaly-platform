from __future__ import annotations

import numpy as np
import pandas as pd


def build_feature_frame(series_by_name: dict[str, pd.Series], rolling_window: int) -> pd.DataFrame:
    if not series_by_name:
        return pd.DataFrame()

    base = pd.concat(series_by_name, axis=1).sort_index()
    base = base.replace([np.inf, -np.inf], np.nan).interpolate(limit_direction="both").ffill().bfill()
    features: dict[str, pd.Series] = {}
    for name in base.columns:
        values = base[name].astype(float)
        rolling = values.rolling(rolling_window, min_periods=rolling_window)
        features[name] = values
        features[f"{name}__mean"] = rolling.mean()
        features[f"{name}__std"] = rolling.std(ddof=0)
        features[f"{name}__delta"] = values.diff()
        features[f"{name}__deviation"] = values - rolling.mean()

    hour = base.index.hour + base.index.minute / 60.0
    features["time__hour_sin"] = pd.Series(np.sin(2 * np.pi * hour / 24), index=base.index)
    features["time__hour_cos"] = pd.Series(np.cos(2 * np.pi * hour / 24), index=base.index)
    frame = pd.DataFrame(features, index=base.index)
    return frame.replace([np.inf, -np.inf], np.nan).dropna()

