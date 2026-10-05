import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from demo_app.main import ENVIRONMENT, SERVICE


def test_default_metric_identity_is_stable():
    assert ENVIRONMENT
    assert SERVICE

