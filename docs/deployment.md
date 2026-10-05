# Linux deployment

## Recommended lab host

- Ubuntu Server or another systemd-based x86_64 Linux distribution
- 4 vCPU, 8 GB RAM, and 30 GB free disk
- Docker Engine, Git, curl, Helm 3, and kubectl
- Outbound Internet access for images and Helm charts

## Install

```bash
git clone <repository-url>
cd cloud-ops-anomaly-platform
make check
make install-k3s
make install-monitoring
cp .env.example .env
# Edit .env with SMTP settings.
make secrets
make deploy
make verify
```

The detector needs roughly one hour of one-minute samples before its first model is ready. For a quick functional test, temporarily lower `minimumSamples` in the Helm values. Do not use the lowered setting when evaluating detection quality.

## Access the UI

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
```

Retrieve the generated Grafana admin password:

```bash
kubectl get secret -n monitoring kube-prometheus-stack-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

## AWS lab host

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
# Set monitoring_cidr to the public /32 of the K3s host.
terraform init
terraform plan
terraform apply
```

Add the `node_exporter_target` Terraform output to a Prometheus scrape configuration or an additional ServiceMonitor-compatible exporter proxy. For long-running use, connect the networks privately instead of scraping over a public address.

Destroy the chargeable AWS resources after the demonstration:

```bash
terraform destroy
```

