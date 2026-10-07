# 基于 K3s、Prometheus 与无监督学习的混合云监控告警平台

这是一个运行在单节点 K3s 集群中的小型混合云可观测性平台。它统一采集 Linux 主机、Kubernetes 资源和应用时序指标，通过 Grafana 展示，通过 PrometheusRule 与 Alertmanager 完成告警、聚合、抑制和邮件通知，并使用 Isolation Forest 对多维时序特征进行无监督异常检测。

项目还提供 AWS EC2、CloudWatch 和 Terraform 接入能力。默认部署只包含本地 K3s 环境，AWS 部分需要按本文后续步骤单独启用。

> 项目当前定位为可复现的实验环境与技术原型，不是生产级大规模监控平台，也不包含自动修复闭环。

## 一、项目解决的问题

传统固定阈值告警有三个常见问题：

- 正常的周期性高峰可能反复触发告警，产生误报和告警风暴。
- CPU、延迟、流量和错误率之间存在关联，单个指标没有越过阈值时仍可能存在风险。
- Linux、Kubernetes 和 AWS 指标分散，缺少统一的数据模型、仪表盘和告警出口。

本项目采用混合告警策略：

- 宕机、错误率、磁盘容量等确定性故障继续使用 Prometheus 固定规则。
- 周期性、波动型和多指标关联异常使用 Isolation Forest。
- Alertmanager 负责告警分组、去重、抑制、重复通知间隔和恢复通知。
- 机器学习只输出异常证据，不直接执行重启、扩容等高风险操作。

## 二、总体架构

```text
┌──────────────────── Ubuntu 虚拟机 / 单节点 K3s ────────────────────┐
│                                                                    │
│  Linux 主机                    K3s                  Demo API         │
│      │                          │                       │             │
│ node-exporter      kube-state-metrics / Kubelet       /metrics      │
│      │                          │                       │             │
│      └──────────────────────────┴───────────────────────┘             │
│                                 │                                  │
│                            Prometheus                              │
│                         存储与 PromQL 查询                          │
│                          /        |        \                        │
│                         /         |         \                       │
│                    Grafana   PrometheusRule   Anomaly Detector      │
│                                              │ query_range         │
│                                              │ 特征工程             │
│                                              │ Isolation Forest    │
│                                              └─ /metrics ─┐        │
│                                                          │        │
│                            Prometheus <───────────────────┘        │
│                                 │                                  │
│                            Alertmanager                            │
│                                 │                                  │
│                                邮件                                │
└────────────────────────────────────────────────────────────────────┘

可选 AWS 环境：

EC2 node-exporter ────────────────┐
CloudWatch ── YACE ───────────────┴──> Prometheus
```

## 三、当前实际运行形态

默认采用单节点 K3s：控制平面和工作节点位于同一台 Ubuntu 虚拟机。

```text
Ubuntu 虚拟机
├── K3s 控制平面
│   ├── API Server
│   ├── Scheduler
│   ├── Controller Manager
│   └── 集群数据存储
└── K3s 工作节点
    ├── Kubelet
    ├── containerd
    └── 所有 Pod
```

K3s 将多个控制平面组件整合到 `k3s server` 进程中，因此它们不一定以独立 Pod 出现。

| 命名空间 | 内容 |
|---|---|
| `kube-system` | CoreDNS、metrics-server、Traefik、local-path-provisioner 等 K3s 组件 |
| `monitoring` | Prometheus、Grafana、Alertmanager、Prometheus Operator、node-exporter、kube-state-metrics |
| `cloud-ops` | Demo API、Anomaly Detector，以及演示时创建的临时流量 Pod |

## 四、数据源与指标

### Linux 主机指标

node-exporter 采集 Ubuntu 虚拟机的 CPU、内存、磁盘、网络和系统负载。

```promql
node_cpu_seconds_total
node_memory_MemAvailable_bytes
node_filesystem_avail_bytes
node_network_receive_bytes_total
```

### Kubernetes 状态与容器指标

kube-state-metrics 将 Kubernetes API 中的对象状态转换为指标：

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

### Demo API 业务指标

Demo API 是项目自带的被监控应用，支持正常请求、延迟注入和错误注入。

```promql
demo_http_requests_total
demo_http_request_duration_seconds
demo_http_requests_in_progress
```

Prometheus Operator 通过 ServiceMonitor 自动发现 `/metrics` 端点。

### 异常检测服务自身指标

```promql
ops_anomaly_score
ops_anomaly_model_ready
ops_anomaly_training_samples
ops_anomaly_last_training_timestamp_seconds
ops_anomaly_last_evaluation_timestamp_seconds
ops_anomaly_evaluation_failures_total
ops_anomaly_evaluation_duration_seconds
```

### AWS 指标

