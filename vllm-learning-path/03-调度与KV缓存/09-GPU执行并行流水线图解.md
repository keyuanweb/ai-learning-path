# 09 · GPU 执行并行流水线图解：计算 vs 数据加载

**源码参考**：
- [`code/vllm/vllm/v1/worker/gpu/model_runner.py`](../../code/vllm/vllm/v1/worker/gpu/model_runner.py) — 模型执行主逻辑
- [`code/vllm/vllm/v1/worker/gpu/async_utils.py`](../../code/vllm/vllm/v1/worker/gpu/async_utils.py) — 异步 D2H 拷贝与流管理
- [`code/vllm/vllm/v1/worker/gpu/buffer_utils.py`](../../code/vllm/vllm/v1/worker/gpu/buffer_utils.py) — 异步 H2D 拷贝与 UVA 缓冲池
- [`code/vllm/vllm/v1/worker/gpu/pp_utils.py`](../../code/vllm/vllm/v1/worker/gpu/pp_utils.py) — 流水线并行采样广播
- [`code/vllm/vllm/v1/engine/core.py`](../../code/vllm/vllm/v1/engine/core.py) — `step_with_batch_queue()` 调度-执行重叠
- [`code/vllm/vllm/v1/worker/gpu/dp_utils.py`](../../code/vllm/vllm/v1/worker/gpu/dp_utils.py) — 数据并行批次协调

---

vLLM 达到极致推理吞吐的秘诀在于**把计算和数据加载完全重叠**。本文档用气泡图拆解这背后的并行流水线机制。

阅读前建议先看过 [08-调度与批量执行图解.md](08-调度与批量执行图解.md)。

## 一、一张图看懂：GPU 时间线并行全景

一个推理 step 中，计算（蓝色）和数据加载（橙色）在两条 CUDA Stream 上并行推进：

```mermaid
flowchart TB
    subgraph timeline["GPU 时间线（一个 step 的并行分解）"]
        direction LR
        subgraph ms["main_stream（默认流）"]
            direction TB
            m1["① H2D: InputBatch<br/>写入 GPU 输入缓冲区"]
            m2["② Model Forward<br/>（CUDA Graph 重放）"]
            m3["③ Sample Tokens<br/>logits → token_ids"]
            m4["④ Postprocess<br/>更新 num_computed_tokens"]
            m5["⑤ Speculator Proposal<br/>（投机解码）"]
        end

        subgraph cs["output_copy_stream（拷贝流）"]
            direction TB
            c1["③→④ 并行: D2H Async Copy<br/>sampled_token_ids → CPU"]
            c2["logprobs → CPU"]
            c3["prompt_logprobs → CPU"]
        end

        subgraph bs["broadcast_stream（广播流，PP 场景）"]
            direction TB
            b1["③→④ 并行: Sampled Tokens<br/>广播到非尾 PP rank"]
        end
    end

    m1 --> m2 --> m3
    m3 --> m4 & c1
    c1 --> c2 --> c3
    m3 --> b1

    style ms fill:#d1ecf1,stroke:#0c5460
    style cs fill:#fff3cd,stroke:#ffc107
    style bs fill:#d4edda,stroke:#155724
```

> **核心原理**：模型前向在 `main_stream` 上执行完毕后，采样结果立即被 `output_copy_stream` 异步拷贝到 CPU。与此同时，`main_stream` 不等待拷贝完成，继续执行后处理和投机解码 draft 生成。两条流之间通过 CUDA Event 同步，确保拷贝完成时才读取 CPU 端数据。

## 二、六大并行维度气泡图

### 2.1 维度一：异步 D2H 拷贝（AsyncOutput）

模型前向完成后，采样结果要从 GPU 拷回 CPU。这一拷贝与后续 GPU 计算**完全并行**：

