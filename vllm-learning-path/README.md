# vLLM 源码学习路径

> 基于对 `code/vllm/vllm/` 目录的通读生成，按学习阶段分目录组织。
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
                           │  (通过 ZMQ 或内存直传)
                           ▼
┌─ v1/engine/core.py ──────────────────────────────────────┐
│  EngineCore（后端）：推理紧循环                             │
│  每次 step() 做五件事：                                    │
│    1. Scheduler.schedule()   → 决定这步算哪些 token       │
│    2. Executor.execute_model() → GPU 跑前向               │
│    3. Scheduler.get_grammar_bitmask() → 结构化输出约束     │
│    4. Executor.sample_tokens()  → 采样出 token            │
│    5. Scheduler.update_from_output() → 更新状态、释放 KV   │
└──────┬──────────────────────────────┬────────────────────┘
       │                              │
       ▼                              ▼
┌─ v1/core/sched/ ─────┐    ┌─ v1/executor/ + v1/worker/ ─┐
│  Scheduler            │    │  Executor 分发到 Worker       │
│  KVCacheManager       │    │  GPUModelRunner 跑 forward    │
│  决定「何时算哪些」    │    │  决定「如何算」              │
└───────────────────────┘    └─────────────────────────────┘
                                        │
                                        ▼
                              ┌─ model_executor/ ──────────┐
                              │  models/llama.py 等         │
                              │  layers/linear.py 等        │
                              │  model_loader/              │
                              └─────────────────────────────┘
```

**核心设计**：前后端分离。前端（`LLMEngine`）管「请求从哪来、结果回哪去」；后端（`EngineCore`）管「每步调度-执行-采样的紧循环」。两者通过 `EngineCoreClient`（IPC 抽象层）通信。

## 学习阶段

| 阶段 | 目录 | 学时 |
|------|------|------|
| 0 | [00-入口](00-入口/) — 找到正确的入口，避开废弃代码 | 15 分钟 |
| 1 | [01-用户API到引擎](01-用户API到引擎/) — 从 LLM.generate() 追到引擎入口 | 2~3 小时 |
| 2 | [02-V1引擎主循环](02-V1引擎主循环/) — EngineCore.step() 五步紧循环 | 3~5 小时 |
| 3 | [03-调度与KV缓存](03-调度与KV缓存/) — 调度器算法与 KV 块管理 | 4~6 小时 |
| 4 | [04-模型执行与采样](04-模型执行与采样/) — Executor/Worker/GPUModelRunner | 3~5 小时 |
| 5 | [05-模型实现](05-模型实现/) — 模型实现模式、层、加载 | 3~5 小时 |
| 6 | [06-Attention后端](06-Attention后端/) — 可插拔 attention 后端设计 | 2~3 小时 |
| 7 | [07-高级特性](07-高级特性/) — 投机解码、分布式、多模态等（按需） | 每项 1~3 天 |

**建议节奏**：阶段 0~1 第一天；阶段 2 第二天；阶段 3 第三~四天；阶段 4 第五~六天；阶段 5 第七~八天；阶段 6 第九天；阶段 7 按需深入。

## 阅读技巧

1. **用 IDE Ctrl+Click 追 import 链**。vLLM 大量使用 re-export，IDE 跳转比 grep 快得多。
2. **忽略 C++/CUDA 代码直到必要**。`csrc/` 目录是 kernel 实现，第一遍全部跳过。
3. **复杂文件分多次读**：`scheduler.py`(1300行) 只读 `schedule()` 和 `update_from_output()`；`model_runner.py`(3000+行) 只读 `execute_model()` 和 `load_model()`；`arg_utils.py`(2600行) 只扫字段分组。
4. **每读完一个阶段画图**。画出模块间的调用关系。

## 常见误区

| 误区 | 纠正 |
|------|------|
| 在 `vllm/engine/` 找代码 | 那是历史遗物，只有 re-export。一切在 `vllm/v1/` |
| 认为 prefill 和 decode 是不同阶段 | V1 已统一，只有 `num_computed_tokens` 追 `num_tokens` |
| 从 CUDA kernel 开始读 | 先理解 Python 层的调度和模型执行流程 |
| 认为 `LLM` 和 `LLMEngine` 是同一个东西 | `LLM` 是用户入口，`LLMEngine` 是前端，`EngineCore` 才是引擎 |

## 目录

```
vllm-learning-path/
├── README.md                    # 总览 + 架构图 + 学习建议
├── 00-入口/                     # 15 分钟
│   ├── 01-符号地图.md           # vllm/__init__.py 的导出清单
│   └── 02-废弃目录.md           # vllm/engine/ 是历史 shim
├── 01-用户API到引擎/            # 2~3 小时
│   ├── 01-LLM类.md              # entrypoints/llm.py
│   ├── 02-配置系统.md           # EngineArgs → VllmConfig
│   └── 03-输入输出类型.md        # inputs / outputs / SamplingParams
├── 02-V1引擎主循环/             # 3~5 小时
│   ├── 01-核心类型定义.md       # EngineCoreRequest/Output/FinishReason
│   ├── 02-请求内部表示.md       # num_computed_tokens vs num_tokens
│   ├── 03-前端引擎.md            # LLMEngine
│   ├── 04-IPC抽象层.md          # InprocClient / SyncMPClient / AsyncMPClient
│   ├── 05-后端引擎.md           # EngineCore.step() 五步紧循环
│   └── 06-辅助组件.md           # InputProcessor/OutputProcessor/序列化
├── 03-调度与KV缓存/             # 4~6 小时
│   ├── 01-调度器.md              # Scheduler.schedule() 算法
│   ├── 02-调度输出结构.md        # SchedulerOutput / NewRequestData
│   ├── 03-KV缓存管理器.md        # KVCacheManager 接口
│   ├── 04-KV缓存协调器.md        # BlockPool / KVCacheBlock
│   └── 05-KV缓存规格.md          # FullAttentionSpec / MLAAttentionSpec
├── 04-模型执行与采样/           # 3~5 小时
│   ├── 01-Executor抽象.md        # execute_model / sample_tokens
│   ├── 02-Worker抽象.md          # WorkerBase / WorkerWrapperBase
│   ├── 03-GPUModelRunner.md      # execute_model() 四个步骤 + CUDA Graph
│   └── 04-采样器.md              # Sampler.forward() 六步流程
├── 05-模型实现/                 # 3~5 小时
│   ├── 01-模型实现模式.md        # Llama 五层结构 + 标准 forward 签名
│   ├── 02-模型注册与加载.md      # ModelRegistry + DefaultModelLoader
│   ├── 03-关键层实现.md          # 并行 Linear / VocabParallelEmbedding
│   └── 04-能力接口.md            # SupportsLoRA / SupportsPP / ...
├── 06-Attention后端/            # 2~3 小时
│   ├── 01-后端注册.md            # 标准 / MLA / Mamba 三类后端
│   ├── 02-后端选择.md            # get_attn_backend() 验证链
│   └── 03-Attention实现层次.md   # AttentionImpl / MLAAttentionImpl / MetadataBuilder
└── 07-高级特性/                 # 按需
    ├── 01-投机解码.md
    ├── 02-分布式并行.md
    ├── 03-多模态.md
    ├── 04-结构化输出.md
    └── 05-量化与KV卸载.md
```

