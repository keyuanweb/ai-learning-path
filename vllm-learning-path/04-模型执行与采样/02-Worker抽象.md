# 02 · Worker 抽象

**源码**：[`code/vllm/vllm/v1/worker/worker_base.py`](../../code/vllm/vllm/v1/worker/worker_base.py)

## 职责

`WorkerBase` 是单个设备（GPU/CPU/TPU）上的执行单元。它拥有模型实例，执行前向计算和采样。

## 抽象接口

| 方法 | 说明 |
|------|------|
| `init_device()` | 在设备上加载模型 |
| `execute_model(scheduler_output)` | 跑一次模型前向。可能返回 None（采样推迟到后续） |
| `sample_tokens(grammar_output)` | 从最近的 logits 采样 |
| `get_kv_cache_spec()` | 返回 KV 缓存规格（供引擎计算块数） |
| `compile_or_warm_up_model()` | CUDA graph 录制 / torch.compile |
| `determine_available_memory()` | 通过哑加载 profile 可用内存 |
| `shutdown()` | 清理资源 |

## WorkerWrapperBase — 多进程的懒初始化 wrapper

在多进程模式下（`MultiprocExecutor`），先在子进程里创建一个空的 `WorkerWrapperBase`。当 `Executor` 调用 `init_worker()` 时，wrapper 才真正加载模型。这样做是为了：
- 模型加载只在子进程中触发（避免主进程 import torch/CUDA）
- 错误处理更清晰（worker 初始化失败可以单独处理）

## 阅读重点

- 理解 `execute_model` 和 `sample_tokens` 的关系（前者可能不做采样，留给后者）
- 知道 `WorkerWrapperBase` 是懒初始化模式
- 其他 Worker 实现（CPU/TPU）第一遍跳过