```mermaid
flowchart TB
    subgraph parallel["两条 CUDA Stream 并行执行"]
        direction LR

        subgraph comp["🔵 main_stream — 计算"]
            direction TB
            c_step["Sample Tokens<br/>（GPU Kernel）"]
            c_post["Postprocess Sampled<br/>（更新请求状态）"]
            c_spec["Speculator Propose<br/>（生成 draft tokens）"]

            c_step --> c_post --> c_spec
        end

        subgraph copy["🟠 output_copy_stream — 数据加载"]
            direction TB
            d1["copy_stream.wait_stream(main_stream)<br/>等待采样完成"]
            d2["async_copy_to_np(sampled_token_ids)<br/>GPU→CPU 异步拷贝"]
            d3["logprobs.to_cpu_nonblocking()<br/>GPU→CPU 异步拷贝"]
            d4["copy_event.record(copy_stream)<br/>标记拷贝完成"]

            d1 --> d2 --> d3 --> d4
        end
    end

    sync["EngineCore 侧: copy_event.synchronize()<br/>确保 CPU 端数据就绪后返回结果"]

    c_step -.->|"CUDA Event 同步点"| d1
    d4 -.->|"同步点"| sync

    style comp fill:#d1ecf1,stroke:#0c5460,stroke-width:2px
    style copy fill:#fff3cd,stroke:#ffc107,stroke-width:2px
```

**源码关键代码**（[async_utils.py](../../code/vllm/vllm/v1/worker/gpu/async_utils.py)）：

```python
class AsyncOutput:
    def __init__(self, model_runner_output, sampler_output,
                 num_sampled_tokens, main_stream, copy_stream):
        self.copy_event = torch.cuda.Event(blocking=True)
        with stream(copy_stream, main_stream):
            copy_stream.wait_stream(main_stream)           # ← 等主流的采样 kernel 跑完
            self.sampled_token_ids = async_copy_to_np(...) # ← 异步拷贝（非阻塞）
            self.logprobs_tensors = logprobs.to_cpu_nonblocking()
            self.copy_event.record(copy_stream)            # ← 记录拷贝完成信号
        # 控制权立即返回 — main_stream 继续往后跑，不等拷贝
```

**收益**：每次 step 节省 ~50-200μs 的 D2H 等待时间。在 decode-heavy 场景下，这相当于 3~8% 的延迟降低。

### 2.2 维度二：异步 H2D 拷贝（InputBatch 构建）

每步调度结束后，CPU 上的 `SchedulerOutput` 需要拷贝到 GPU 的 InputBatch 缓冲区。这些 H2D 拷贝全部使用 `non_blocking=True`：

```mermaid
flowchart TB
    subgraph h2d["🔵 H2D 异步拷贝流水线"]
        direction LR

        subgraph cpu_side["CPU 侧准备"]
            c1["Scheduler.schedule()<br/>产出 SchedulerOutput"]
            c2["ModelRunner.prepare_inputs()<br/>构建 numpy 数组"]
            c3["从 CPU pinned memory<br/>启动 non_blocking H2D 拷贝"]
        end

        subgraph gpu_side["GPU 侧消费"]
            g1["input_ids<br/>copy_(pinned_cpu, non_blocking=True)"]
            g2["query_start_loc<br/>copy_(pinned_cpu, non_blocking=True)"]
            g3["idx_mapping<br/>copy_(pinned_cpu, non_blocking=True)"]
        end

        c1 --> c2 --> c3
        c3 --> g1 & g2 & g3
    end

    overlap["💡 拷贝期间 GPU 可能正在执行上一步的 CUDA Graph<br/>H2D 拷贝和上一 step 的计算重叠"]

    style cpu_side fill:#e8daef,stroke:#7d3c98
    style gpu_side fill:#d1ecf1,stroke:#0c5460
```

**关键机制**：
- CPU 端使用 **pinned memory**（`pin_memory()`），DMA 引擎可直接读写，无需 CPU 中转
- `non_blocking=True` 让拷贝命令提交后立即返回，GPU 在后台完成传输
- **UVA Buffer Pool**（[buffer_utils.py](../../code/vllm/vllm/v1/worker/gpu/buffer_utils.py)）：环形缓冲池，支持多步并发的 H2D 拷贝互不覆盖

### 2.3 维度三：流水线并行 — 调度与执行重叠

当启用 PP（Pipeline Parallelism）时，`step_with_batch_queue()` 通过 Batch Queue 让 CPU 调度和 GPU 执行完全重叠：

