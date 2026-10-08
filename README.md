# Cloud Ops Anomaly Platform

基于 K3s、Prometheus 和 Isolation Forest 的混合云可观测性与异常检测平台。

平台统一采集 Linux 主机、Kubernetes 工作负载、应用服务和 AWS 资源指标，通过 Grafana 提供可视化，通过 PrometheusRule 与 Alertmanager 完成告警分组、去重、抑制和邮件通知，并使用无监督学习识别多指标关联异常。

## 核心能力

- 统一采集 Linux、Kubernetes、应用和 AWS 指标
- 使用 Prometheus、ServiceMonitor 和 YACE 构建指标链路
- 使用 Grafana 展示主机、集群、应用和异常分数
- 使用 PrometheusRule 覆盖可用性、错误率和异常检测告警
- 使用 Alertmanager 完成分组、去重、抑制、恢复通知和 SMTP 路由
- 使用 Isolation Forest 分析请求速率、错误率、P95 延迟和并发请求数
- 使用 Terraform 配置 AWS EC2、IAM、SSM 和监控网络
- 使用 Helm、Makefile 和脚本完成安装、部署与验证
- 使用 GitHub Actions 执行测试、镜像构建、Helm 校验和 Terraform 校验

## 系统架构

```text
┌──────────────────────────── K3s Cluster ────────────────────────────┐
│                                                                     │
│  Linux Host                 Kubernetes              Application API │
│      │                          │                         │           │
│ node-exporter       kube-state-metrics / Kubelet       /metrics     │
│      │                          │                         │           │
│      └──────────────────────────┴─────────────────────────┘           │
│                                 │                                   │
│                            Prometheus                               │
│                         storage + PromQL                            │
│                          /        |         \                        │
│                         /         |          \                       │
│                    Grafana   PrometheusRule   Anomaly Detector       │
│                                              │ range query          │
│                                              │ feature engineering │
│                                              │ Isolation Forest    │
│                                              └─ /metrics ─┐         │
│                                                          │         │
│                            Prometheus <───────────────────┘         │
│                                 │                                   │
│                            Alertmanager                             │
│                                 │                                   │
│                               Email                                 │
└─────────────────────────────────────────────────────────────────────┘

AWS EC2 node-exporter ───────────┐
AWS CloudWatch ── YACE ──────────┴──> Prometheus
```

K3s 控制平面与工作节点运行在 Ubuntu 主机上。项目使用以下命名空间：

| 命名空间 | 组件 |
|---|---|
| `kube-system` | CoreDNS、metrics-server、Traefik、local-path-provisioner |
| `monitoring` | Prometheus、Grafana、Alertmanager、Prometheus Operator、node-exporter、kube-state-metrics |
| `cloud-ops` | 应用服务、Anomaly Detector 和流量任务 |

## 指标体系

### Linux 主机

node-exporter 采集 CPU、内存、磁盘、网络和系统负载：

```promql
node_cpu_seconds_total
node_memory_MemAvailable_bytes
node_filesystem_avail_bytes
node_network_receive_bytes_total
```

### Kubernetes

kube-state-metrics 提供 Kubernetes 对象状态：

```promql
kube_pod_status_phase
kube_pod_container_status_restarts_total
kube_deployment_status_replicas_available
kube_node_status_condition
```

Kubelet 与 cAdvisor 提供容器资源指标：

```promql
container_cpu_usage_seconds_total
container_memory_working_set_bytes
```

### 应用服务

内置应用暴露请求量、响应时间和并发请求指标：

```promql
demo_http_requests_total
demo_http_request_duration_seconds
demo_http_requests_in_progress
```

Prometheus Operator 通过 ServiceMonitor 发现 `/metrics` 端点。

### 异常检测服务

```promql
ops_anomaly_score
ops_anomaly_model_ready
ops_anomaly_training_samples
ops_anomaly_last_training_timestamp_seconds
ops_anomaly_last_evaluation_timestamp_seconds
ops_anomaly_evaluation_failures_total
ops_anomaly_evaluation_duration_seconds
```

### AWS

AWS 指标链路覆盖 EC2 node-exporter 与 CloudWatch，并可扩展至 ALB、RDS 等服务。YACE 配置位于 `deploy/aws/yace-config.yaml`。

## 异常检测流程

```text
Prometheus range query
        ↓
时间对齐与缺失值处理
        ↓
滑动窗口特征工程
        ↓
RobustScaler
        ↓
Isolation Forest
        ↓
归一化异常分数
        ↓
Prometheus /metrics
        ↓
PrometheusRule + Alertmanager
```

模型分析以下应用指标：

- 请求速率
- 错误率
- P95 响应时间
- 当前并发请求数

每个原始指标生成当前值、滚动均值、滚动标准差、一阶差分以及当前值相对滚动均值的偏差。`hour_sin` 与 `hour_cos` 用于表达日周期位置。

模型配置：

