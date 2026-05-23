# Job 与 CronJob

## 核心原理

Job 运行**一次性任务**，Pod 成功完成指定次数后 Job 结束。CronJob 按 cron 表达式**定时**创建 Job。

> **类比**：Job 是「临时工单次任务」；CronJob 是「 cron 定时闹钟」到点派一批临时工。

## Job 示例

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: pi-calc
  namespace: k8s-learn
spec:
  completions: 3
  parallelism: 2
  backoffLimit: 4
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: pi
        image: perl:5.34
        command: ["perl", "-Mbignum=b", "-wle", "print bpi(2000)"]
```

| 字段 | 含义 |
|------|------|
| completions | 成功完成的 Pod 总数 |
| parallelism | 同时运行的 Pod 数 |
| backoffLimit | 失败重试次数 |
| restartPolicy | Job Pod 必须为 Never 或 OnFailure |

```bash
kubectl apply -f job.yaml
kubectl get jobs -n k8s-learn
kubectl logs job/pi-calc -n k8s-learn
```

## CronJob 示例

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: hello-cron
  namespace: k8s-learn
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: hello
            image: busybox:1.36
            command: ["sh", "-c", "date; echo Hello from CronJob"]
```

```bash
kubectl apply -f cronjob.yaml
kubectl get cronjobs -n k8s-learn
kubectl get jobs -n k8s-learn
```

## concurrencyPolicy

| 值 | 行为 |
|----|------|
| Allow | 允许并发（默认） |
| Forbid | 上次未完成则跳过 |
| Replace | 取消上次，启动新的 |

## 动手练习

1. 创建 Job，`completions=5, parallelism=2`，观察并行执行
2. 创建 CronJob 每分钟执行，用 `kubectl get jobs -w` 观察
3. 手动触发：`kubectl create job --from=cronjob/hello-cron manual-1 -n k8s-learn`

## 常见坑

- **Job Pod restartPolicy**：不能是 Always
- **CronJob 时区**：默认控制器时区（通常 UTC），K8s 1.27+ 支持 `timeZone` 字段
- **Completed Job 清理**：设置 `ttlSecondsAfterFinished` 自动清理

## 小结

- Job 适合批处理、迁移、一次性计算
- CronJob 适合定时备份、报表、清理任务
- 注意 concurrencyPolicy 和 history limit 控制资源
