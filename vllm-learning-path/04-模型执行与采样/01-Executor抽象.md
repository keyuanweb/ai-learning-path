# 01 · Executor 抽象

**源码**：[`code/vllm/vllm/v1/executor/abstract.py`](../../code/vllm/vllm/v1/executor/abstract.py)

## 职责

`Executor` 是执行器的抽象。它负责把 `SchedulerOutput` 分发到 GPU Workers 上执行。

## 抽象接口

| 方法 | 说明 |
|------|------|
| `execute_model(scheduler_output)` | 向所有 worker 发起前向计算，返回 `ModelRunnerOutput` |
| `sample_tokens(grammar_output)` | 从最新的 logits 采样 token |
| `collective_rpc(method, ...)` | 在所有 worker 上执行同一方法（用于初始化等） |
| `determine_available_memory()` | 通过哑加载 profile 可用 GPU 内存 |
| `initialize_from_config(kv_cache_configs)` | 分配 KV 缓存 + warmup 模型（CUDA graph 录制） |
| `get_kv_cache_specs()` | 获取各 worker 的 KV 缓存规格 |

## 工厂选择逻辑

```python
@staticmethod
def get_class(vllm_config):
    backend = vllm_config.parallel_config.distributed_executor_backend
    if backend == "uni":
        return UniProcExecutor      # 单进程
    elif backend == "mp":
        return MultiprocExecutor     # 多进程 + 共享内存
    elif backend == "ray":
        return RayDistributedExecutor  # Ray 集群
```

## 三个具体实现

| 实现 | 文件 | 场景 |
|------|------|------|
| `UniProcExecutor` | `uniproc_executor.py` | 单 GPU 离线推理，worker 在主进程内 |
| `MultiprocExecutor` | `multiproc_executor.py` | 多 GPU（TP>1），worker 在独立进程，共享内存传 tensor |
| `RayDistributedExecutor` | `ray_executor.py` | 跨节点的 Ray 集群部署 |

## 阅读重点

- 理解 Executor 是 Scheduler 和 Worker 之间的桥梁
- `execute_model()` 一次调用 = 一次 GPU 前向
- `initialize_from_config()` 做 KV 缓存分配 + CUDA graph 录制
- 第一遍不需要读各实现类的细节
