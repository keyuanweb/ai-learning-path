# 03 · Attention 实现层次

## 三层架构

```
AttentionBackend (注册在 registry)
  │ 静态方法: 描述自己是什么
  │ 验证: 与环境的兼容性
  │ 能力: is_mla(), is_sparse()
  │
  ├─→ AttentionImpl (ABC)
  │   └── forward(layer, query, key, value, kv_cache, attn_metadata, output)
  │       标准 PagedAttention 的前向。
  │       kv_cache 参数 = PagedAttention 核心
  │
  ├─→ MLAAttentionImpl (ABC)
  │   ├── forward_mha(q, kv_c_normed, k_pe, kv_cache, attn_metadata)
  │   │   MLA 的多头 attention 部分
  │   └── forward_mqa(q, kv_c_and_k_pe_cache, attn_metadata, layer)
  │       MLA 的多查询 attention 部分
  │
  └─→ AttentionMetadataBuilder (ABC)
      ├── build(common_prefix_len, common_attn_metadata) → metadata
      │   为每个 batch 构建 attention 元数据
      ├── build_for_cudagraph_capture(...)
      ├── update_block_table(...)
      └── use_cascade_attention(...)
```

## AttentionImpl.forward() 的签名是 PagedAttention 的核心

```python
class AttentionImpl(ABC):
    def forward(
        self,
        layer: AttentionLayerBase,      # 发起调用的 attention 层
        query: torch.Tensor,            # [num_tokens, num_heads, head_size]
        key: torch.Tensor,              # [num_tokens, num_kv_heads, head_size]
        value: torch.Tensor,            # [num_tokens, num_kv_heads, head_size]
        kv_cache: torch.Tensor,         # 物理 KV 缓存张量（PagedAttention 核心！）
        attn_metadata: "AttentionMetadata",  # batch 级别的元数据（block_table 等）
        output: torch.Tensor,           # [num_tokens, num_heads, head_size] 输出
    ): ...
```

`kv_cache` 就是 PagedAttention 中的「页表」。kernel 通过 `attn_metadata` 中的 `block_table` 索引到 `kv_cache` 中的对应块，直接从 KV 缓存读取/写入，不需要为每个序列分配临时显存。

## AttentionMetadataBuilder — 为每步构建元数据

每个 attention 后端有自己的 `AttentionMetadataBuilder` 子类。它的职责是把 `SchedulerOutput` 中的 block_tables、context_lens 等转成 attention kernel 需要的格式。

## CUDA Graph 支持级别

```python
class CUDAGraphSupport(IntEnum):
    ALWAYS = 3           # 任何 batch 都能用
    UNIFORM_BATCH = 2    # 所有 query 长度相同才能用
    UNIFORM_SINGLE_TOKEN_DECODE = 1  # 纯 decode（每个请求 1 token）才能用
    NEVER = 0            # 不支持 CUDA graph
```

## 阅读重点

- 理解 `AttentionImpl.forward()` 的 kv_cache 参数
- `AttentionMetadataBuilder` 是调度层到 kernel 层的桥梁
- 不同后端的关键差异在于 `forward()` 中使用的 CUDA/Triton kernel
