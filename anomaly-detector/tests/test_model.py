import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from anomaly_detector.model import ModelBundle


def test_model_scores_strong_outlier_higher_than_normal_sample():
    rng = np.random.default_rng(42)
    training = pd.DataFrame({"cpu": rng.normal(30, 2, 300), "latency": rng.normal(0.1, 0.01, 300)})
    bundle = ModelBundle.fit(training, contamination=0.03)

    normal = pd.DataFrame({"cpu": [30.0], "latency": [0.1]})
    outlier = pd.DataFrame({"cpu": [99.0], "latency": [3.0]})

    assert bundle.score(outlier)[0] > bundle.score(normal)[0]


def test_model_round_trip_preserves_scores(tmp_path):
    rng = np.random.default_rng(7)
    training = pd.DataFrame({"cpu": rng.normal(40, 3, 120), "latency": rng.normal(0.2, 0.02, 120)})
    bundle = ModelBundle.fit(training, contamination=0.05)
    model_path = tmp_path / "model.joblib"
    bundle.save(model_path)

    restored = ModelBundle.load(model_path)
    sample = pd.DataFrame({"cpu": [85.0], "latency": [1.2]})

    assert restored.columns == bundle.columns
    assert np.allclose(restored.score(sample), bundle.score(sample))

