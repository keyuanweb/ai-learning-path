# 02 · Worker 抽象

**源码**：[`code/vllm/vllm/v1/worker/worker_base.py`](../../code/vllm/vllm/v1/worker/worker_base.py)

## 职责

`WorkerBase` 是单个设备（GPU/CPU/TPU）上的执行单元。它拥有模型实例，执行前向计算和采样。在 TP 模式下，每个 GPU 有一个 Worker 实例——它们并行执行同一个模型的各自部分。

## 抽象接口

| 方法 | 说明 |
|------|------|
| `init_device()` | 设置设备、初始化 CUDA context |
| `load_model()` | 加载模型权重到设备 |
| `execute_model(scheduler_output)` | 跑一次模型前向。可能返回 `ModelRunnerOutput`（尾 rank）或 None（中间 PP rank / 采样延迟） |
| `sample_tokens(grammar_output)` | 从最近一次前向的 logits 中采样（当 execute_model 没做采样时） |
| `get_kv_cache_spec()` | 返回此 worker 持有的 KV 缓存规格 |
| `compile_or_warm_up_model()` | CUDA graph 录制 + torch.compile 编译 |
| `shutdown()` | 清理 CUDA 资源 |

## `execute_model` 和 `sample_tokens` 的关系

两者可能合并，也可能分开：

- **合并**（默认）：`execute_model()` 中的 CUDA graph 包含了采样 step → `ModelRunnerOutput.sampled_token_ids` 已填充
- **分开**（某些后端）：
  1. `execute_model()` 只做前向计算，返回 `ModelRunnerOutput`（含 logits 不含采样结果）
  2. 调度器调用 `get_grammar_bitmask()` 获得合法 token 集合
  3. `sample_tokens(grammar_output)` 在 logits 上应用 bitmask + 采样

分离的目的是让结构化输出的 grammar bitmask 可以在采样前注入。

## WorkerWrapperBase — 多进程的懒初始化 wrapper

在多进程模式下（`MultiprocExecutor`），子进程启动时先创建一个空的 `WorkerWrapperBase`，不加载模型。当 `Executor` 调用 `init_worker()` / `initialize_from_config()` 时，wrapper 才真正：

1. 调用 `worker_class(vllm_config)` 创建实际的 Worker 实例
2. 调用 `worker.init_device()` 设置 CUDA
3. 调用 `worker.load_model()` 加载模型权重

这样做的好处：
- 模型加载只在子进程中触发（避免主进程 import torch/CUDA 的副作用）
- 错误处理清晰：worker 初始化失败可以单独报告
- 支持进程 fork 后重新初始化 CUDA context

## Worker 类型

| Worker 类 | 文件 | 设备 |
|-----------|------|------|
| `Worker` | `v1/worker/gpu_worker.py` | NVIDIA GPU |
| `CPUWorker` | `v1/worker/cpu_worker.py` | CPU |
| `XPUWorker` | `v1/worker/xpu_worker.py` | Intel GPU |

Worker 是默认也是最常用的。CPU/XPU Worker 第一遍忽略。

## 阅读重点

- 理解 `execute_model` 和 `sample_tokens` 的「合并 vs 分开」两种模式
- 知道 `WorkerWrapperBase` 的懒初始化模式：先创建 wrapper，后加载模型
- 第一遍只看 Worker 的接口，不看 CPU/XPU
