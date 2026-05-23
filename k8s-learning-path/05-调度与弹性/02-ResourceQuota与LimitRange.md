# ResourceQuota 与 LimitRange

## 核心原理

**requests/limits** 控制单 Pod 资源；**ResourceQuota** 限制 Namespace 总量；**LimitRange** 为 Namespace 设默认值和上下限。

> **类比**：LimitRange 是「单人餐标」；ResourceQuota 是「部门月度预算」。

## Pod 资源声明

```yaml
resources:
  requests:
    cpu: 100m      # 0.1 核，调度依据
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

| 概念 | 说明 |
|------|------|
| requests | 调度保证的最小资源 |
| limits | 容器可用上限，超 CPU 节流，超内存 OOM |
| cpu 单位 | 1 = 1 核，100m = 0.1 核 |
| memory | Mi、Gi 等二进制单位 |

## ResourceQuota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: k8s-learn
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
```

```bash
kubectl apply -f quota.yaml
kubectl describe resourcequota compute-quota -n k8s-learn
```

超出配额时 Pod 创建被拒绝。

## LimitRange

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: k8s-learn
spec:
  limits:
  - default:
      cpu: 200m
      memory: 256Mi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    max:
      cpu: "2"
      memory: 2Gi
    min:
      cpu: 50m
      memory: 64Mi
    type: Container
```

未设 resources 的 Pod 自动应用 default/defaultRequest。

## 动手练习

1. 创建 ResourceQuota，尝试超额创建 Pod 观察失败
2. 创建 LimitRange，部署无 resources 的 Pod，验证自动注入
3. 用 `kubectl top pods` 查看实际用量（需 metrics-server）

## 常见坑

- **只设 limits 不设 requests**：requests 默认等于 limits，可能过度占用调度资源
- **Quota 与 LimitRange 配合**：Quota 统计 requests/limits 总和
- **BestEffort Pod**：无 requests/limits 的 Pod 在资源紧张时最先被驱逐

## 小结

- requests 影响调度，limits 影响运行时上限
- ResourceQuota 限制 namespace 总量
- LimitRange 提供默认值和边界，防止资源滥用
