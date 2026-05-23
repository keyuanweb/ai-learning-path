# ConfigMap 与 Secret

## 核心原理

ConfigMap 存储**非敏感配置**（配置文件、环境变量）；Secret 存储**敏感数据**（密码、证书、Token），Base64 编码存储（非加密，需配合 RBAC 和 etcd 加密）。

> **类比**：ConfigMap 是「公开张贴的配置表」；Secret 是「上锁抽屉里的钥匙」——仍要防内鬼（RBAC）。

## ConfigMap 示例

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: k8s-learn
data:
  APP_ENV: production
  log_level: info
  nginx.conf: |
    server {
      listen 80;
      location / { return 200 'Hello'; }
    }
```

### 注入方式

**环境变量：**

```yaml
spec:
  containers:
  - name: app
    image: nginx:1.25
    env:
    - name: APP_ENV
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: APP_ENV
```

**Volume 挂载：**

```yaml
spec:
  volumes:
  - name: config-vol
    configMap:
      name: app-config
  containers:
  - name: app
    image: nginx:1.25
    volumeMounts:
    - name: config-vol
      mountPath: /etc/nginx/conf.d
```

```bash
kubectl apply -f configmap.yaml
kubectl apply -f pod-with-config.yaml
kubectl exec pod-name -n k8s-learn -- cat /etc/nginx/conf.d/nginx.conf
```

## Secret 示例

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
  namespace: k8s-learn
type: Opaque
stringData:
  username: admin
  password: s3cr3t
```

```yaml
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: db-secret
      key: password
```

```bash
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=s3cr3t \
  -n k8s-learn
```

## 对比

| | ConfigMap | Secret |
|---|-----------|--------|
| 用途 | 普通配置 | 敏感数据 |
| 大小限制 | 1 MiB | 1 MiB |
| 存储 | 明文 | Base64（需 RBAC + etcd 加密） |
| 类型 | 默认 | Opaque、kubernetes.io/tls、docker-registry 等 |

## 配置热更新

Volume 挂载 ConfigMap 时，kubelet 会**同步更新**文件（有延迟，约 1 分钟）。应用需支持 reload（如 nginx `-s reload`）或使用 **Reloader** 等工具自动重启  

## 动手练习

1. 创建 ConfigMap，用 env 和 volume 两种方式注入 Pod  
2. 创建 Secret，验证 `kubectl get secret db-secret -o yaml` 中 data 为 Base64  
3. 修改 ConfigMap，观察挂载文件是否更新  

## 常见坑

- **Secret 不是加密**：Base64 ≠ 加密，生产必须启用 etcd 加密 + 严格 RBAC  
- **subPath 不热更新**：`subPath` 挂载的 ConfigMap **不会**自动更新  
- **大小限制**：单个 ConfigMap/Secret 最大 1 MiB  

## 小结  

- ConfigMap / Secret 解耦配置与镜像  
- 注入方式：env、volumeMount、envFrom  
- Secret 需 RBAC 保护，生产启用 etcd encryption at rest  