AWS 默认未启用。启用后可以接入 EC2 node-exporter、CloudWatch EC2 CPU 和网络指标，并扩展 ALB、RDS 等服务。YACE 示例位于 `deploy/aws/yace-config.yaml`。

## 五、无监督异常检测设计

```text
Prometheus range query
        ↓
时间对齐、无穷值和缺失值处理
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

模型默认分析 Demo API 的请求速率、错误率、P95 响应时间和当前并发请求数。

每个原始指标会生成：

- 当前值
- 滚动均值
- 滚动标准差
- 一阶差分
- 当前值与滚动均值的偏差

另外加入 `hour_sin` 与 `hour_cos` 表示一天中的周期位置，避免 23 点和 0 点在数值上被视为相距很远。

默认模型生命周期：

- 查询最近 24 小时历史数据，步长 60 秒。
- 至少需要 60 个训练样本和 1 个推理样本。
- 每 6 小时重新训练。
- 模型保存到 1 GiB PersistentVolumeClaim。
- 冷启动没有数据时不训练，模型就绪指标保持为 `0`。
- 异常检测不可用时，传统告警仍然工作。

模型识别的是“偏离历史模式”，不是已经确认的根因。新服务需要基线，发布和业务增长可能造成数据漂移，异常分数仍需要阈值与持续时间策略。

## 六、告警设计

| 告警 | 条件 | 持续时间 | 等级 |
|---|---|---:|---|
| `CloudOpsTargetDown` | `cloud-ops` 采集目标不可达 | 3 分钟 | critical |
| `CloudOpsDemoHighErrorRate` | Demo API 错误率大于 5% | 5 分钟 | warning |
| `CloudOpsMultivariateAnomaly` | 模型就绪且异常分数大于 0.80 | 5 分钟 | warning |
| `CloudOpsAnomalyDetectorStale` | 超过 5 分钟无成功评估 | 2 分钟 | critical |

Alertmanager 按 `alertname`、`environment`、`service` 分组，首次等待 30 秒，同组更新间隔 5 分钟。critical 告警会抑制同一环境和服务的 warning，并在恢复时发送 resolved 通知。

## 七、技术栈

| 分类 | 技术 |
|---|---|
| 容器编排 | K3s、Kubernetes、Helm |
| 指标 | Prometheus、node-exporter、kube-state-metrics、ServiceMonitor |
| 可视化 | Grafana |
| 告警 | PrometheusRule、Alertmanager、SMTP |
| 异常检测 | Python、pandas、NumPy、scikit-learn、Isolation Forest、RobustScaler |
| AWS | EC2、CloudWatch、IAM、SSM、Terraform、YACE |
| 工程化 | Docker、GitHub Actions、pytest、Makefile |

## 八、仓库结构

```text
anomaly-detector/          异常检测服务、特征工程、模型与测试
demo-app/                  可注入延迟和错误的测试应用
deploy/alertmanager/       邮件路由、分组与抑制
deploy/aws/                YACE 和 AWS 目标示例
deploy/grafana/            Grafana Dashboard
deploy/helm/               项目 Helm Chart
deploy/monitoring/         kube-prometheus-stack values
deploy/scripts/            安装、部署、验证与演示脚本
terraform/aws/             AWS EC2 实验环境
docs/                      补充文档
```

## 九、运行环境

推荐 Ubuntu Server 22.04 或 24.04，4 vCPU、8 GiB 内存、30 GiB 以上磁盘，使用 NAT 网络。

依赖：Git、curl、Make、Docker、Helm、kubectl；Terraform 仅在 AWS 部分需要。

## 十、安装与部署

### 安装基础工具

```bash
sudo apt update
sudo apt install -y git curl make docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### 克隆项目

```bash
git clone https://github.com/jz-118/cloud-ops-anomaly-platform.git
cd cloud-ops-anomaly-platform
```

### 依次部署

```bash
make install-k3s
make check
make install-monitoring
make deploy
make verify
```

- `make install-k3s`：安装单节点 K3s，配置 kubectl 并等待节点 Ready。
- `make check`：检查 Git、curl、Docker、kubectl、Helm 和 Docker daemon。
- `make install-monitoring`：安装 kube-prometheus-stack。
- `make deploy`：构建两个本地镜像，导入 K3s containerd，再部署业务组件。
- `make verify`：等待 Deployment 可用并执行健康检查。

项目镜像由 Docker 本地构建，再通过 `k3s ctr images import` 导入 K3s，不需要将项目镜像上传到公共仓库。

## 十一、代理环境配置

如果虚拟机不能直连 GitHub 或 Docker Hub，需要同时配置当前终端、Docker daemon 和 K3s containerd。以下示例假设 Windows VMware VMnet8 地址为 `192.168.146.1`，Clash Mixed Port 为 `7897`。

Clash 必须开启 `Allow LAN`，代理端口应监听在 `0.0.0.0` 或 VMnet8 地址，而不是只监听 `127.0.0.1`。

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

