# Self-Attention 详解

这是整个 Transformer 最核心的机制。Self-Attention 解决一个根本问题：**给定一个序列，如何让每个 token 的表示融合所有相关上下文的信息？**

---

## 1. Query、Key、Value 框架

### 解决什么问题

最简单的方案是让所有 token 的向量直接做内积来衡量相关性。但问题在于：一个 token 自己的向量和自身内积一定最大（因为向量相同），模型会永远只关注自己——变成"自恋狂"。

### Q/K/V 分离的作用

将同一个输入通过三套不同的可学习投影（$W^Q, W^K, W^V$），分别映射到三个不同的空间：

| 组件 | 角色 | 直觉 |
|------|------|------|
| **Query** | "搜寻者" | 当前 token 发出的查询："我想要找什么样的信息？" |
| **Key** | "标签" | 每个 token 的标识："我是什么？谁应该关注我？" |
| **Value** | "内容" | 实际要传递的信息实体 |

类比信息检索：你去图书馆（所有 token），带着你的问题（Query），比对每本书的索引卡片（Key），然后阅读匹配的书的内容（Value）。

### 为什么这种分离有效

Q 和 K 使用不同的权重矩阵 → 即使两个 token 的原始 embedding 完全相同，它们的 Q 和 K 也可以不同 → 打破了"自己一定最关注自己"的对称性 → 模型学会了"去别的地方找信息"。

---

## 2. Scaled Dot-Product Attention：逐步推导

### 第一步：计算注意力分数

$$S = QK^T \quad \in \mathbb{R}^{n \times n}$$

$S_{ij}$ = 第 i 个 Q 与第 j 个 K 的点积。数值越大 → 方向越一致 → 第 i 个 token 越关注第 j 个 token。

### 第二步：缩放 $\sqrt{d_k}$

$$S_{\text{scaled}} = \frac{S}{\sqrt{d_k}}$$

**解决的问题**：当 $d_k$（Key 的维度）较大时，Q 和 K 的点积的方差为 $d_k$。假设每个分量独立且方差为 1：

$$\text{Var}(q \cdot k) = \text{Var}\left(\sum_{i=1}^{d_k} q_i k_i\right) = \sum_{i=1}^{d_k} \underbrace{\text{Var}(q_i)}_{=1} \cdot \underbrace{\text{Var}(k_i)}_{=1} = d_k$$

当 $d_k=64$ 时，内积的标准差为 8。这意味着很多内积值在 ±8 甚至更大。Softmax 对大输入值的梯度几乎为零：

$$\frac{\partial \,\text{softmax}(z_i)}{\partial z_i} = \text{softmax}(z_i)(1 - \text{softmax}(z_i))$$

当某个 $z_i$ 远大于其他值时，$\text{softmax}(z_i) \approx 1$，梯度 $\approx 0$。模型停止学习。

**除以 $\sqrt{d_k}$ 将方差恢复为 1**，保证 softmax 输入在健康范围内，梯度持续有效。这不是经验技巧，而是有明确数学依据的设计。

### 第三步：Softmax 归一化

$$A = \text{softmax}(S_{\text{scaled}})$$

每一行 $A_i$ 归一化为和为 1 的概率分布，含义是"第 i 个 token 对每个位置分配的注意力比例"。

**为什么需要和为 1**：确保后续加权求和时不会放大/缩小信号。无论序列多长（10 个 token 还是 1000 个），注意力权重之和恒为 1，输出量级保持不变。

### 第四步：加权聚合

$$\text{Output} = A \cdot V$$

每个位置的新表示 = 所有位置的 Value 的加权和，权重 = 注意力分数。这相当于说：**"每个 token 的新表示，是根据它与所有 token 的相关性，从它们那里有选择地收集信息而形成的"**。

---

## 3. 完整的数学总结

$$\text{Attention}(Q, K, V) = \text{softmax}\!\left(\frac{QK^T}{\sqrt{d_k}}\right) V$$

| 操作 | 解决的问题 |
|------|-----------|
| $QK^T$ | 将"我对你的关注度"量化为一个实数分数 |
| $\div \sqrt{d_k}$ | 防止大维度导致方差爆炸 → softmax 梯度消失 |
| $\text{softmax}$ | 分数 → 概率分布，且和为 1 确保信号不伸缩 |
| $\times V$ | 按注意力权重从各处收集信息 |

---

## 4. PyTorch 实现

```python
def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Q, K, V: [batch, seq_len, d_k]
    返回: [batch, seq_len, d_k]
    """
    d_k = Q.size(-1)
    scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_k)

    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))

    attn_weights = torch.softmax(scores, dim=-1)
    return torch.matmul(attn_weights, V)
```

---

## 5. 维度追踪：理解 Attention 的关键

理解大模型代码的核心能力就是在脑中追踪 tensor shape 的变化。一次 Self-Attention 的完整维度流：

```
输入: X            [batch, seq_len, d_model=512]
W_Q, W_K, W_V:     [d_model, d_k=64]

Q = X @ W_Q:       [batch, seq_len, 64]
K = X @ W_K:       [batch, seq_len, 64]
V = X @ W_V:       [batch, seq_len, 64]

scores = Q @ K^T:  [batch, seq_len, seq_len]  ← 每对token的关联矩阵
scaled = /√64
weights = softmax: [batch, seq_len, seq_len]  ← 每行为1
output = w @ V:    [batch, seq_len, 64]        ← 聚合后的新表示
```

**关键理解**：Attention 将一个 $[seq\_len, d]$ 的序列转化为另一个 $[seq\_len, d]$ 的序列，但新序列中每个 token 的表示已经融合了整个序列的上下文信息。
