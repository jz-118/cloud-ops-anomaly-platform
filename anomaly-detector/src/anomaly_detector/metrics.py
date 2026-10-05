from prometheus_client import Gauge, Counter, Histogram

ANOMALY_SCORE = Gauge(
    "ops_anomaly_score",
    "Normalized anomaly score where values near one are more anomalous.",
    ["target", "environment", "service", "model"],
)
MODEL_READY = Gauge(
    "ops_anomaly_model_ready",
    "Whether the anomaly model is trained and ready.",
    ["target", "environment", "service"],
)
TRAINING_SAMPLES = Gauge(
    "ops_anomaly_training_samples",
    "Number of samples used for the latest training run.",
    ["target", "environment", "service"],
)
LAST_TRAINING_TIMESTAMP = Gauge(
    "ops_anomaly_last_training_timestamp_seconds",
    "Unix timestamp of the latest successful model training run.",
    ["target", "environment", "service"],
)
LAST_EVALUATION_TIMESTAMP = Gauge(
    "ops_anomaly_last_evaluation_timestamp_seconds",
    "Unix timestamp of the latest successful evaluation.",
    ["target", "environment", "service"],
)
EVALUATION_FAILURES = Counter(
    "ops_anomaly_evaluation_failures_total",
    "Number of failed anomaly evaluations.",
    ["target", "environment", "service"],
)
EVALUATION_DURATION = Histogram(
    "ops_anomaly_evaluation_duration_seconds",
    "Time spent querying, training, and scoring a target.",
    ["target"],
)