| 参数 | 默认值 |
|---|---:|
| 历史窗口 | 24 小时 |
| 查询步长 | 60 秒 |
| 最少训练样本 | 60 |
| 重新训练间隔 | 6 小时 |
| 滑动窗口 | 5 |
| 模型存储 | 1 GiB PVC |

异常分数由 PrometheusRule 结合阈值与持续时间触发告警。固定规则与异常检测规则分别运行，形成覆盖确定性故障和动态模式偏移的告警体系。

## 告警策略

| 告警 | 条件 | 持续时间 | 等级 |
|---|---|---:|---|
| `CloudOpsTargetDown` | `cloud-ops` 采集目标不可达 | 3 分钟 | critical |
| `CloudOpsDemoHighErrorRate` | 应用错误率大于 5% | 5 分钟 | warning |
| `CloudOpsMultivariateAnomaly` | 模型就绪且异常分数大于 0.80 | 5 分钟 | warning |
| `CloudOpsAnomalyDetectorStale` | 超过 5 分钟无成功评估 | 2 分钟 | critical |

Alertmanager 按 `alertname`、`environment`、`service` 分组，首次等待 30 秒，同组更新间隔为 5 分钟。critical 告警会抑制相同环境和服务的 warning，并在状态恢复后发送 resolved 通知。

## 技术栈

| 分类 | 技术 |
|---|---|
| 容器编排 | K3s、Kubernetes、Helm |
| 指标采集 | Prometheus、node-exporter、kube-state-metrics、ServiceMonitor、YACE |
| 可视化 | Grafana |
| 告警 | PrometheusRule、Alertmanager、SMTP |
| 异常检测 | Python、pandas、NumPy、scikit-learn、Isolation Forest、RobustScaler |
| AWS | EC2、CloudWatch、IAM、SSM、Terraform |
| 工程化 | Docker、GitHub Actions、pytest、Makefile |

## 仓库结构

```text
anomaly-detector/          异常检测服务、特征工程、模型与测试
demo-app/                  应用服务与指标端点
deploy/alertmanager/       告警路由、分组与抑制配置
deploy/aws/                YACE 与 AWS 采集配置
deploy/grafana/            Grafana Dashboard
deploy/helm/               Helm Chart
deploy/monitoring/         kube-prometheus-stack values
deploy/scripts/            安装、部署、验证与流量脚本
terraform/aws/             AWS 基础设施
docs/                      架构、部署和场景文档
```

## 环境要求

推荐配置：

- Ubuntu Server 22.04 或 24.04
- 4 vCPU
- 8 GiB 内存
- 30 GiB 磁盘
- NAT 网络

依赖工具：Git、curl、Make、Docker、Helm、kubectl。AWS 资源由 Terraform 管理。

## 快速开始

### 1. 安装基础工具

```bash
sudo apt update
sudo apt install -y git curl make docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### 2. 克隆仓库

```bash
git clone https://github.com/jz-118/cloud-ops-anomaly-platform.git
cd cloud-ops-anomaly-platform
```

### 3. 部署平台

```bash
make install-k3s
make check
make install-monitoring
make deploy
make verify
```

| 命令 | 作用 |
|---|---|
| `make install-k3s` | 安装 K3s、配置 kubectl 并等待节点就绪 |
| `make check` | 检查 Git、curl、Docker、kubectl、Helm 和 Docker daemon |
| `make install-monitoring` | 安装 kube-prometheus-stack |
| `make deploy` | 构建镜像、导入 K3s containerd 并部署平台组件 |
| `make verify` | 等待 Deployment 就绪并执行健康检查 |

## 访问服务

分别启动端口转发：

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
```

| 服务 | 地址 |
|---|---|
| Grafana | `http://127.0.0.1:3000` |
| Prometheus | `http://127.0.0.1:9090` |
| Alertmanager | `http://127.0.0.1:9093` |

获取 Grafana 管理员密码：

```bash
kubectl get secret -n monitoring kube-prometheus-stack-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

用户名为 `admin`，预置仪表盘名称为 `Cloud Ops / Hybrid Environment Overview`。

## 邮件告警

复制环境变量文件并填写 SMTP 配置：

```bash
cp .env.example .env
nano .env
```

```dotenv
SMTP_SMARTHOST=smtp.qq.com:587
SMTP_FROM=your-account@qq.com
SMTP_TO=receiver@example.com
SMTP_USERNAME=your-account@qq.com
SMTP_PASSWORD=SMTP授权码
```

创建 Kubernetes Secret：

```bash
make secrets
```

`.env`、AWS 凭据和 Terraform state 由本地环境管理，并已纳入相应的 Git 忽略规则。

## 流量与告警场景

将异常检测参数调整为短周期配置：

```bash
helm upgrade cloud-ops deploy/helm/cloud-ops-platform \
  -n cloud-ops \
  --set anomalyDetector.minimumSamples=10 \
  --set anomalyDetector.lookbackHours=1 \
  --set anomalyDetector.evaluationIntervalSeconds=30 \
  --wait
