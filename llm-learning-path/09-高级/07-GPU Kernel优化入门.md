# GPU Kernel 优化入门

PyTorch 的高层 API 隐藏了 GPU 计算的大部分细节。当你需要超越标准实现的性能时（FlashAttention 的诞生就来自于此），你需要理解 GPU 计算的基本原理并手写 Triton kernel。

---

## 1. GPU 计算的基本瓶颈

### CPU vs GPU 的差异

| | CPU | GPU |
|------|-----|-----|
| 核心数 | 8-32 个强核心 | 数千个小核心 |
| 擅长 | 串行逻辑、分支 | 并行数值计算 |
| 模型类比 | 几位大学教授 | 几千个小学生 |

大模型计算 = 大量并行的矩阵乘法和逐元素运算 → 天然适合 GPU。

### 真正的瓶颈不是计算，是内存带宽

```
GPU 每秒钟能算 300 TFLOPS（FP16）
但显存带宽只有 ~2 TB/s
每次计算需要从显存读取数据 → 带宽成为瓶颈
```

**FlashAttention 的革命性**：不是"算得更快"，而是"减少显存读写次数"——计算量反而增加了（有重计算），但因为少读了数据，总时间反而更短。

---

## 2. Triton 语言入门

### 为什么用 Triton

CUDA 是 GPU 原生语言，但开发效率极低（手动管理线程块、共享内存、同步）。Triton 是 Python 风格的 GPU 编程语言，编译器自动处理底层线程管理。

```python
# 标准 PyTorch
def add_pytorch(x, y):
    return x + y

# Triton kernel（逐元素加法）
import triton
import triton.language as tl

@triton.jit
def add_kernel(x_ptr, y_ptr, output_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    # 获取当前"程序"的索引
    pid = tl.program_id(0)    # 类似"我在第几个线程块"
    block_start = pid * BLOCK_SIZE
    offsets = block_start + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements  # 防止越界

    # 从显存加载数据
    x = tl.load(x_ptr + offsets, mask=mask)
    y = tl.load(y_ptr + offsets, mask=mask)

    # 计算
    output = x + y

    # 写回显存
    tl.store(output_ptr + offsets, output, mask=mask)

# 调用 kernel
def add_triton(x: torch.Tensor, y: torch.Tensor):
    output = torch.empty_like(x)
    n_elements = x.numel()
    grid = lambda meta: (triton.cdiv(n_elements, meta['BLOCK_SIZE']),)

    add_kernel[grid](x, y, output, n_elements, BLOCK_SIZE=1024)
    return output
```

### Triton 核心概念

| 概念 | 直觉 |
|------|------|
| **Program** | GPU 上一个独立的"计算单元"。每个 program 处理数据的一部分 |
| **Block** | 每次处理的数据块大小。太小→并行度不足，太大→一个 program 做太多 |
| **Grid** | 总共需要多少个 program 来覆盖全部数据 |
| **Mask** | 防止数据量不能被 block 整除时的越界访问 |

---

## 3. 从零实现简化版 FlashAttention

### FlashAttention 的核心思想

标准 Attention 的实现：
```python
# 标准做法：完整计算 QK^T → Softmax → × V（显存开销大）
S = Q @ K.T            # [N, N] 存储到 HBM
P = softmax(S)         # [N, N] 存储到 HBM
O = P @ V              # [N, d]
```

FlashAttention 的关键：不在慢速的 HBM（高带宽显存）中存储完整的 S 和 P。把 Q、K、V 切成小块，逐块在快速的 SRAM（片上共享内存）中完成计算。

```python
# FlashAttention 的分块策略
for i in range(num_q_blocks):         # Q 切成块
    for j in range(num_kv_blocks):    # K、V 也切成块
        # 1. 从 HBM 加载 Q_block[i], K_block[j], V_block[j] 到 SRAM（快速读写）
        # 2. 在 SRAM 中算 S_block = Q_block @ K_block.T（小块，快）
        # 3. 在线 Softmax（不够存全部 S，用 running max 技巧）
        # 4. 在 SRAM 中算 P_block @ V_block（小块，快）
        # 5. 累积到 O（最终写回 HBM）
```

