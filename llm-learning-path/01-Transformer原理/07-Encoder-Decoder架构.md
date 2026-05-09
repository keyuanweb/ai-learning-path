# Encoder-Decoder 架构

原版 Transformer 是完整的 Encoder-Decoder 结构。理解它，才能理解为什么后来 ChatGPT 和所有主流大模型都"简化"成了 Decoder-Only。

---

## 1. 为什么需要 Encoder-Decoder

### 解决的问题：序列到序列的映射

翻译、摘要等任务需要将一个序列转化为另一个序列，且两个序列的**长度不同、结构不同**。输入是"一种语言"的表达，输出是"另一种语言"的表达。

需要一个架构：一部分负责"理解输入"（Encoder），另一部分负责"生成输出"（Decoder），两者通过一个桥梁连接。

---

## 2. 完整架构

```
Input → [Encoder × N] → Encoder Output
                              ↓
Output ← [Decoder × N] ← (cross-attention from Encoder Output)
```

### Encoder Block
```
x = x + MultiHeadAttention(LayerNorm(x))     # 双向 Self-Attention
x = x + FFN(LayerNorm(x))
```
每个 token 能看到所有 token（双向）→ 充分理解上下文。

### Decoder Block
```
x = x + MaskedMultiHeadAttention(LayerNorm(x))  # 因果 Self-Attention
x = x + CrossAttention(LayerNorm(x), enc_out)   # Cross-Attention
x = x + FFN(LayerNorm(x))
```
- 第一层：因果 Self-Attention（只看已生成的部分）
- 第二层：Cross-Attention（从 Encoder 输出中获取源语言信息）
- 第三层：FFN（处理融合后的信息）

---

## 3. 三种 Attention 的分工

| 类型 | 位置 | 作用 | 解决的问题 |
|------|------|------|-----------|
| **Self-Attention** (Encoder) | Encoder | 双向理解输入序列 | 理解"这句话每个词之间的关系" |
| **Masked Self-Attn** (Decoder) | Decoder 第1层 | 单向理解已生成内容 | 生成时不能偷看未来的词 |
| **Cross-Attention** | Decoder 第2层 | 从Encoder取信息 | "我生成到哪了？源句的哪部分和当前相关？" |

### Cross-Attention 的工作机制

```
Q ← Decoder: "我现在要生成什么？谁有我需要的信息？"
K ← Encoder: "我的每个位置包含什么信息？"
V ← Encoder: "把我的信息给Decoder"

Q_dec · K_enc → 注意力分数 → 加权聚合 V_enc
```

在翻译中：
```
源句 (Encoder): "The agreement on European economic zone was signed..."
正在生成 (Decoder): "关于欧洲经济区的协议已经签..."

Decoder 当前要生成下一个词:
  Q("签") 去 Encoder 中查找:
    → K("signed"): 高分 ✓
    → K("agreement"): 中分
    → K("The"): 低分
  聚合 V("signed") 的信息 → 输出 "署"（完成"签署"）
```

---

## 4. 为什么 Decoder-Only 成了绝对主流

### Encoder-Decoder 的劣势

1. **两套参数**：Encoder 和 Decoder 各有自己的参数，同参数总量下每套参数更小
2. **训练目标不统一**：Encoder 用 MLM，Decoder 用 CLM，需要多种损失
3. **不灵活**：擅长翻译/摘要等有明确输入→输出的任务，对话和通用生成不够自然

### GPT 用 Decoder-Only 证明的事实

> 一个简单的自回归生成模型，如果足够大，可以完成所有 NLP 任务——无需 Encoder。

关键逻辑：
- 翻译 → "英语: Hello → 中文:"（当成一个序列，让模型补全）
- 摘要 → "Summarize: [文章] → Summary:"
- 问答 → "Question: [问题] → Answer:"

**所有任务都统一为"给定上文，预测下文"——Decoder-Only 的天才简化**。

### Decoder-Only 为什么更可扩展

| 维度 | Encoder-Decoder | Decoder-Only |
|------|----------------|--------------|
| 结构复杂度 | 高（三种Attention） | 低（只有Causal Self-Attention） |
| 参数利用率 | 低（两套参数分别用） | 高（一套参数做所有） |
| 训练目标 | 多目标 | 单目标（next token prediction） |
| 工程优化 | 复杂 | 简单，生态成熟 |
| Scaling友好度 | 一般 | 极好 |

Scaling Law 的核心启示：**在绝对的数据量和参数量面前，架构的精细化不如简单粗暴的 scale**。Decoder-Only 因为结构简单、训练目标单一，成为了 scale 的最佳载体。

---

## 5. 什么时候还用 Encoder-Decoder

| 场景 | 推荐 | 原因 |
|------|------|------|
| 机器翻译 | Encoder-Decoder (T5式) | 明确的双序列映射 |
| 长文档摘要 | Encoder-Decoder | Encoder 独立编码长文，Decoder 生成精炼 |
| 语音识别 | Encoder-Decoder | 语音特征 → 文本，天然序列映射 |
| 通用对话/代码/推理 | Decoder-Only | Scale + 统一 = 更好 |