```mermaid
flowchart TB
    subgraph pp_timeline["PP 模式时间线（batch_queue_size=3）"]
        direction LR
        subgraph step1["t=0: Step"]
            s1_s["调度 Batch A"]
            s1_g["GPU: A.Rank0 → A.Rank1 → A.Rank2"]
            s1_s -.-> s1_g
        end
        subgraph step2["t=1: Step"]
            s2_s["调度 Batch B"]
            s2_g["GPU: B.Rank0"]
            s2_s -.-> s2_g
        end
        subgraph step3["t=2: Step"]
            s3_s["调度 Batch C"]
            s3_g["GPU: C.Rank0"]
            s3_s -.-> s3_g
        end
        subgraph step4["t=3: Step"]
            s4_g["GPU: A 完成，取结果"]
        end
    end

    annotation["💡 CPU 调度 Batch B/C 时，GPU 仍在执行 Batch A<br/>→ CPU 调度开销被完全隐藏"]
```

**Batch Queue 机制**：

```mermaid
flowchart TB
    enter["step_with_batch_queue() 被调用"]

    try_sched{"batch_queue 未满<br/>且有未调度请求?"}
    sched["schedule() + execute_model(non_block=True)<br/>→ 将 (future, scheduler_output) 入队"]
    return_none["直接返回 None<br/>不等待 GPU 结果"]

    queue_has{"batch_queue 非空?"}
    pop["从队尾 pop 最早的 future<br/>阻塞等待 model_output = future.result()"]
    process["update_from_output()<br/>返回 EngineCoreOutputs"]

    enter --> try_sched
    try_sched -->|是| sched --> return_none
    try_sched -->|否| queue_has
    queue_has -->|是| pop --> process
    queue_has -->|否| return_none
```

**PP 采样广播并行**（[pp_utils.py](../../code/vllm/vllm/v1/worker/gpu/pp_utils.py)）：

```mermaid
flowchart TB
    subgraph pp_bcast["PPHandler: 采样令牌广播"]
        direction LR
        subgraph last["Last PP Rank (拥有采样结果)"]
            l1["main_stream: sample_tokens()"]
            l2["broadcast_stream: dist.broadcast()<br/>通过专用 NCCL communicator"]
            l3["main_stream: postprocess()<br/>继续执行，不等待广播完成"]
            l1 --> l2
            l2 -.->|并行| l3
        end
        subgraph other["Non-Last PP Rank"]
            o1["broadcast_stream: dist.broadcast() 接收"]
            o2["main_stream: 继续其他工作"]
            o1 -.->|并行| o2
        end
    end

    note["💡 专用 broadcast_stream + 专用 NCCL communicator<br/>→ 采样广播不与层间 hidden state p2p send/recv 序列化"]

    style last fill:#d4edda,stroke:#155724
    style other fill:#d1ecf1,stroke:#0c5460
```

### 2.4 维度四：CUDA Graph — 消灭 Kernel Launch 开销

CUDA Graph 将整个模型前向的所有 kernel 调用预录制为单个可重放的计算图：

```mermaid
flowchart TB
    subgraph compare["Eager vs CUDA Graph 对比"]
        direction LR
        subgraph eager["Eager 模式"]
            e1["Python: for layer in model.layers:"]
            e2["  launch_attn_kernel() ← CPU→GPU 同步"]
            e3["  launch_ffn_kernel()  ← CPU→GPU 同步"]
            e4["  launch_norm_kernel() ← CPU→GPU 同步"]
            e5["... × 80 layers = 240+ kernel launches"]
            e6["每次 launch ≈ 3-10μs CPU 开销"]
            e1 --> e2 --> e3 --> e4 --> e5 --> e6
        end

        subgraph cg["CUDA Graph 模式"]
            c1["cudagraph_manager.run_fullgraph()<br/>← 单次 CUDA API 调用"]
            c2["GPU 自行串行执行所有 kernel<br/>无 CPU 介入"]
            c3["节省: 240 × 5μs ≈ 1.2ms/step<br/>（decode 场景占比 ~10-15%）"]
            c1 --> c2 --> c3
        end
    end

    style eager fill:#f8d7da,stroke:#721c24
    style cg fill:#d4edda,stroke:#155724
```

**三种 CUDA Graph 模式**：

| 模式 | 适用场景 | batch 形状要求 |
|------|---------|:---:|
| **FULL** | 全 decode（每个请求 1 token） | batch_size 和 token 数必须精确匹配录制时的值 |
| **PIECEWISE** | 混合 batch（含 chunked prefill） | 按 Attention 边界分段的可中断图 |
| **NONE** | 罕见 batch 配置、profile | 直接 eager forward |

