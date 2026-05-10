# KV-Cache 机制

> KV Cache 是 Transformer 推理优化的起点。没有它，每生成一个新 token 的耗时将线性增长，有它则是常数时间。

---

## 1. 没有 KV Cache 的灾难

### 问题

自回归生成每步都会重新计算整个序列的 Attention。在第 t 步：

```python
# 序列: [tok_0, tok_1, ..., tok_t]  共 t+1 个 token
# Attention 计算: Q @ K^T → (t+1) × (t+1) 矩阵
```

第 t 步的计算量 ∝ (t+1)²。生成 N 个 token 的总计算量 ∝ N³。这是不可接受的——生成 4096 个 token 的计算量可能是第 1 个 token 的 1600 万倍。

### KV Cache 的核心洞察

> 已生成的 token 的 K 和 V 不会变化，每一步重新算一遍是纯粹浪费。把它们存起来即可。

---

## 2. KV Cache 的工作机制

### 原理

第 t+1 步时，只有新 token $x_t$ 的 $K_t$ 和 $V_t$ 是新的。前面的 $K_{0:t-1}$ 和 $V_{0:t-1}$ 与上一步完全相同。

```python
# 没有 KV Cache (浪费)
for step in range(max_len):
    K_all = compute_K(x_all)  # 重新算所有旧 token 的 K
    V_all = compute_V(x_all)  # 重新算所有旧 token 的 V
    attn = softmax(Q[-1] @ K_all^T) @ V_all

# 有 KV Cache (高效)
K_cache, V_cache = [], []
for step in range(max_len):
    k_new, v_new = compute_KV(x_new)       # 只算新 token
    K_cache = concat([K_cache, k_new])     # 追加到缓存
    V_cache = concat([V_cache, v_new])
    attn = softmax(Q_new @ K_cache^T) @ V_cache  # 用缓存
```

### 复杂度变化

| | 无 KV Cache | 有 KV Cache |
|---|---|---|
| 第 t 步计算量 | O(t²·d) | O(t·d) |
| 生成 N token 总量 | O(N³·d) | O(N²·d) |
| 实际加速 | — | 10-100× (取决于序列长度) |

---

## 3. KV Cache 的显存分析

### KV Cache 的大小

每个 token 的 KV Cache 计算（单层 K + V）：

$$\text{PerTokenPerLayer} = 2 \times n\_kv\_heads \times d\_k \times \text{bytes\_per\_elem}$$

全部层的总 KV Cache：

$$\text{KV Cache Size} = 2 \times n\_layers \times n\_kv\_heads \times seq\_len \times d\_k \times \text{bytes\_per\_elem}$$

> 公式中第一个 `2` = K + V 两份缓存, `bytes_per_elem` = 2 (BF16/FP16)。

以 LLaMA-7B (32 层, 32 KV heads, $d_k=128$, BF16):

$$\text{每 token} = 2 \times 32 \times 32 \times 1 \times 128 \times 2 = 524288 \text{ bytes} = 512 \text{ KiB}$$

| 序列长度 | 总 KV Cache |
|----------|-------------|
| 1K (1024) | 512 MiB |
| 4K (4096) | 2 GiB |
| 32K | 16 GiB |
| 128K | 64 GiB ← 已经超过单卡 H100 (80GB) 显存！ |

> 简化公式：$\text{KV Cache} = 2 \times n\_{layers} \times d\_{model} \times seq\\_len \times 2 \text{ bytes}$ ，因为 $n\_{kv\\_heads} \times d\_k = d\_{model}$。

**KV Cache 是长序列推理的主要显存瓶颈。** 这就是为什么 GQA（减少 KV 头数）和 MLA（KV 压缩）如此重要。

---

## 4. KV Cache 的优化技术

### GQA/MQA

减少 KV 头的数量 → KV Cache 直接缩小：

| 方案 | 例子 | KV Cache 缩小 |
|------|------|-------------|
| MHA | 32 Q, 32 KV | 1× |
| GQA | 32 Q, 8 KV | 4× |
| MQA | 32 Q, 1 KV | 32× |

### PagedAttention (vLLM 的核心)

将 KV Cache 按"页"管理（类似操作系统虚拟内存），而非线性连续分配：
- 解决碎片化（不同请求序列长度不同，线性分配浪费显存）
- 允许内存"共享"（不同请求可以共享相同的 prompt prefix 的 KV Cache）
- 吞吐量提升 2-4×

### KV Cache 量化

将 K 和 V 从 FP16 量化到 INT8 或更低 → KV Cache 大小直接减半或减到 1/4。

---

## 5. 为什么 KV Cache 不能完全消除

### Multi-Query 为什么不行

如果所有 Q 头共享一组 K/V（MQA），虽然 KV Cache 最小，但建模能力会下降。每个头学到的是不同的"注意力模式"——头1关注句法距离，头2关注语义相关性。让它们共享同一组 Key 相当于把它们绑在一起，失去"分头"的意义。

### GQA 的折中

分组共享（如 8 组）在大幅减少 KV Cache 的同时保留了多模式的能力。这是当前最好的平衡点。
