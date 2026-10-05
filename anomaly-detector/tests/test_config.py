import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from anomaly_detector.config import load_targets


def test_load_targets_reads_identity_and_queries(tmp_path):
    config = tmp_path / "targets.yaml"
    config.write_text(
        """
targets:
  - name: api
    environment: k3s
    service: demo-api
    queries:
      latency: histogram_quantile(0.95, rate(example_bucket[5m]))
""".strip(),
        encoding="utf-8",
    )

    targets = load_targets(config)

    assert targets[0].name == "api"
    assert targets[0].queries["latency"].startswith("histogram_quantile")


def test_load_targets_rejects_empty_target_list(tmp_path):
    config = tmp_path / "targets.yaml"
    config.write_text("targets: []", encoding="utf-8")

    with pytest.raises(ValueError, match="no targets"):
        load_targets(config)

