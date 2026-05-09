# Decoder-Only 架构

2025 年，所有主流大模型都是 Decoder-Only 架构。这不是偶然——它解决了 Encoder-Decoder 的固有矛盾。

---

## 1. Encoder-Decoder 的固有矛盾

### 参数割裂

Encoder 和 Decoder 各有独立的参数。假设总参数量固定为 N，实际 Encoder 做"理解"的只有 N/2，Decoder 做"生成"的也只有 N/2。同样的参数量，一套参数做两件事不如一套参数做所有事效率高。

### 训练目标不统一

- Encoder 训练目标：理解上下文（双向，MLM）
- Decoder 训练目标：生成下文（单向，CLM）

两个目标可能冲突——双向理解学到的特征，不一定对单向生成有用。模型实际上是"两头讨好"。

---

## 2. GPT 的天才简化

OpenAI 在 GPT 论文中提出的洞察：

> **所有 NLP 任务都可以转化为"给定上文，预测下文"。**

- 翻译："I love you → 翻译成中文：我"（预测下一个字"爱"）
- 摘要："Summarize: [长文] → Summary: 本文"（预测下一个字）
- 问答："Q: 地球到月球多远? A: 大约"（预测下一个字"38"）
- 代码："def fib(n):\n    "（预测下一行代码）

不需要 Encoder 来"理解"，不需要 Cross-Attention 来"对齐"。一切都统一在 Next Token Prediction 这一个任务下。

### 统一的代价和收益

| 设计简化 | 代价 | 收益 |
|----------|------|------|
| 去掉 Encoder | "理解"能力不如 BERT 强 | 参数全部用于生成，更高效 |
| 去掉 Cross-Attention | 无显式的源→目标对齐 | 结构更简单，更易 scale |
| 统一为 Next Token Prediction | 部分任务格式不自然 | 训练极度简单，一个损失函数 |

---

## 3. 为什么简单 = 可 Scale

Scaling Law 的核心启示：**在绝对的数据量和算力面前，架构的精细化不如简单粗暴的扩展**。

Decoder-Only 的优势：
- **结构简化** = 工程优化容易 → DeepSpeed/FlashAttention/GQA 等优化都针对 Decoder-Only
- **训练目标单一** = 损失函数就是交叉熵 → 不需要平衡多目标权重
- **生态收敛** = HuggingFace/vLLM/llama.cpp 等都优先支持 → 工具链最成熟

这不是说 Encoder-Decoder 不好，而是说**在 scale 这个维度上，简单就是更好的**。

---

## 4. 现代 Decoder-Only 的标准组件

```
Input Tokens
    ↓
Token Embedding (可学习查表)
    ↓
[× N layers]
    ├── RMSNorm (Pre-Norm)
    ├── GQA + RoPE Causal Self-Attention
    ├── 残差连接
    ├── RMSNorm (Pre-Norm)
    ├── SwiGLU FFN (可选 MoE)
    └── 残差连接
    ↓
RMSNorm (Final)
    ↓
lm_head (与 Token Embedding 共享权重)
    ↓
Output Logits
```

这些组件的每个设计细节都有明确的问题在解决：

| 组件 | 解决的问题 |
|------|-----------|
| Pre-Norm (RMSNorm) | 深层训练不稳定 |
| RoPE | Attention 不感知相对位置 |
| GQA | MHA 的 KV Cache 显存开销大 |
| SwiGLU FFN | 简单 ReLU 非线性不够灵活 |
| MoE (可选) | 参数量 vs 计算成本的矛盾 |
| Weight Tying | Embedding 和 lm_head 参数冗余 |

---

## 5. Prefix-Decoder：第三条路？

GLM 和 U-PaLM 采用了折中方案——Encoder 和 Decoder 共享参数，但有双向注意力的前缀和单向注意力的后缀。这试图同时获得理解能力和生成能力，但实现复杂度和参数效率之间的权衡目前仍不如纯 Decoder-Only 方案有竞争力。
