# Kubernetes 学习路径

Kubernetes（K8s）是云原生应用的事实标准编排平台。本路径从架构原理到生产运维，系统掌握 Pod、工作负载、网络、存储、安全、Helm/GitOps 等核心能力，末阶段衔接本仓库 AI 路径中的推理服务与 KubeRay 部署。

| 阶段 | 内容 | 预计学时 |
|------|------|----------|
| 00-入口 | 学习路线总览、环境搭建（kind/kubectl） | 2h |
| 01-架构与核心概念 | K8s 架构总览、Pod 与容器运行时 | 5h |
| 02-工作负载 | Deployment、StatefulSet、DaemonSet、Job/CronJob | 6h |
| 03-服务与网络 | Service、Ingress、NetworkPolicy 与 CNI | 6h |
| 04-存储与配置 | ConfigMap/Secret、PV/PVC、卷挂载实战 | 5h |
| 05-调度与弹性 | 调度器与亲和性、ResourceQuota、HPA/VPA | 6h |
| 06-安全与治理 | RBAC、SecurityContext、多租户隔离 | 5h |
| 07-运维与可观测 | kubectl 调试、日志事件、Prometheus/Grafana | 5h |
| 08-生态与交付 | Helm、Operator/CRD、GitOps/ArgoCD | 6h |
| 09-AI 工作负载实战 | 推理服务部署、vLLM 与 KubeRay 案例 | 4h |

**总计约 50 学时**

## 学习建议

1. **必学基础**（00-04）：Pod、Deployment、Service、ConfigMap/Secret 是日常 80% 的操作
2. **生产必备**（05-07）：调度、安全、排障是 CKA/CKAD 考试和生产运维的核心
3. **平台进阶**（08）：Helm 和 GitOps 是团队交付的标准工具链
4. **AI 衔接**（09）：完成通用 K8s 后，可继续 [Ray KubeRay 章节](../ray-learning-path/08-集群与生产/02-KubeRay与云原生部署.md) 与 [vLLM 学习路径](../vllm-learning-path/)
