# MoE 混合专家架构

MoE (Mixture of Experts) 是 2024-2025 大模型最重要的架构创新。它解决了一个根本矛盾：**更大的知识容量 vs 更低的推理成本**。

---

## 1. 密集模型的根本矛盾

### 问题

密集（Dense）模型中，每个 token 必须经过所有参数。这意味着：
- 想让模型知道更多东西 → 需要更多参数（增大 $d_{ff}$ 或增加层数）
- 更多参数 → 每个 token 的计算量更大 → 推理更慢、更贵
- **知识和推理成本的矛盾无法调和**

### MoE 的核心洞察

> **不需要每个 token 都经过所有参数。** 不同 token 涉及不同领域知识：法律术语用法律专家、编程语法用代码专家、日常对话用通用专家。让模型学习"该问谁"。

---

## 2. MoE 的工作机制

### 结构

```
普通 Transformer Block:           MoE Transformer Block:
    Attention                          Attention
       ↓                                  ↓
    FFN (全部参数激活)                  Router (路由)
                                       /  |  \
                                   Expert₁ Expert₂ ... Expertₙ
                                    (只有被选中的才计算)
                                       \  |  /
                                    加权合并
```

### 路由：token → 专家的指派

```python
# 每个 token 通过 router 计算各专家的得分
router_logits = self.router(x)           # [batch, seq, n_experts]
router_probs = softmax(router_logits)    # 归一化

# 选 top-k 个专家
top_k_probs, top_k_indices = topk(router_probs, k=2)

# 每个 token 只经过被选中的专家
output = 0
for k in range(top_k):
    expert = self.experts[top_k_indices[:, k]]
    weight = top_k_probs[:, k]
    output += weight * expert(x)   # 加权聚合
```

### "稀疏激活"的含义

- 密集模型：每个 token 激活 100% 的 FFN 参数
- MoE 模型：每个 token 只激活 5-20% 的 FFN 参数
- **总参数量可以巨大（知识多），但每 token 计算量很小（推理快）**

---

## 3. MoE 的核心工程挑战

### 挑战 1：负载均衡——"马太效应"

**问题**：训练中某些专家会被越来越多 token 选择（"热专家"），另一些专家逐渐被冷落。如果所有 token 都选同一个专家，MoE 退化为密集模型。

**解决方案**：

1. **辅助损失函数**：惩罚路由概率分布的不均衡

```python
# 鼓励每个专家被均匀选择
load_balance_loss = n_experts * sum(f_i * P_i)
# f_i: 专家i实际处理的token比例
# P_i: 路由分配给专家i的平均概率
# 两者均匀时 loss 最小
```

2. **专家容量上限**：每个专家最多处理 `total_tokens / n_experts * capacity_factor` 个 token，超出部分直接丢弃（token dropping）

3. **Node-Limited Routing** (DeepSeek)：考虑 GPU 拓扑的路由策略。如果两个专家在不同 GPU 上，跨 GPU 传输 token 的通信开销可能超过计算节省。DeepSeek 限制路由在同一节点内的专家之间

### 挑战 2：通信开销

**问题**：MoE 的专家分布在多张 GPU 上。每个 token 需要从当前 GPU "发送"到专家所在的 GPU → 计算完成后再"收回"。这种跨卡通信（all-to-all）是 MoE 训练和推理的主要瓶颈。

**解决方案**：
- 增大专家容量（让更多 token 在本地处理）
- expert parallelism 与 data parallelism/tensor parallelism 的混合策略
- DeepSeek 的精细化通信-计算重叠

### 挑战 3：微调困难

**问题**：MoE 模型参数量大但每个专家见到的样本少（因为 token 被分散了），导致微调时更容易过拟合。需要更大的微调数据集。

---

## 4. 各模型 MoE 设计对比

| 设计决策 | DeepSeek-V3 | LLaMA 4 Maverick | Qwen3-MoE | Mixtral 8×7B |
|----------|-------------|------------------|-----------|--------------|
| **总参数** | 671B | 400B | 235B | 47B |
| **活跃参数** | 37B (5.5%) | 17B (4.3%) | 22B (9.4%) | 13B (27.7%) |
| **专家数** | 256 | 128 | 128 | 8 |
| **Top-k** | 9 (1共享+8路由) | 2 (1共享+1路由) | 8 | 2 |
| **共享专家** | 是 | 是 | 否 | 否 |

### 设计取舍分析

- **共享专家**：保留一个通用专家（所有 token 都经过）→ 捕获通用语言能力；路由专家负责领域专长。DeepSeek 和 LLaMA 4 选择此方案
- **无共享专家**：所有知识都通过路由选择 → 更纯净的稀疏激活，但需要更复杂的负载均衡。Qwen3 的选择
- **极端稀疏 (DeepSeek)**：5.5% 的激活率 → 推理极快，但需要 256 个专家确保路由有足够选择空间
- **高激活 (Mixtral)**：27.7% → 更接近密集模型的建模能力，但推理加速有限

---

## 5. MoE 什么时候适合你

| 场景 | 建议 |
|------|------|
| 极致推理吞吐 + 低成本 | MoE（DeepSeek-V3 级别） |
| 单卡推理 | 小密集模型（MoE 全部参数仍需加载到显存） |
| 多 GPU 集群推理 | MoE 可发挥专家并行的吞吐优势 |
| 微调定制 | 密集模型更简单，MoE 微调难度大 |
| 追求模型能力上限 | 密集模型（GPT-4 级别）目前仍领先 |

MoE 不是免费的：虽然推理 FLOPS 低了，但总参数量的显存开销（所有专家都要在显存里）和通信开销是新的瓶颈。