```

### 建立基线流量

```bash
kubectl delete pod demo-baseline -n cloud-ops --ignore-not-found
kubectl run demo-baseline -n cloud-ops --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+1200)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null http://cloud-ops-demo-app:8080/work; sleep 0.5; done'
```

### 触发延迟异常

```bash
kubectl delete pod demo-latency -n cloud-ops --ignore-not-found
kubectl run demo-latency -n cloud-ops --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?latency_ms=1500"; sleep 1; done'
```

P95 延迟与异常分数达到规则条件后触发 `CloudOpsMultivariateAnomaly`。

### 触发错误率告警

```bash
kubectl delete pod demo-errors -n cloud-ops --ignore-not-found
kubectl run demo-errors -n cloud-ops --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?fail=true"; sleep 1; done'
```

错误率达到规则条件后触发 `CloudOpsDemoHighErrorRate`，Alertmanager 发送 firing 和 resolved 通知。

恢复 Helm 配置：

```bash
helm upgrade cloud-ops deploy/helm/cloud-ops-platform \
  -n cloud-ops --reset-values --wait
```

## AWS 接入

### 1. 创建资源

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
terraform init
terraform plan
terraform apply
```

将 `monitoring_cidr` 设置为 K3s 主机出口公网 IP 的 `/32`。Terraform 将创建加密 EC2、IMDSv2、SSM Instance Profile、安全组和 node-exporter。

### 2. 配置 Prometheus

返回仓库根目录，复制 AWS 监控配置并填入 Terraform 输出的 EC2 地址：

```bash
cd ../..
cp deploy/monitoring/values-aws.example.yaml deploy/monitoring/values-aws.yaml
nano deploy/monitoring/values-aws.yaml
```

升级监控栈：

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f deploy/monitoring/values.yaml \
  -f deploy/monitoring/values-aws.yaml \
  --wait --timeout 15m
```

### 3. 销毁资源

```bash
cd terraform/aws
terraform destroy
```

## 代理配置

虚拟机通过宿主机代理访问 GitHub、镜像仓库和软件源时，需要配置终端、Docker daemon 与 K3s containerd。以下配置使用 VMware VMnet8 地址 `192.168.146.1` 和 Clash Mixed Port `7897`。

Clash 开启 `Allow LAN`，并在 `0.0.0.0` 或 VMnet8 地址监听代理端口。

### 当前终端

```bash
export HTTP_PROXY=http://192.168.146.1:7897
export HTTPS_PROXY=http://192.168.146.1:7897
export http_proxy=$HTTP_PROXY
export https_proxy=$HTTPS_PROXY
export NO_PROXY=127.0.0.1,localhost,10.42.0.0/16,10.43.0.0/16,192.168.0.0/16,.svc,.cluster.local
export no_proxy=$NO_PROXY
```

### Docker daemon

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/proxy.conf >/dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=http://192.168.146.1:7897"
Environment="HTTPS_PROXY=http://192.168.146.1:7897"
Environment="NO_PROXY=127.0.0.1,localhost,10.42.0.0/16,10.43.0.0/16,192.168.0.0/16,.svc,.cluster.local"
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### K3s containerd

```bash
sudo mkdir -p /etc/systemd/system/k3s.service.d
sudo tee /etc/systemd/system/k3s.service.d/proxy.conf >/dev/null <<'EOF'
[Service]
Environment="CONTAINERD_HTTP_PROXY=http://192.168.146.1:7897"
Environment="CONTAINERD_HTTPS_PROXY=http://192.168.146.1:7897"
Environment="CONTAINERD_NO_PROXY=127.0.0.1,localhost,10.42.0.0/16,10.43.0.0/16,192.168.0.0/16,.svc,.cluster.local"
EOF
sudo systemctl daemon-reload
sudo systemctl restart k3s
```

## 开发与测试

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest anomaly-detector/tests demo-app/tests
```

GitHub Actions 执行以下检查：

- Python 单元测试
- Docker 镜像构建
- Helm lint 与 template
- Terraform fmt 与 validate

## 运维命令

查看 Pod 事件：

```bash
kubectl describe pod <Pod名称> -n <命名空间> | sed -n '/Events:/,$p'
```

查看服务日志：

```bash
kubectl logs deployment/cloud-ops-anomaly-detector -n cloud-ops --tail=100
kubectl logs deployment/cloud-ops-demo-app -n cloud-ops --tail=100
```

查看集群与监控资源：

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get servicemonitor,prometheusrule -n cloud-ops
```

查看异常检测指标：

```bash
kubectl port-forward -n cloud-ops svc/cloud-ops-anomaly-detector 8081:8080
curl http://127.0.0.1:8081/metrics
```

## 路线图

- 按服务和实例维护独立模型
- 增加周周期特征、漂移检测和模型版本管理
- 使用 S3 保存模型与评估报告
- 接入 ALB、RDS、Loki 和 Tempo
- 建立私有网络中的跨环境指标采集链路
- 基于历史告警结果评估规则与模型效果

## License

[MIT](LICENSE)