### 2.5 维度五：数据并行（DP）— 多 GPU 独立调度

DP 模式下，多个 GPU 独立运行各自的 EngineCore，通过 all_reduce 协调 batch 形状：

```mermaid
flowchart TB
    subgraph dp["DP 多 GPU 并行"]
        direction LR

        subgraph gpu0["GPU 0 (dp_rank=0)"]
            g0_s["schedule() → 128 tokens, 50 reqs"]
            g0_g["execute_model()"]
        end

        subgraph gpu1["GPU 1 (dp_rank=1)"]
            g1_s["schedule() → 96 tokens, 38 reqs"]
            g1_g["execute_model()"]
        end

        sync["dispatch_cg_and_sync_dp()<br/>all_reduce: 对齐 CUDA Graph 模式<br/>选定 max(num_tokens)<br/>padding 补齐差异"]
    end

    g0_s & g1_s --> sync
    sync --> g0_g & g1_g
```

**DP 预填充平衡（prefill throttling）**：非对齐步骤推迟 prefill compute，确保 DP rank 间的 prefill 批次对齐，避免某个 rank 过载。

### 2.6 维度六：KV Cache Offload 异步传输

KV 缓存可以在 GPU ↔ CPU ↔ 远程存储之间异步迁移，与计算并行：

```mermaid
flowchart TB
    subgraph kv_offload["KV Offload 并行流水线"]
        direction LR

        subgraph compute_pipe["GPU 计算"]
            c1["Step N: Forward<br/>使用 GPU KV Cache"]
            c2["Step N+1: Forward<br/>使用 GPU KV Cache"]
        end

        subgraph offload_pipe["后台异步传输"]
            o1["KV Blocks 异步保存<br/>GPU → CPU (non_blocking)"]
            o2["KV Blocks 异步加载<br/>CPU → GPU (non_blocking)"]
            o3["KV Connector<br/>远端 KV 传输<br/>（Mooncake/NIXL/LMCache）"]
        end
    end

    c1 -.->|"并行"| o1
    o1 -.-> o2 -.-> o3

    style compute_pipe fill:#d1ecf1,stroke:#0c5460
    style offload_pipe fill:#fff3cd,stroke:#ffc107
```

**调度器侧的配合**：
- `defer_block_free`：异步调度场景下延迟释放 KV block，避免消费者 connector 的加载与写入产生竞争
- `WAITING_FOR_REMOTE_KVS`：请求等待远端 KV 加载完成的状态，加载期间不调度该请求的 prefill

---

## 三、端到端流水线气泡图

将六大维度合并，一个 step 的 GPU 时间线全景：

```mermaid
flowchart TB
    subgraph full_pipeline["一个 Step 的完整 GPU 时间线"]
        direction LR

        subgraph phase1["阶段1: 数据加载 H2D"]
            p1a["CPU 准备 InputBatch<br/>→ 异步拷贝到 GPU buffer<br/>（non_blocking）"]
        end

        subgraph phase2["阶段2: 模型前向"]
            p2a["CUDA Graph 重放<br/>（单次 API 调用）"]
        end

        subgraph phase3["阶段3: 采样"]
            p3a["GPU Kernel: logits → token_ids"]
        end

        subgraph phase4["阶段4: 并行后处理"]
            direction LR
            subgraph p4_main["main_stream"]
                p4a["Postprocess: 更新 token 状态"]
                p4b["Speculator: draft token 生成"]
                p4c["KV Connector: post_forward"]
                p4a --> p4b --> p4c
            end
            subgraph p4_copy["output_copy_stream"]
                p4d["Async D2H: token_ids → CPU"]
                p4e["Async D2H: logprobs → CPU"]
                p4d --> p4e
            end
            subgraph p4_bcast["broadcast_stream (PP)"]
                p4f["Async Broadcast: tokens 到非尾 rank"]
            end
        end

        subgraph phase5["阶段5: 同步与返回"]
            p5a["copy_event.synchronize()<br/>等待 CPU 端数据就绪"]
            p5b["返回 EngineCoreOutputs"]
        end
    end

    phase1 --> phase2 --> phase3 --> phase4 --> phase5
    p4_main & p4_copy & p4_bcast -.->|"并行执行"| phase5

    style phase1 fill:#e8daef,stroke:#7d3c98,stroke-width:2px
    style phase2 fill:#d1ecf1,stroke:#0c5460,stroke-width:2px
    style phase3 fill:#d4edda,stroke:#155724,stroke-width:2px
    style phase4 fill:#fff3cd,stroke:#ffc107,stroke-width:2px
    style phase5 fill:#f5b7b1,stroke:#922b21,stroke-width:2px
```