### 简化版 Triton 实现

```python
@triton.jit
def flash_attention_fwd(
    Q, K, V, O,                     # 输入输出张量的指针
    L,                              # 用于在线 Softmax 归一化的缓冲区
    seq_len, d_head,
    BLOCK_SIZE: tl.constexpr,       # 每个 block 处理的 token 数
):
    # 当前 program 处理 Q 的哪一块
    q_block_idx = tl.program_id(0)
    q_offset = q_block_idx * BLOCK_SIZE
    q_range = q_offset + tl.arange(0, BLOCK_SIZE)
    q_mask = q_range < seq_len

    # 加载 Q 块到 SRAM
    q = tl.load(Q + q_range[:, None] * d_head +
                tl.arange(0, d_head)[None, :], mask=q_mask[:, None])

    # 在线 Softmax 的状态
    m_i = tl.full([BLOCK_SIZE], float('-inf'), dtype=tl.float32)  # 当前最大值
    l_i = tl.zeros([BLOCK_SIZE], dtype=tl.float32)                 # 累加和
    o_i = tl.zeros([BLOCK_SIZE, d_head], dtype=tl.float32)         # 输出累积

    # 遍历 K、V 块
    for kv_start in range(0, seq_len, BLOCK_SIZE):
        kv_range = kv_start + tl.arange(0, BLOCK_SIZE)
        kv_mask = kv_range < seq_len

        # 加载 K、V 块
        k = tl.load(K + kv_range[:, None] * d_head +
                    tl.arange(0, d_head)[None, :], mask=kv_mask[:, None])
        v = tl.load(V + kv_range[:, None] * d_head +
                    tl.arange(0, d_head)[None, :], mask=kv_mask[:, None])

        # 计算 QK^T（在 SRAM 中）
        scores = tl.dot(q, tl.trans(k))  # [BLOCK_SIZE, BLOCK_SIZE]

        # 在线 Softmax
        m_curr = tl.max(scores, axis=1)  # 当前块的最大值
        m_new = tl.maximum(m_i, m_curr)   # 更新全局最大值
        scores = scores - m_new[:, None]  # 减去最大值（数值稳定的 exp）
        p = tl.exp(scores)

        # 更新累积值（用旧的 max 重新缩放旧的累积）
        l_i = l_i * tl.exp(m_i - m_new)
        l_i += tl.sum(p, axis=1)

        # 更新输出累积
        o_i = o_i * tl.exp(m_i - m_new)[:, None]
        o_i += tl.dot(p.to(tl.float16), v)

        m_i = m_new

    # 最终归一化
    o_i = o_i / l_i[:, None]

    # 写回 HBM
    tl.store(O + q_range[:, None] * d_head +
             tl.arange(0, d_head)[None, :], o_i.to(tl.float16), mask=q_mask[:, None])
```

---

## 4. 实践路径

| 步骤 | 做什么 |
|------|--------|
| **第一步** | 用 Triton 写一个逐元素操作（加法/乘法） |
| **第二步** | 写一个矩阵乘法 tiling kernel |
| **第三步** | 写一个简化版 FlashAttention（只实现前向） |
| **进阶** | 加入 Mask、Dropout、反向传播 |

### 参考资源

- **Triton 官方教程**：[triton-lang.org](https://triton-lang.org)
- **Liger Kernel**：为 LLM 训练优化的 Triton kernel 集合（可直接用于生产）
- **Unsloth**：使用 Triton 优化的微调框架

---

## 本章速查

| 概念 | 核心 |
|------|------|
| **GPU 瓶颈** | 内存带宽，不是计算能力 |
| **FlashAttention 策略** | 分块计算 + SRAM + 在线 Softmax |
| **Triton** | Python 风格 GPU 编程，编译器自动管理线程 |
| **核心语言** | Triton（入门）、CUDA（精通） |
| **参考** | Liger Kernel（生产级 Triton kernel 集合） |
