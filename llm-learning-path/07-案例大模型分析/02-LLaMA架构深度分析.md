# LLaMA 架构深度分析

LLaMA 是开源大模型生态的奠基者。它的每一个设计决策都有明确的目的。

---

## 1. LLaMA 1 (2023)：小模型 + 多数据的范式转换

### 解决的问题

GPT-3 175B 很大很贵，普通人无法复现。LLaMA 证明了：**用更多数据训练更小的模型，效果可以超过更大的模型**。

### 核心设计

| 决策 | 解决的问题 |
|------|-----------|
| RoPE | 更好的位置建模和外推性 |
| Pre-Norm (RMSNorm) | 训练稳定性 |
| SwiGLU FFN | 比标准 ReLU FFN 更强的表达能力 |
| **只公开数据源训练** | 可复现性（不用私有数据） |
| 7B/13B/33B/65B 四级 | 不同硬件预算的可选方案 |

### Chinchilla 的影响

LLaMA 1 的 7B 模型用了 1T tokens（远超 Chinchilla 建议的 140B tokens 的"最优"量）。但这"过度训练"反而让 LLaMA-7B 在很多 benchmark 上超过了 GPT-3 175B。

**启示**：Chinchilla Law 给出的是"给定计算预算下困惑度最优"的配置，但下游任务能力可能受益于更多数据（即使超过了"最优"比例）。

---

## 2. LLaMA 2 (2023)：开源对齐模型

### 解决的问题

LLaMA 1 只有预训练权重，没有对话能力。用户需要自己做 SFT。LLaMA 2 直接发布了**已完成 SFT + RLHF 的对话模型**。

### 核心新增

| 决策 | 解决的问题 |
|------|-----------|
| GQA (Grouped-Query Attention) | KV Cache 太大（L2 的 70B 推理太贵） |
| 4K 上下文窗口 | 比 LLaMA 1 的 2K 加倍 |
| SFT + RLHF 对齐 | 用户不需要自己做对齐 |
| Ghost Attention | 多轮对话中 system prompt 的一致性 |

### Ghost Attention

**解决的问题**：多轮对话中，模型在第 3 轮就"忘了" system prompt 的要求。

**方案**：在 SFT 训练数据中，将 system prompt 重复地拼接到每一轮对话的开头，强迫模型学会在整个对话中保持 system prompt 的约束。

---

## 3. LLaMA 3 (2024)：开源追平闭源

### 关键改进

| 决策 | 解决的问题 |
|------|-----------|
| 8K 原生上下文 | L2 的 4K 不够用 |
| 128K vocab size (4× LLaMA 2) | 多语言效率（尤其是中文/阿拉伯语） |
| 15T tokens 训练数据 | 彻底"喂饱"模型 |
| GQA 保持 | 验证有效的推理优化 |
| 8B/70B/405B 三级 | 8B 可在消费卡运行，405B 挑战 GPT-4 |
| **MoE in Llama 4** | 参数量 vs 推理成本的矛盾 |

### LLaMA 3 vs LLaMA 2 的技术演进

```
LLaMA 2 7B:   RoPE + GQA + SwiGLU + RMSNorm + 2T tokens
LLaMA 3 8B:   更大 vocab (128K) + 7× 数据 (15T) + 原生 8K context
LLaMA 4:      引入 MoE（稀疏激活）
```

LLaMA 从 1 到 4 的演进代表了开源大模型的经典路线：**结构不激进变化，主要在数据规模、上下文长度和训练后对齐上持续改进**。

---

## 4. LLaMA 架构的技术取舍

### 为什么一直没有用 MLA 或 MoE (直到 LLaMA 4)

- **MLA**：压缩 KV Cache 的技术复杂，且 GQA 在多数场景已足够
- **MoE**：增加了微调和部署的复杂度。LLaMA 的定位是"简单好用"

**LLaMA 4 引入 MoE 说明**：参数量继续增长是必要的（能力提升），但密集模型的推理成本已经高到不可接受。MoE 从"前沿探索"变成了"必选项"。

---

## 5. LLaMA 架构对开源生态的影响

| 影响 | 具体 |
|------|------|
| RoPE | 成为所有后续开源模型的位置编码标准 |
| GQA | KV Cache 优化的"标准答案" |
| SwiGLU | 密集 FFN 的标配 |
| RMSNorm | 替代 LayerNorm 的默认选择 |
| LLaMA 命名惯例 | Qwen、DeepSeek、Mistral 都遵循了 7B/13B/70B 的规模分级 |
| 开源权重文化 | LLaMA 开创了"发布权重但不开放训练数据"的模式 |
