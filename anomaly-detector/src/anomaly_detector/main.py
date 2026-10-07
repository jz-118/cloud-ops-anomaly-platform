from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import signal
import threading
import time

from prometheus_client import start_http_server

from .config import Settings, TargetConfig, load_targets
from .features import build_feature_frame
from .metrics import (
    ANOMALY_SCORE,
    EVALUATION_DURATION,
    EVALUATION_FAILURES,
    LAST_EVALUATION_TIMESTAMP,
    LAST_TRAINING_TIMESTAMP,
    MODEL_READY,
    TRAINING_SAMPLES,
)
from .model import ModelBundle
from .prometheus import PrometheusClient

LOGGER = logging.getLogger(__name__)


class InsufficientSamplesError(RuntimeError):
    """The target has not collected enough history for model evaluation."""


class DetectorService:
    def __init__(self, settings: Settings, targets: list[TargetConfig]) -> None:
        self.settings = settings
        self.targets = targets
        self.client = PrometheusClient(settings.prometheus_url)
        self.models: dict[str, ModelBundle] = {}
        self.last_trained: dict[str, datetime] = {}
        self.stop_event = threading.Event()

    def _labels(self, target: TargetConfig) -> tuple[str, str, str]:
        return target.name, target.environment, target.service

    def _model_path(self, target: TargetConfig) -> Path:
        return self.settings.model_dir / f"{target.name}.joblib"

    def _load_existing_model(self, target: TargetConfig) -> None:
        path = self._model_path(target)
        if path.exists():
            try:
                self.models[target.name] = ModelBundle.load(path)
                self.last_trained[target.name] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                MODEL_READY.labels(*self._labels(target)).set(1)
            except Exception:
                LOGGER.exception("Unable to load model for %s", target.name)

    def evaluate(self, target: TargetConfig) -> None:
        labels = self._labels(target)
        with EVALUATION_DURATION.labels(target.name).time():
            now = datetime.now(timezone.utc)
            start = now - timedelta(hours=self.settings.lookback_hours)
            series = {
                name: self.client.query_range(query, start, now, self.settings.query_step_seconds)
                for name, query in target.queries.items()
            }
            frame = build_feature_frame(series, self.settings.rolling_window)
            required_samples = self.settings.minimum_samples + 1
            if len(frame) < required_samples:
                MODEL_READY.labels(*labels).set(0)
                raise InsufficientSamplesError(
                    f"target {target.name} has {len(frame)} usable samples; "
                    f"minimum is {required_samples} ({self.settings.minimum_samples} training plus one inference sample)"
                )

            trained_at = self.last_trained.get(target.name)
            should_train = target.name not in self.models or trained_at is None or (
                now - trained_at
            ).total_seconds() >= self.settings.retrain_interval_seconds
            if should_train:
                bundle = ModelBundle.fit(frame.iloc[:-1], self.settings.contamination)
                bundle.save(self._model_path(target))
                self.models[target.name] = bundle
                self.last_trained[target.name] = now
                TRAINING_SAMPLES.labels(*labels).set(len(frame) - 1)
                LAST_TRAINING_TIMESTAMP.labels(*labels).set(now.timestamp())
                MODEL_READY.labels(*labels).set(1)
                LOGGER.info("Trained %s with %d samples", target.name, len(frame) - 1)

            score = float(self.models[target.name].score(frame.tail(1))[0])
            ANOMALY_SCORE.labels(*labels, "isolation_forest").set(score)
            LAST_EVALUATION_TIMESTAMP.labels(*labels).set(now.timestamp())
            LOGGER.info("Target %s anomaly score %.4f", target.name, score)

    def run(self) -> None:
        for target in self.targets:
            self._load_existing_model(target)
        while not self.stop_event.is_set():
            started = time.monotonic()
            for target in self.targets:
                try:
                    self.evaluate(target)
                except InsufficientSamplesError as error:
                    LOGGER.warning("%s", error)
                except Exception:
                    EVALUATION_FAILURES.labels(*self._labels(target)).inc()
                    LOGGER.exception("Evaluation failed for %s", target.name)
            elapsed = time.monotonic() - started
            self.stop_event.wait(max(1.0, self.settings.evaluation_interval_seconds - elapsed))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    targets = load_targets(settings.config_path)
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    service = DetectorService(settings, targets)
    signal.signal(signal.SIGTERM, lambda *_: service.stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: service.stop_event.set())
    start_http_server(settings.listen_port)
    LOGGER.info("Metrics server listening on port %d", settings.listen_port)
    service.run()


if __name__ == "__main__":
    main()
