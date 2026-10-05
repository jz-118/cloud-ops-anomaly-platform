from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler


@dataclass
class ModelBundle:
    scaler: RobustScaler
    model: IsolationForest
    columns: list[str]
    threshold: float
    score_scale: float

    @classmethod
    def fit(cls, frame: pd.DataFrame, contamination: float, random_state: int = 42) -> "ModelBundle":
        scaler = RobustScaler()
        values = scaler.fit_transform(frame)
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
            n_jobs=1,
        )
        model.fit(values)
        raw_scores = model.score_samples(values)
        threshold = float(np.quantile(raw_scores, contamination))
        score_scale = max(float(np.std(raw_scores)), 1e-6)
        return cls(scaler, model, list(frame.columns), threshold, score_scale)

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        aligned = frame.reindex(columns=self.columns)
        if aligned.isna().any().any():
            raise ValueError("feature frame is missing model columns")
        raw = self.model.score_samples(self.scaler.transform(aligned))
        distance = np.clip((self.threshold - raw) / self.score_scale, -20.0, 20.0)
        return 1.0 / (1.0 + np.exp(-distance))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path) -> "ModelBundle":
        loaded = joblib.load(path)
        if not isinstance(loaded, cls):
            raise TypeError(f"unexpected model type in {path}")
        return loaded

