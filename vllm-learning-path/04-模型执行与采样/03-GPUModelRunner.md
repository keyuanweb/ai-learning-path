# 03 · GPUModelRunner（核心！）

**源码**：[`code/vllm/vllm/v1/worker/gpu/model_runner.py`](../../code/vllm/vllm/v1/worker/gpu/model_runner.py)

约 3000+ 行。这是 worker 侧最核心的文件。第一遍只读 `execute_model()` 和 `load_model()`。

## `load_model()` — 模型加载

1. 通过 `get_model_loader()` 获取加载器
2. `loader.load_model(vllm_config)` 实例化模型并加载权重
3. 如果启用了 LoRA，用 LoRA 适配器包装模型
4. 如果有 EAGLE 投机解码，加载 aux hidden states 层
5. 如果是 PP 的非首 rank，创建持久化的 `intermediate_tensors`

## `execute_model()` — 一次前向执行

```python
def execute_model(self, scheduler_output: SchedulerOutput):
    # 1. 更新请求状态
    #    从 scheduler_output 读取 new_reqs / cached_reqs
    #    更新内部的 req_states 字典

    # 2. 构建 InputBatch
    input_ids = ...       # 本步要计算的 token IDs
    positions = ...       # 每个 token 在序列中的位置
    block_tables = ...    # KV 缓存的块表（每个序列 → 物理块号列表）
    slot_mappings = ...   # 每个 token 写入 KV 缓存的哪个 slot

    # 3. 构建 Attention Metadata
    attn_metadata = self.model_state.prepare_attn(
        block_tables, context_lens, slot_mappings, ...
    )

    # 4. 跑模型前向
    if cudagraph_mode == FULL:
        hidden_states = self.cudagraph_manager.run_fullgraph(batch_desc)
    else:
        hidden_states = self.model(
            input_ids=input_ids,
            positions=positions,
            intermediate_tensors=...,
            inputs_embeds=...
        )

    # 5. 返回
    if is_last_pp_rank:
        # 如果是尾 PP rank：采样的结果已经在 CUDA graph 中算好了
        return ModelRunnerOutput(sampled_token_ids=...)
    else:
        # 如果是中间 PP rank：返回中间张量给下一个 rank
        return IntermediateTensors(...)
```

## 关键数据结构

### InputBatch / InputBuffers

从 `SchedulerOutput` 构建模型输入的批处理结构。包括：
- `input_ids`: `[total_tokens]` 本步要计算的所有 token
- `positions`: `[total_tokens]` 每个 token 的位置
- `block_tables`: `[num_seqs, max_blocks]` KV 缓存的块表

### BlockTables

管理序列到 KV 物理块的映射。每个 GPU worker 维护自己的一组块表。

### CUDAGraphManager

在 warmup 阶段录制多种 batch 规模的 CUDA graph。运行时根据 batch size 匹配最适合的 graph 直接重放。

CUDA graph 的三个支持级别：
- `ALWAYS` — 任何时候都能重放
- `UNIFORM_SINGLE_TOKEN_DECODE` — 只在纯 decode（每个请求只算 1 个 token）时能用
- `UNIFORM_BATCH` — 只在所有请求 query 长度相同时能用
- `NEVER` — 不支持（如某些 attention backend）

## 阅读重点

- `execute_model()` 的四个步骤
- `block_tables` 和 `slot_mappings` 的语义（这是 PagedAttention 的核心数据）
- CUDA graph 的作用（减少 kernel launch overhead）
- 跳过 `cudagraph_manager` 的实现细节
