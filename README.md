# Cloud Ops Anomaly Platform

A small hybrid-cloud observability project for K3s and AWS. It combines Prometheus, Grafana, Alertmanager, deterministic alert rules, and a Python Isolation Forest service that detects multivariate deviations in time-series metrics.

The project is intentionally scoped as an interview-ready lab: it demonstrates collection, visualization, alert routing, noise reduction, model lifecycle, secure AWS access, and reproducible fault injection without claiming automatic root-cause analysis or remediation.

## What it demonstrates

- K3s infrastructure and Kubernetes workload monitoring
- Linux EC2 host metrics and optional CloudWatch collection
- Application request, error-rate, and latency metrics
- Grafana dashboards provisioned as code
- Email notifications with grouping, inhibition, deduplication, and resolved events
- Unsupervised multivariate anomaly detection using scikit-learn Isolation Forest
- Terraform-managed AWS lab infrastructure with restricted ingress and SSM access
- Linux-first deployment from a Git repository

## Architecture

```text
K3s node     Demo API       AWS EC2       CloudWatch
   |            |              |              |
node_exporter  /metrics   node_exporter      YACE
   |            |              |              |
   +------------+--------------+--------------+
                        |
                    Prometheus
                    /    |    \
                   /     |     \
             Grafana  rules  anomaly-detector
                               | query_range
                               | Isolation Forest
                               +---- /metrics ----+
                                                 |
                                             Prometheus
                                                 |
                                            Alertmanager
                                                 |
                                               email
```

See [docs/architecture.md](docs/architecture.md) for component boundaries and design decisions.

## Repository layout

```text
anomaly-detector/   Prometheus client, feature pipeline, model lifecycle, metrics
demo-app/           Instrumented HTTP workload with controlled fault parameters
deploy/             Helm chart, monitoring values, alerts, dashboards, scripts
terraform/aws/      Restricted EC2 lab host managed with Terraform
docs/               Architecture, deployment, and demonstration scenarios
```

## Quick start on Linux

Recommended lab capacity: 4 vCPU, 8 GB RAM, and 30 GB free disk on a systemd-based x86_64 Linux VM.

Prerequisites:

- Git and curl
- Docker Engine with a running daemon
- Helm 3
- kubectl (the K3s installer can provide it)
- Terraform only when creating AWS resources

```bash
git clone <repository-url>
cd cloud-ops-anomaly-platform

make install-k3s
make check
make install-monitoring

cp .env.example .env
# Edit .env with real SMTP values.
make secrets

make deploy
make verify
```

The deployment builds Linux container images locally and imports them into the K3s containerd image store. It does not require a public container registry.

Open Grafana:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

Then visit `http://127.0.0.1:3000` and open **Cloud Ops / Hybrid Environment Overview**.

## Anomaly detection behavior

For each configured target, the detector:

1. Queries a historical range through the Prometheus HTTP API.
2. Aligns samples and handles missing or non-finite values.
3. Builds rolling mean, standard deviation, delta, deviation, and daily cyclic features.
4. Trains an Isolation Forest after the minimum sample guard is satisfied.
5. Persists the model and retrains it on a schedule.
6. Exposes a normalized `ops_anomaly_score` and operational health metrics.

The alert requires a score above `0.80` for five minutes. Deterministic failures continue to use normal Prometheus rules; machine learning supplements them instead of replacing them.

## Run the demonstration

The default model needs at least 60 usable one-minute samples. After baseline collection:

```bash
make demo
```

This generates ordinary requests followed by a six-minute latency-and-error anomaly. Detailed commands and expected evidence are in [docs/demo-scenarios.md](docs/demo-scenarios.md).

## Add the AWS environment

Create the monitored EC2 host:

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
# Replace monitoring_cidr with the public /32 address of the K3s host.
terraform init
terraform plan
terraform apply
```

The instance exposes node_exporter only to `monitoring_cidr`, uses IMDSv2 and an encrypted volume, and is administered through AWS Systems Manager rather than an open SSH port.

To scrape it, copy `deploy/monitoring/values-aws.example.yaml` to `values-aws.yaml`, replace the EC2 address, and upgrade the monitoring release with both values files:

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values deploy/monitoring/values.yaml \
  --values deploy/monitoring/values-aws.yaml \
  --wait --timeout 15m
```

CloudWatch integration is optional and documented in [deploy/aws/README.md](deploy/aws/README.md).

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest anomaly-detector/tests demo-app/tests
```

On Windows, use `.venv\Scripts\python.exe` for tests. Runtime containers and shell scripts remain Linux-only.

## Secrets and cost controls

- `.env`, Terraform state, variable files, credentials, and trained models are ignored by Git.
- Do not expose node_exporter, Prometheus, Grafana, or Alertmanager broadly to the Internet.
- Destroy the EC2 lab resources with `terraform destroy` when the demonstration is complete.
- Treat anomaly output as supporting evidence, not an automated root-cause conclusion.

## License

MIT

