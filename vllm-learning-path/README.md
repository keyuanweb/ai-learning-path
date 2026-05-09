# vLLM 源码学习路径

> 基于对 `code/vllm/vllm/` (v0.20.0) 的通读生成，按学习阶段分目录组织。
> 源码位置：`code/vllm/`（与本学习路径同级）

## 整体架构（读代码前先看这张图）

```
用户调用 LLM.generate(["你好"])
        │
        ▼
┌─ entrypoints/llm.py ─────────────────────────────────────┐
│  LLM 类：用户入口。把 prompt 转成 token ids，调引擎        │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌─ v1/engine/llm_engine.py ────────────────────────────────┐
│  LLMEngine（前端）：管请求生命周期                          │
│  内部持有：InputProcessor / OutputProcessor / EngineCoreClient │
└──────────────────────────┬───────────────────────────────┘
                           │  (InprocClient/ZMQ)
                           ▼
┌─ v1/engine/core.py ──────────────────────────────────────┐
│  EngineCore（后端）：推理紧循环                             │
│  step() 做四件事：                                        │
│    1. Scheduler.schedule()   → SchedulerOutput            │
│    2. Executor.execute_model() → ModelRunnerOutput        │
│    3. Scheduler.get_grammar_bitmask() → 结构化输出约束     │
│    4. Scheduler.update_from_output() → EngineCoreOutputs   │
└──────┬──────────────────────────────┬────────────────────┘
       │                              │
       ▼                              ▼
┌─ v1/core/sched/ ─────┐    ┌─ v1/executor/ + v1/worker/ ─┐
│  Scheduler            │    │  Executor 分发 → Worker       │
│  KVCacheManager       │    │  GPUModelRunner:              │
│  KVCacheCoordinator   │    │    prepare_inputs → forward   │
│  BlockPool            │    │    → sample_tokens            │
│  决定「何时算哪些」    │    │  决定「如何算」              │
└───────────────────────┘    └─────────────────────────────┘
                                        │
                                        ▼
                              ┌─ model_executor/ ──────────┐
                              │  models/llama.py 等         │
                              │  layers/linear.py (并行层)  │
                              │  model_loader/ (权重加载)   │
                              └─────────────────────────────┘
```

**核心设计**：前后端分离。前端 `LLMEngine` 管「请求从哪来、结果回哪去」；后端 `EngineCore` 管「每步调度-执行-采样的紧循环」。两者通过 `EngineCoreClient`（IPC 抽象层：InprocClient/MpClient/AsyncMPClient）通信。

**V1 统一调度**：不再区分 prefill/decode 阶段。每个 Request 有 `num_computed_tokens` 和 `num_tokens_with_spec`，调度器让前者追后者——自然地处理了 chunked prefill、prefix caching、speculative decoding。

## 学习阶段

| 阶段 | 目录 | 学时 |
|------|------|------|
| 0 | [00-入口](00-入口/) — 找到正确的入口，避开废弃代码 | 15 分钟 |
| 1 | [01-用户API到引擎](01-用户API到引擎/) — 从 LLM.generate() 追到引擎入口 | 2~3 小时 |
| 2 | [02-V1引擎主循环](02-V1引擎主循环/) — EngineCore.step() 紧循环 | 3~5 小时 |
| 3 | [03-调度与KV缓存](03-调度与KV缓存/) — 调度器算法与 KV 块管理 | 4~6 小时 |
| 4 | [04-模型执行与采样](04-模型执行与采样/) — Executor/Worker/GPUModelRunner | 3~5 小时 |
| 5 | [05-模型实现](05-模型实现/) — 模型实现模式、层、加载 | 3~5 小时 |
| 6 | [06-Attention后端](06-Attention后端/) — 可插拔 attention 后端设计 | 2~3 小时 |
| 7 | [07-高级特性](07-高级特性/) — 投机解码、分布式、多模态等（按需） | 每项 1~3 天 |

**建议节奏**：阶段 0~1 第一天；阶段 2 第二天；阶段 3 第三~四天；阶段 4 第五~六天；阶段 5 第七~八天；阶段 6 第九天；阶段 7 按需深入。

## 阅读技巧

1. **用 IDE Ctrl+Click 追 import 链**。vLLM 大量使用 re-export（如 `vllm/engine/` → `vllm/v1/engine/`），IDE 跳转比 grep 快。
2. **忽略 C++/CUDA 代码直到必要**。`csrc/` 目录是 kernel 实现，第一遍全部跳过。
3. **复杂文件分多次读**：`scheduler.py`(1300行) 只读 `schedule()`；`model_runner.py`(3000+行) 只读 `execute_model()`/`load_model()`；`arg_utils.py`(2600行) 只扫字段分组。
4. **每读完一个阶段画图**。画出模块间的调用关系和数据流。
5. **配合 examples/tests 打断点**。`code/vllm/examples/` 和 `code/vllm/tests/` 有对应测试。

## 常见误区

| 误区 | 纠正 |
|------|------|
| 在 `vllm/engine/` 找代码 | 那是历史遗物，只有 re-export。一切在 `vllm/v1/` |
| 认为 prefill 和 decode 是不同阶段 | V1 已统一，只有 `num_computed_tokens` 追 `num_tokens_with_spec` |
| 从 CUDA kernel 开始读 | 先理解 Python 层的调度和模型执行流程 |
| 认为 `LLM` 和 `LLMEngine` 是同一个东西 | `LLM` 是用户入口，`LLMEngine` 是前端，`EngineCore` 才是后端引擎 |
| 忽略 `v1/engine/__init__.py` 的类型定义 | `EngineCoreRequest`/`EngineCoreOutput` 是理解数据流的基础 |
