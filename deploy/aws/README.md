# AWS metric integration

The local K3s deployment works without AWS credentials. Enable AWS collection only after the core stack is healthy.

1. Create an IAM principal with read-only access to CloudWatch metric discovery. A minimal policy should include `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics`, `ec2:DescribeInstances`, and `tag:GetResources`.
2. Store credentials as a Kubernetes Secret; never commit them. Prefer a short-lived or workload identity mechanism when the K3s environment supports one.
3. Install Yet Another CloudWatch Exporter (YACE) using its Helm chart and `yace-config.yaml`.
4. Add a ServiceMonitor carrying the `release: kube-prometheus-stack` label.
5. Copy `targets-aws.example.yaml` entries into the anomaly detector target configuration after the corresponding metrics appear in Prometheus.

For direct EC2 host metrics, install node_exporter on the instance and expose port 9100 only to the K3s node or private tunnel. Do not expose exporter ports to `0.0.0.0/0`.

