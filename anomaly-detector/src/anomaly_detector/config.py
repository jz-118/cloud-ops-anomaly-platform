from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

import yaml


@dataclass(frozen=True)
class TargetConfig:
    name: str
    environment: str
    service: str
    queries: dict[str, str]


@dataclass(frozen=True)
class Settings:
    prometheus_url: str
    config_path: Path
    model_dir: Path
    lookback_hours: int
    query_step_seconds: int
    evaluation_interval_seconds: int
    retrain_interval_seconds: int
    minimum_samples: int
    contamination: float
    rolling_window: int
    listen_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            prometheus_url=os.getenv("PROMETHEUS_URL", "http://prometheus-operated.monitoring.svc:9090").rstrip("/"),
            config_path=Path(os.getenv("TARGET_CONFIG", "/etc/anomaly-detector/targets.yaml")),
            model_dir=Path(os.getenv("MODEL_DIR", "/var/lib/anomaly-detector")),
            lookback_hours=int(os.getenv("LOOKBACK_HOURS", "24")),
            query_step_seconds=int(os.getenv("QUERY_STEP_SECONDS", "60")),
            evaluation_interval_seconds=int(os.getenv("EVALUATION_INTERVAL_SECONDS", "60")),
            retrain_interval_seconds=int(os.getenv("RETRAIN_INTERVAL_SECONDS", "21600")),
            minimum_samples=int(os.getenv("MINIMUM_SAMPLES", "60")),
            contamination=float(os.getenv("CONTAMINATION", "0.03")),
            rolling_window=int(os.getenv("ROLLING_WINDOW", "5")),
            listen_port=int(os.getenv("LISTEN_PORT", "8080")),
        )


def load_targets(path: Path) -> list[TargetConfig]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    targets = []
    for item in payload.get("targets", []):
        queries = item.get("queries", {})
        if not queries:
            raise ValueError(f"target {item.get('name', '<unnamed>')} has no queries")
        targets.append(
            TargetConfig(
                name=item["name"],
                environment=item["environment"],
                service=item["service"],
                queries={str(key): str(value) for key, value in queries.items()},
            )
        )
    if not targets:
        raise ValueError("target configuration contains no targets")
    return targets

