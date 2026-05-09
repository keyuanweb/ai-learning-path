# RLHF 与 GRPO

RLHF 是让 ChatGPT 成为可能的最后一块拼图。GRPO 是 DeepSeek 提出的更高效的替代方案。

---

## 1. RLHF 的四模型架构

### 问题：如何优化"人类偏好"这个不可微分的指标

"回答好不好"没有数学公式可以精确计算（不同于交叉熵）。需要用人（或模型）的打分作为信号来优化模型。

### 四个模型的分工

| 模型 | 角色 | 是否训练 |
|------|------|---------|
| **Policy Model** | 被优化的对话模型 | 是 |
| **Reference Model** | SFT模型的冻结副本，防止跑偏 | 否 |
| **Reward Model** | 给回答打分（模仿人类偏好） | 否（已训好） |
| **Value Model** | 估计当前状态的"价值"（期望未来奖励） | 是 |

### PPO 的训练流程

```
1. Policy 对 prompt 生成回答
2. Reward Model 对回答打分
3. 用 PPO 算法更新 Policy：
   - 奖励高的回答 → 增加概率
   - 奖励低的回答 → 降低概率
   - 同时约束 Policy 不要偏离 Reference 太远 (KL 惩罚)
4. 重复，收集新的生成、打分、更新...
```

### RLHF 的工程复杂度

- 奖励模型需要**大量人工标注**（几万到几十万条偏好比较）
- PPO 训练**极不稳定**（四个模型之间的数值交互容易发散）
- 需要**持续在线采样**（训练过程中不断让模型生成新回答）
- 超参数敏感（KL 惩罚系数、裁剪范围、学习率三者互相影响）

---

## 2. GRPO (Group Relative Policy Optimization)

### DeepSeek 的动机

RLHF 需要一个独立的 Value Model 来估计"状态价值"（当前生成质量 × 期望未来质量）。但 Value Model 通常和 Policy Model 差不多大 → 又是一张 GPU 的显存占用 + 又是一套需要调参的超参数。

**GRPO 的洞察：不需要 Value Model。用同一 prompt 下多个回答的平均奖励作为基线即可。**

### GRPO 的工作机制

```python
# 对每个 prompt，生成一组 k 个回答
responses = [policy.generate(prompt) for _ in range(k)]
rewards = [reward_model(r) for r in responses]

# 组内归一化——减去均值，除以标准差
mean_r = mean(rewards)
std_r = std(rewards)
advantages = [(r - mean_r) / std_r for r in rewards]

# 用 advantage 替代 value baseline 来更新 policy
# advantage > 0: 这个回答比组内平均好 → 增加概率
# advantage < 0: 这个回答比组内平均差 → 降低概率
```

### GRPO 相比 PPO 的优势

| | PPO | GRPO |
|---|---|---|
| 需要的模型数 | 4 (Policy + Ref + Reward + Value) | 3 (Policy + Ref + Reward) |
| Value Model | 需要（与Policy同等规模） | 不需要 |
| 显存需求 | 高 | 低 ~20-30% |
| 训练稳定性 | 不稳定 | 更稳定（组内归一化天然防发散） |
| 代表模型 | GPT-4, Claude | DeepSeek-R1, DeepSeek-V3 |

GRPO 是 DeepSeek 模型训练管线中的核心技术。对开源社区来说，GRPO 降低了偏好对齐的门槛——少了一个大模型的训练和维护。

---

## 3. 奖励模型 (Reward Model)

### 怎么训练奖励模型

```
训练数据:
{"prompt": "解释什么是黑洞",
 "chosen": "黑洞是... [专业解释]",
 "rejected": "黑洞就是很黑很黑的洞"}

损失函数 (Bradley-Terry Model):
P(chosen > rejected) = sigmoid(r(chosen) - r(rejected))
loss = -log(sigmoid(r_chosen - r_rejected))

目标: 让 chosen 的得分显著高于 rejected
```

### 奖励模型的典型配置

- 基于 SFT 模型初始化（保留语言理解能力）
- 将最后的 lm_head 替换为一个标量输出头
- 典型的奖励模型比生成模型小（如 7B 模型训练奖励模型）
- 输出一个标量（分数越高越好）

---

## 4. SFT → 偏好对齐的完整管线

```
预训练模型 (Base Model)
    ↓ SFT (~10K 高质量指令-回答对)
SFT 模型 (会回答，但质量参差不齐)
    ↓ DPO 或 GRPO (~10-50K 偏好对)
对齐模型 (回答质量显著提升)
```

### 什么时候用 DPO，什么时候用 GRPO

| 条件 | DPO | GRPO |
|------|-----|------|
| 有现成的偏好数据对 | 直接用 | 还需要在线采样 |
| 有奖励模型 | 不需要 | 需要 |
| 数据量少 (< 5000) | DPO 更高效 | 需要大量在线 rollout |
| 追求极致效果 | 够用 | 理论上上限更高 |
| 工程简单性 | 极简 | 较复杂 |

**2025 年推荐**：先用 DPO 做第一次对齐（简单快速），如果效果不够好，再考虑 GRPO。