---

## 四、性能收益总结

```mermaid
flowchart LR
    subgraph gains["极致性能的三大支柱"]
        direction TB

        subgraph g1["① 计算与数据加载重叠"]
            g1a["Async D2H: 采样结果拷贝<br/>与后处理/投机解码并行"]
            g1b["Async H2D: InputBatch 拷贝<br/>与上步 CUDA Graph 执行并行"]
            g1c["收益: 每 step 节省 ~50-200μs"]
        end

        subgraph g2["② 调度与执行重叠"]
            g2a["Batch Queue: CPU 调度<br/>与 GPU 执行流水线化"]
            g2b["PP Broadcast: 采样分发<br/>与主计算流脱耦"]
            g2c["收益: GPU 空闲率 → 接近 0%"]
        end

        subgraph g3["③ Kernel Launch 消除"]
            g3a["CUDA Graph: 240+ kernel 调用<br/>→ 单次 API 重放"]
            g3b["Triton Kernel: 一次覆盖<br/>全部 rows（如 StagedWrite）"]
            g3c["收益: decode 延迟 ~10-15% 降低"]
        end
    end

    style g1 fill:#d1ecf1,stroke:#0c5460
    style g2 fill:#fff3cd,stroke:#ffc107
    style g3 fill:#d4edda,stroke:#155724
```

---

## 五、关键概念速查

| 概念 | 机制 | 并行对象 |
|------|------|---------|
| **CUDA Stream** | 同一 GPU 上独立执行队列，不同 stream 的操作可并行 | 计算(主) ↔ 数据拷贝(副) |
| **AsyncOutput** | `copy_stream` 异步 D2H + `copy_event` 同步点 | 采样结果拷贝 ↔ Postprocess |
| **Batch Queue** | deque 持有多个 in-flight step，调度和 GPU 执行流水线化 | CPU 调度 ↔ GPU 执行 |
| **PPHandler** | 专用 `broadcast_stream` + 专用 NCCL communicator | 采样广播 ↔ 层间 p2p send/recv |
| **CUDA Graph** | 预录制 kernel 序列，运行时单次重放 | Kernel launch 开销 → 0 |
| **StagedWriteTensor** | 批量积累写入，单次 Triton kernel 应用 | CPU 侧多次小写入 ↔ GPU 侧单次批量写入 |
| **UVA Buffer Pool** | 环形 pinned memory 缓冲，多步并发 H2D | 多个 step 的 H2D 拷贝互不覆盖 |
| **KV Offload** | GPU↔CPU KV block 异步传输，与 forward 并行 | KV 移动 ↔ 模型计算 |

---

## 阅读重点

- 理解**两条 CUDA Stream**（main + copy）如何并行：main 算后续步骤，copy 搬运采样结果
- 背下 AsyncOutput 的时序：`copy_stream.wait_stream(main)` → async copy → `copy_event.record` → EngineCore 侧 `synchronize()`
- 理解 **Batch Queue** 如何消除 PP 气泡：CPU 永远提前调度好下一个 batch
- CUDA Graph 不是"优化"而是"基础设施"——默认开启，对用户透明
- UVA Buffer Pool 的环形设计保证了多步并发 H2D 的安全性

**相关文档**：
- [08-调度与批量执行图解.md](08-调度与批量执行图解.md) — 调度→执行全链路 Mermaid 图解
- [01-调度器.md](01-调度器.md) — `Scheduler.schedule()` 源码详解
- [../04-模型执行与采样/03-GPUModelRunner.md](../04-模型执行与采样/03-GPUModelRunner.md) — execute_model() 源码详解
- [../02-V1引擎主循环/05-后端引擎.md](../02-V1引擎主循环/05-后端引擎.md) — step() / step_with_batch_queue() 源码
