# Architecture

## Goals

The platform demonstrates a small hybrid monitoring environment rather than a production-scale autonomous remediation system. It centralizes Kubernetes, Linux host, application, and AWS CloudWatch metrics; applies deterministic alert rules; and augments them with unsupervised multivariate anomaly detection.

## Data flow

```text
K3s / EC2 / CloudWatch
        |
        v
Exporters and application metrics
        |
        v
Prometheus ------> Grafana
    |                 |
    | query_range     | dashboards
    v                 |
Anomaly detector      |
    | /metrics        |
    +------> Prometheus
                 |
           alert rules
                 |
           Alertmanager
                 |
               email
```

## Design decisions

### Hybrid alerting

Hard failures remain rule-based: unavailable targets, exhausted disk space, missing replicas, and known business limits are deterministic and explainable. Isolation Forest is used only for behavior that varies over time or across several related metrics.

### Prometheus remains the control point

The detector reads data through the Prometheus HTTP API and publishes its result using the Prometheus exposition format. It does not send notifications directly. This preserves one alert state machine, one routing layer, and a fallback path when the detector is unavailable.

### Feature windows

Each source metric produces its current value, rolling mean, rolling standard deviation, first difference, and deviation from the rolling mean. Cyclic hour-of-day features allow the model to represent daily patterns. Missing samples are aligned and interpolated before incomplete rolling windows are removed.

### Model lifecycle

Models are separated by target or service. They are trained on a configurable lookback window, persisted on a PVC, and retrained periodically. A minimum sample guard prevents unreliable cold-start inference. Model readiness and evaluation freshness are monitored like any other service.

### Alert noise controls

Prometheus `for` durations filter short spikes. Alertmanager groups alerts by alert name, environment, and service. Critical alerts inhibit warning alerts for the same scope, and resolved notifications are sent.

## Security boundaries

- Exporter ports are limited by AWS security groups or private tunnels.
- AWS and SMTP credentials are Kubernetes Secrets and excluded from Git.
- Containers run as non-root users.
- The EC2 instance requires IMDSv2, uses an encrypted root volume, and is administered with SSM rather than an exposed SSH port.
- The Grafana and Prometheus services are accessed through local port forwarding in the lab deployment.

## Known limitations

- The detector identifies statistical deviation, not root cause or business impact.
- A 24-hour lookback does not learn weekly seasonality; longer experiments should use at least several weeks.
- A single K3s node and local-path volumes do not provide high availability.
- Public scraping of an EC2 exporter is suitable only for a restricted lab CIDR; a VPN or private network is preferred.