## 十二、访问页面

三个终端分别执行：

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
```

```text
Grafana       http://127.0.0.1:3000
Prometheus    http://127.0.0.1:9090
Alertmanager  http://127.0.0.1:9093
```

获取 Grafana 密码：

```bash
kubectl get secret -n monitoring kube-prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

用户名是 `admin`，仪表盘名称是 `Cloud Ops / Hybrid Environment Overview`。

## 十三、邮件告警

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

```bash
make secrets
```

`.env` 已加入 `.gitignore`。不要提交邮箱凭据、AWS Access Key 或 Terraform state。

## 十四、快速演示

默认模型约需一小时数据。演示前可临时切换快速配置：

```bash
helm upgrade cloud-ops deploy/helm/cloud-ops-platform \
  -n cloud-ops \
  --set anomalyDetector.minimumSamples=10 \
  --set anomalyDetector.lookbackHours=1 \
  --set anomalyDetector.evaluationIntervalSeconds=30 \
  --wait
```

### 正常基线

```bash
kubectl delete pod demo-baseline -n cloud-ops --ignore-not-found
kubectl run demo-baseline -n cloud-ops --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+1200)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null http://cloud-ops-demo-app:8080/work; sleep 0.5; done'
```

### 机器学习异常

只增加延迟，不产生 HTTP 500：

```bash
kubectl delete pod demo-latency -n cloud-ops --ignore-not-found
kubectl run demo-latency -n cloud-ops --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?latency_ms=1500"; sleep 1; done'
```

预期展示：P95 延迟升高、错误率保持低位、异常分数上升，持续满足条件后触发 `CloudOpsMultivariateAnomaly`。

### 固定规则告警

```bash
kubectl delete pod demo-errors -n cloud-ops --ignore-not-found
kubectl run demo-errors -n cloud-ops --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?fail=true"; sleep 1; done'
```

预期触发 `CloudOpsDemoHighErrorRate`，Alertmanager 发送 firing 和 resolved 通知。

恢复默认参数：

```bash
helm upgrade cloud-ops deploy/helm/cloud-ops-platform -n cloud-ops --reset-values --wait
```

## 十五、AWS 接入

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
terraform init
terraform plan
terraform apply
```

`monitoring_cidr` 必须设置为 K3s 主机出口公网 IP 的 `/32`，模块禁止使用 `0.0.0.0/0`。

Terraform 创建加密 EC2、强制 IMDSv2、SSM Instance Profile、受限安全组，并自动安装 node-exporter，不开放 SSH 端口。

将 Terraform 输出的 EC2 地址写入从 `deploy/monitoring/values-aws.example.yaml` 复制出的 `values-aws.yaml`，然后升级监控栈：

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f deploy/monitoring/values.yaml \
  -f deploy/monitoring/values-aws.yaml \
  --wait --timeout 15m
```

演示结束后释放资源：

```bash
cd terraform/aws
terraform destroy
```

## 十六、开发与持续集成

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest anomaly-detector/tests demo-app/tests
```

GitHub Actions 自动执行 Python 单元测试、两个 Docker 镜像构建、Helm lint/template 和 Terraform fmt/validate。

## 十七、常用排障

查看 Pod 事件：

```bash
kubectl describe pod <Pod名称> -n <命名空间> | sed -n '/Events:/,$p'
```

`ErrImagePull`、`ImagePullBackOff` 或 `FailedCreatePodSandBox` 通常需要检查 K3s containerd 代理，而不只是 Docker 代理。

查看日志：

```bash
kubectl logs deployment/cloud-ops-anomaly-detector -n cloud-ops --tail=100
kubectl logs deployment/cloud-ops-demo-app -n cloud-ops --tail=100
```

查看集群：

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get servicemonitor,prometheusrule -n cloud-ops
```

异常检测冷启动时应先生成连续基线，等待滚动窗口和最少样本数量满足要求。空 Prometheus 历史不会导致服务崩溃。

## 十八、后续扩展

- 按服务或实例分别训练模型。
- 增加周周期特征、漂移检测和模型版本管理。
- 使用 S3 保存模型和评估报告。
- 接入 ALB、RDS、Loki 和 Tempo。
- 使用 VPN 或私有网络替代公网抓取 EC2 exporter。
- 记录历史告警结果，对比固定规则和异常检测的误报率、漏报率。

## 十九、安全与成本

- Grafana、Prometheus、Alertmanager 默认通过 port-forward 访问。
- EC2 node-exporter 安全组仅允许指定 `/32` 地址。
- SMTP 和 AWS 凭据不提交到 Git。
- 容器以非 root 用户运行。
- 模型输出只用于辅助判断，不自动执行生产变更。
- AWS 演示结束后及时执行 `terraform destroy`。

## License

MIT
