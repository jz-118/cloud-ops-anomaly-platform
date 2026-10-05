# Demo scenarios

## 1. Baseline collection

Generate normal traffic until the detector reports `ops_anomaly_model_ready == 1`. The default configuration needs at least 60 usable one-minute samples, plus the rolling-window warm-up period.

## 2. Static error-rate alert

Generate more than five minutes of failed requests:

```bash
kubectl run demo-errors -n cloud-ops --rm -it --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?fail=true"; sleep 1; done'
```

The `CloudOpsDemoHighErrorRate` rule should fire and Alertmanager should produce a grouped email.

## 3. Multivariate anomaly

After a stable baseline, inject both latency and errors:

```bash
kubectl run demo-anomaly -n cloud-ops --rm -it --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?latency_ms=1500&fail=true"; sleep 1; done'
```

Observe P95 latency, error rate, and `ops_anomaly_score` together in Grafana. The anomaly alert requires a score above 0.8 for five minutes.

## 4. Alert inhibition

Scale the demo deployment to zero and observe the target-down alert. Confirm that critical alerts suppress warning-level symptoms sharing the same environment and service labels.

## Evidence to capture

- Grafana baseline and injected anomaly panels.
- Prometheus target and rule states.
- Alertmanager grouped firing and resolved notifications.
- Model logs showing sample count and score.
- Terraform plan and the restricted AWS security group.
