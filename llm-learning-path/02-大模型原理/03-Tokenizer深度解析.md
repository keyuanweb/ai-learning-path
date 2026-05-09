# Tokenizer 深度解析

Tokenizer 是大模型的第一个组件——也被最多人忽视。Tokenizer 质量直接影响模型能力上限。

---

## 1. Tokenizer 要解决的根本矛盾

### 矛盾：文本无限 vs 词表有限

世界上有无穷无尽的不同文本，但 embedding 矩阵的大小（vocab_size × d_model）不能无限增长——显存放不下，训练也太慢。

**所以需要将任意文本切分成由有限的「子词单元」(subword) 组成的序列。**

### 核心权衡

| | 大词表 (100K+) | 小词表 (32K) |
|---|---|---|
| **序列长度** | 短（每个 token 承载更多语义） | 长（需要更多 token 表达同样内容） |
| **Embedding 大小** | 大（vocab_size × d_model） | 小 |
| **新词处理** | 更多词可直接匹配 | 更多词需要拆解为子词 |
| **多语言支持** | 好 | 差（中文/阿拉伯语/编码效率低） |
| **推理速度** | 快（序列短 → Attention 便宜） | 慢（序列长 → Attention $O(n^2)$） |

---

## 2. BPE (Byte-Pair Encoding)：迭代合并的智慧

### 解决什么问题

如何从一个极小词表出发，自动构建一个大小可控、能覆盖所有文本的词表？

### BPE 算法

```
初始: 所有字符作为独立token: {"a","b","c",...,"你","好",...}
循环:
  1. 统计训练语料中所有相邻token pair的出现频率
  2. 将频率最高的pair合并为新token
  3. 重复直到词表达到目标大小
```

### 为什么这个简单算法效果好

1. **高频组合优先合并** → 常见词很快成为独立 token（"the"、"ing"、"tion"）
2. **低频词保持拆分** → 罕见词永远不会占用词表位置
3. **任何词都可表示** → 最终词表覆盖所有字符，任何新词都可以被分解

### 各模型的分词差异

| 模型 | Vocab Size | 中文效率 | 设计考量 |
|------|-----------|----------|---------|
| GPT-2 | 50K | 差（~3-4 tokens/汉字） | 英文优化 |
| LLaMA | 32K | 较差（~2-3 tokens/汉字） | 极小词表减少 embedding 参数 |
| Qwen | 152K | 优（~1 token/汉字） | 中文优先设计 |
| DeepSeek-V3 | 128K | 优（~1 token/汉字） | 多语言均衡优化 |

---

## 3. 数字处理：Tokenizer 的阿喀琉斯之踵

### 问题

`"384215"` 可能被 BPE 切分为 `["38", "42", "15"]`。模型看到的不是"三十八万四千二百一十五"，而是三个碎片。这是大模型算术能力弱的根源之一——数字是数学计算的基础单元，但 tokenizer 把它们切碎了。

### 解决方案

- **数字分隔**：每个数字作为独立 token → 词表爆炸
- **分位标记**：在数字前加特殊标记 `<|num|>` → 增加复杂度
- **按位拆分**："384215" → `["3","8","4","2","1","5"]` → 序列变长
- **更大的词表** → 更多数字整体被保留，但不如专门解决彻底

---

## 4. 特殊 Token 与对话格式

### Chat Template

对话模型需要区分 system prompt、用户输入、助手回复和工具调用。这通过特殊 token 实现：

```
<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
What is the capital of France?<|im_end|>
<|im_start|>assistant
The capital of France is Paris.<|im_end|>
```

Chat Template **不是可有可无的装饰**——它定义了模型看到的"对话结构"。错误的 template 会导致角色混乱、指令失效。

### 不同模型的 Chat Template

| 模型 | 格式 |
|------|------|
| Qwen | `<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n` |
| LLaMA 3 | `<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n...<|eot_id|>` |
| DeepSeek | `<|User|>...<|Assistant|>` |
| ChatML (通用) | `<|im_start|>role\n...<|im_end|>` |

---

## 5. Tokenizer 的暗坑

| 坑 | 后果 | 解决方案 |
|----|------|---------|
| **尾部空格** `"hello"` ≠ `" hello"` | 同一个词因为空格变成不同 token → 语义不连续 | 使用 SentencePiece（空格编码为 `▁`） |
| **中文低效** | 同等内容中文 token 数 = 英文 × 1.5-2 → 推理更贵 | 选 Qwen/DeepSeek tokenizer |
| **代码不友好** | 缩进和换行被切碎 → 代码生成质量差 | 训练时添加代码数据扩展词表 |
| **多语言不公平** | 高资源语言 token 少，低资源语言 token 多 | 语料平衡 + 调大词表 |
