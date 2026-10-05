from datetime import datetime, timezone
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from prometheus_client import generate_latest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from anomaly_detector.config import Settings, TargetConfig
from anomaly_detector.main import DetectorService


class FakePrometheusClient:
    def __init__(self) -> None:
        index = pd.date_range(datetime.now(timezone.utc), periods=90, freq="min")
        self.series = {
            "cpu_query": pd.Series(np.linspace(20, 35, len(index)), index=index),
            "latency_query": pd.Series(np.linspace(0.08, 0.12, len(index)), index=index),
        }

    def query_range(self, query, start, end, step_seconds):
        return self.series[query]


def test_service_trains_persists_and_scores_target(tmp_path):
    settings = Settings(
        prometheus_url="http://prometheus.invalid",
        config_path=tmp_path / "targets.yaml",
        model_dir=tmp_path / "models",
        lookback_hours=24,
        query_step_seconds=60,
        evaluation_interval_seconds=60,
        retrain_interval_seconds=21600,
        minimum_samples=60,
        contamination=0.03,
        rolling_window=5,
        listen_port=8080,
    )
    target = TargetConfig(
        name="demo-api-test",
        environment="test",
        service="demo-api",
        queries={"cpu": "cpu_query", "latency": "latency_query"},
    )
    service = DetectorService(settings, [target])
    service.client = FakePrometheusClient()

    service.evaluate(target)

    assert target.name in service.models
    assert (settings.model_dir / "demo-api-test.joblib").is_file()
    assert service.last_trained[target.name].tzinfo is timezone.utc
    metrics = generate_latest().decode("utf-8")
    assert 'ops_anomaly_score{environment="test",model="isolation_forest",service="demo-api"' in metrics

