# Actor 故障恢复

## 提出问题

Task 是无状态的，挂了重跑就行。但 Actor 有状态——模型权重、计数器值、训练优化器状态——Actor 进程挂了怎么办？状态会丢吗？能不能自动恢复？

## 核心原理

Actor 的容错比 Task 复杂得多，因为**状态需要恢复**。Ray 提供了多层级的 Actor 容错选项：

> **类比**：Task 挂了像是外包临时工不干了——重新找个人再跑一遍。Actor 挂了像是你的核心员工离职了——你需要决定：是不是再招一个重新培训（重启）？还是整个项目就算了（不重启）？

## 基础：Actor 故障检测

### 心跳机制

Ray 通过心跳检测 Actor 存活：

```mermaid
graph LR
    A["Actor"] -->|"心跳"| GCS["GCS"]
    GCS -->|"N 秒没心跳"| D["标记 Actor 为 DEAD"]
    D --> N["通知所有持有该 Actor Handle 的 Worker"]

    style D fill:#f8d7da
    style N fill:#fff3cd
```

### 故障表现

```python
@ray.remote
class Worker:
    def __init__(self):
        self.state = {}

    def work(self):
        import os
        os._exit(1)  # 模拟崩溃

w = Worker.remote()
try:
    ray.get(w.work.remote())
except ray.exceptions.RayActorError as e:
    print(f"Actor 崩溃了: {e}")
```

## 容错选项

### max_restarts（最大重启次数）

```python
# 最多重启 3 次
@ray.remote(max_restarts=3)
class RobustWorker:
    def __init__(self):
        self.counter = 0

    def increment(self):
        self.counter += 1
        return self.counter

worker = RobustWorker.remote()
# 如果 Worker 崩溃，Ray 自动重启最多 3 次
# 注意：重启后 counter 重置为 0！状态丢失
```

### max_task_retries（Task 级重试）

```python
# Task 失败时重试（不需要整个 Actor 重启）
@ray.remote(max_task_retries=3)
class RetryableWorker:
    def unreliable_work(self):
        if random.random() < 0.5:
            raise RuntimeError("偶发错误")
        return "成功"

w = RetryableWorker.remote()
try:
    result = ray.get(w.unreliable_work.remote())
    # 如果方法抛异常，Ray 自动重试最多 3 次
except ray.exceptions.RayTaskError:
    print("3 次重试后仍然失败")
```

### 组合使用

```python
@ray.remote(max_restarts=5, max_task_retries=3)
class ProductionWorker:
    def __init__(self):
        self.load_state_from_checkpoint()  # 从外部存储恢复

    def load_state_from_checkpoint(self):
        # 尝试从 S3/Redis/本地文件恢复状态
        try:
            self.state = load_checkpoint()
        except FileNotFoundError:
            self.state = {}

    def save_checkpoint(self):
        save_to_storage(self.state)

    def process(self, item):
        result = compute(self.state, item)
        self.state = update(self.state, result)
        self.save_checkpoint()  # 定期快照
        return result
```

## Actor 状态恢复策略

### 策略 1：无状态恢复（重新初始化）

```python
@ray.remote(max_restarts=3)
class StatelessWorker:
    def __init__(self, config):
        self.config = config  # 配置可以从参数恢复
        self.cache = {}       # 缓存无所谓，丢了就丢了

    def serve(self, request):
        if request.id not in self.cache:
            self.cache[request.id] = compute(request)
        return self.cache[request.id]
```

> 适合：缓存、纯计算的 Actor

### 策略 2：外部存储恢复

```python
import pickle
import redis

@ray.remote(max_restarts=5)
class ReliableActor:
    def __init__(self, redis_url):
        self.redis = redis.from_url(redis_url)
        # 尝试恢复状态
        saved = self.redis.get("actor_state")
        self.state = pickle.loads(saved) if saved else {}

    def update(self, key, value):
        self.state[key] = value
        # 每次更新都持久化
        self.redis.set("actor_state", pickle.dumps(self.state))

    def get(self, key):
        return self.state.get(key)
```

> 适合：需要可靠性的有状态 Actor

### 策略 3：从血统重建（仅确定性 Actor）

```python
@ray.remote(max_restarts=3)
class DeterministicActor:
    def __init__(self):
        self.events = []  # 确定性事件日志

    def apply(self, event):
        self.events.append(event)
        return compute_state(self.events)  # 确定性计算
    # 如果挂了 → 重启 → 重放 events（如果 events 也被持久化）
```

> 适合：确定性计算，可以重放

## 各容错层级对比

| 层级 | 机制 | 恢复内容 | 适用场景 |
|------|------|----------|----------|
| Task 重试 | `max_retries=N` | 重新执行函数 | 无状态计算 |
| Actor 重启 | `max_restarts=N` | 重新 `__init__` | 有状态但可重建 |
| 方法重试 | `max_task_retries=N` | 重新执行方法 | 偶发错误 |
| 血统重建 | Lineage | 重新计算丢失对象 | 对象级容错 |
| 外部 Checkpoint | 手动持久化 | 完整状态恢复 | 关键状态 |

## 故障传播

### Actor 树

```python
@ray.remote
class Parent:
    def __init__(self):
        self.child = Child.remote()  # Parent 创建 Child

    def work(self):
        return self.child.do.remote()

@ray.remote
class Child:
    def do(self):
        return "done"

parent = Parent.remote()
# Parent 持有 Child 的 Handle
# 如果 Child 崩溃，Parent 调用 remote() 时会收到 RayActorError
```

Actor 的创建者（Parent）需要处理子 Actor 的故障：

```python
@ray.remote(max_restarts=3)
class RobustParent:
    def __init__(self):
        self.create_child()

    def create_child(self):
        self.child = Child.remote()

    def work(self):
        try:
            return ray.get(self.child.do.remote(), timeout=5)
        except ray.exceptions.RayActorError:
            self.create_child()  # 子 Actor 挂了，重建
            return self.work()   # 重试
```

## 常见陷阱

### 1. 假设 Actor 永远不死

```python
# ❌ Actor 可能在任何时候崩溃
result = ray.get(actor.do_something.remote())
# 如果没 try-catch，调用方的程序也会崩溃
```

### 2. 状态恢复不完整

```python
# ❌ __init__ 恢复状态，但 __init__ 参数不完整
@ray.remote(max_restarts=3)
class BadRecovery:
    def __init__(self, model_path):
        self.model = load(model_path)  # 模型恢复了
        self.optimizer = Adam(self.model.parameters())  # ❌ 优化器状态丢失！
```

### 3. 重启循环

```python
# ❌ __init__ 中的 bug 导致反复重启
@ray.remote(max_restarts=5)
class CrashLoop:
    def __init__(self):
        connect_to_broken_service()  # 每次都失败
        # → 无限重启 → 耗尽 max_restarts

# ✅ 在 __init__ 中加 try-catch
@ray.remote(max_restarts=5)
class SafeInit:
    def __init__(self):
        try:
            self.conn = connect_with_timeout(5)
        except Exception:
            self.conn = None  # 降级
```

## 小结

- Actor 故障检测基于心跳，崩溃后抛出 `RayActorError`
- `max_restarts`：控制 Actor 进程重启次数，重启后状态不保留
- `max_task_retries`：控制单个方法调用重试次数
- 关键状态需要**手动持久化到外部存储**（Redis/S3/数据库）
- 创建者需要处理子 Actor 的故障（Actor 树模式）
- 防止无限重启循环：确保 `__init__` 在异常场景下也能安全完成
